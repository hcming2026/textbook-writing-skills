#!/usr/bin/env python3
"""skill 定义一致性检查（零依赖，Python 3.8+）

检查九个 skill 与规范库之间「应该一致」的五件事。这些都是人工审阅时
靠翻文件才能发现的类型，写成脚本后可重复执行、可进 CI。

用法：
    python tools/consistency_check.py            # 在仓库根执行
    python tools/consistency_check.py --quiet    # 只输出汇总

退出码：0 表示全部通过，1 表示有 ERROR。
WARN 不影响退出码，但建议逐条判断。
"""

import ast
import hashlib
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS_DIR = os.path.join(ROOT, "skills")
RULES_DIR = os.path.join(ROOT, "规范库")

BASE_SECTIONS = ["适用场景", "输入要求", "执行步骤", "输出格式", "质量要求", "禁止事项"]

# 允许额外增加的节（目前只有 textbook-polish，登记并注明理由）
EXTRA_SECTIONS_ALLOWED = {
    # 润色是「口径敏感」的活：合不合规与像不像机器写是两套刻度，必须并列声明四维目标，
    # 否则读者会把诊断指标当合规判据（v1.2.x 的实际事故）。故允许独立的「润色目标」节。
    # 六种合法动作是改稿的权限边界，与「禁止事项」互补而非重复，故独立成节。
    "textbook-polish": ["润色目标", "改稿动作"],
}

errors, warns = [], []


def err(code, msg):
    errors.append((code, msg))


def warn(code, msg):
    warns.append((code, msg))


def read(path):
    with open(path, encoding="utf-8", newline="") as f:
        return f.read().replace("\r\n", "\n")


def skill_names():
    return sorted(
        d for d in os.listdir(SKILLS_DIR)
        if os.path.isfile(os.path.join(SKILLS_DIR, d, "SKILL.md"))
    )


def strip_fences(text):
    """去掉 ``` 围栏内的内容，避免把示例里的 ## 标题当成真实章节。"""
    out, fence = [], False
    for line in text.split("\n"):
        if line.strip().startswith("```"):
            fence = not fence
            continue
        if not fence:
            out.append(line)
    return "\n".join(out)


def body_of(text):
    m = re.match(r"^---\n.*?\n---\n", text, re.S)
    return text[m.end():] if m else text


def frontmatter_of(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    return m.group(1) if m else ""


# ---------- 检查 1：references 副本与母本一致 ----------
def check_reference_copies():
    mothers = {}
    for name in os.listdir(RULES_DIR):
        if name.endswith(".md"):
            mothers[name] = hashlib.md5(
                open(os.path.join(RULES_DIR, name), "rb").read()
            ).hexdigest()
    for sk in skill_names():
        ref_dir = os.path.join(SKILLS_DIR, sk, "references")
        if not os.path.isdir(ref_dir):
            continue
        for fname in sorted(os.listdir(ref_dir)):
            if fname not in mothers:
                continue  # skill 独有的参考文件，不参与比对
            p = os.path.join(ref_dir, fname)
            h = hashlib.md5(open(p, "rb").read()).hexdigest()
            if h != mothers[fname]:
                err("REF-DRIFT", f"{sk}/references/{fname} 与 规范库/{fname} 不一致，"
                                f"以母本为准重新同步（母本方向不可逆）")


# ---------- 检查 2：SKILL.md 内部引用路径存在 ----------
def check_references_exist():
    for sk in skill_names():
        d = os.path.join(SKILLS_DIR, sk)
        text = read(os.path.join(d, "SKILL.md"))
        refs = set(re.findall(r"`((?:references|assets|scripts)/[^`\s]+?)`", text))
        for r in sorted(refs):
            if not os.path.exists(os.path.join(d, r)):
                err("DEAD-REF", f"{sk}/SKILL.md 引用了不存在的 {r}")


# ---------- 检查 3：脚本参数与规则库数值一致 ----------
def check_params_consistency():
    # 规则库里出现的所有区间
    allowed = set()
    for name in ("学段适配.md", "体例规范.md"):
        p = os.path.join(RULES_DIR, name)
        if not os.path.exists(p):
            continue
        for a, b in re.findall(r"(\d+)\s*[–\-]\s*(\d+)", read(p)):
            allowed.add((int(a), int(b)))

    script = os.path.join(SKILLS_DIR, "unit-writer", "scripts", "check_draft.py")
    if not os.path.exists(script):
        warn("PARAMS", "未找到 unit-writer/scripts/check_draft.py，跳过参数比对")
        return
    src = read(script)
    tree = ast.parse(src)
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values):
                if not isinstance(v, ast.Dict):
                    continue
                for vk, vv in zip(v.keys, v.values):
                    if (isinstance(vv, ast.Tuple) and len(vv.elts) == 2
                            and all(isinstance(e, ast.Constant) for e in vv.elts)):
                        pair = (vv.elts[0].value, vv.elts[1].value)
                        if isinstance(pair[0], int):
                            found.append(pair)
    if not found:
        warn("PARAMS", "未能从 check_draft.py 解析出区间，跳过比对")
        return
    for pair in sorted(set(found)):
        if pair not in allowed:
            err("PARAMS", f"check_draft.py 的区间 {pair[0]}–{pair[1]} 在规范库里找不到出处，"
                          f"规则改了脚本没跟")


# ---------- 检查 4：章节结构一致 ----------
def check_sections():
    for sk in skill_names():
        body = strip_fences(body_of(read(os.path.join(SKILLS_DIR, sk, "SKILL.md"))))
        secs = [l[3:].strip() for l in body.split("\n") if l.startswith("## ")]
        missing = [s for s in BASE_SECTIONS if s not in secs]
        if missing:
            err("SECTION", f"{sk} 缺少必备章节：{'、'.join(missing)}")
        extra = [s for s in secs if s not in BASE_SECTIONS]
        allowed = EXTRA_SECTIONS_ALLOWED.get(sk, [])
        unexpected = [s for s in extra if not any(s.startswith(a) for a in allowed)]
        if unexpected:
            warn("SECTION", f"{sk} 有非标准章节：{'、'.join(unexpected)}")


# ---------- 检查 5：步骤编号连续 ----------
def check_step_numbers():
    for sk in skill_names():
        body = strip_fences(body_of(read(os.path.join(SKILLS_DIR, sk, "SKILL.md"))))
        nums = [int(m.group(1)) for m in re.finditer(r"^(\d+)\.\s\*\*", body, re.M)]
        if nums and nums != list(range(1, len(nums) + 1)):
            err("STEP", f"{sk} 的执行步骤编号不连续：{nums}")


# ---------- 检查 6：description 带边界声明 ----------
def check_description_boundary():
    for sk in skill_names():
        fm = frontmatter_of(read(os.path.join(SKILLS_DIR, sk, "SKILL.md")))
        m = re.search(r"^description:\s*(.+)$", fm, re.M)
        if not m:
            err("DESC", f"{sk} 缺少 description 字段")
            continue
        desc = m.group(1)
        if "不用于" not in desc and "不负责" not in desc:
            err("DESC", f"{sk} 的 description 没有边界声明（不用于/不负责），"
                        f"渐进加载时路由环节看不到「不适用」")
        if len(desc) > 400:
            warn("DESC", f"{sk} 的 description 长度 {len(desc)} 字，过长会稀释触发词权重")


def main():
    quiet = "--quiet" in sys.argv
    check_reference_copies()
    check_references_exist()
    check_params_consistency()
    check_sections()
    check_step_numbers()
    check_description_boundary()

    if not quiet:
        for code, msg in errors:
            print(f"[ERROR] {code} :: {msg}")
        for code, msg in warns:
            print(f"[WARN ] {code} :: {msg}")
        if errors or warns:
            print()
    print(f"结果：{len(errors)} 个 ERROR，{len(warns)} 个 WARN")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
