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


# ---------- 检查 7：引用的规则编号必须在母本里真实存在 ----------
# 加这条的原因是一次真实事故：v1.3.0 的 textbook-polish/references/改稿动作.md
# 把「搭配不当／成分残缺／指代不明」指到 YY-12／13／14，而母本那三条分别是
# 「案例虚构化」「MBA 案例须含信息不对称」「案例数据自洽」——六处引用全部悬空。
# 编号写对了格式、指向了别的内容，比写错格式更难发现：肉眼看着像有依据，
# 实际上等于自造判据。前六项检查都发现不了，故单列一项。
RULE_ID = re.compile(r"\b((?:TY|YY|XD|LX)-\d{2}|SJ-X\d)\b")

# 这些文件里允许出现母本之外的编号：测试用例是故意写错的样本稿
RULE_REF_SKIP = ("测试用例",)


def check_rule_ids():
    master = set()
    if not os.path.isdir(RULES_DIR):
        warn("RULE-ID", "未找到 规范库/，跳过编号校验")
        return
    for name in os.listdir(RULES_DIR):
        if name.endswith(".md"):
            master |= set(RULE_ID.findall(read(os.path.join(RULES_DIR, name))))
    if not master:
        warn("RULE-ID", "规范库/ 内未解析到任何规则编号")
        return

    targets = []
    for root, _dirs, files in os.walk(SKILLS_DIR):
        if any(s in root for s in RULE_REF_SKIP):
            continue
        for f in files:
            if f.endswith((".md", ".py")):
                targets.append(os.path.join(root, f))

    for p in targets:
        text = read(p)
        for rid in sorted(set(RULE_ID.findall(text))):
            if rid not in master:
                rel = os.path.relpath(p, ROOT).replace("\\", "/")
                err("RULE-ID", f"{rel} 引用 {rid}，但母本里没有这条编号")


# ---------- 检查 8：跨 skill 共用的脚本副本必须逐字节一致 ----------
# check_draft.py 在 3 处、lang_rules.py 在 4 处各存一份，靠 cp 同步。
# 这层如果没有守门，改了主份忘了复制，同一份稿件在「写作 / 审校 / 排版」三个环节
# 会得出不同结论——而且不会报错，只会静默地少报或多报几条。
SHARED_SCRIPTS = {
    "check_draft.py": 3,   # unit-writer / textbook-reviewer / textbook-formatter
    "lang_rules.py": 4,    # 上述三处 + textbook-polish
}


def check_script_copies():
    for name, expect in SHARED_SCRIPTS.items():
        found = []
        for sk in skill_names():
            p = os.path.join(SKILLS_DIR, sk, "scripts", name)
            if os.path.exists(p):
                found.append((sk, p))
        if not found:
            continue
        if len(found) != expect:
            err("SCRIPT-COUNT",
                f"{name} 应有 {expect} 份副本，实有 {len(found)} 份："
                + "、".join(sk for sk, _ in found))
        digests = {sk: hashlib.md5(open(p, "rb").read()).hexdigest() for sk, p in found}
        uniq = set(digests.values())
        if len(uniq) > 1:
            # 以 textbook-reviewer 那份为准（它是主份所在）
            base = digests.get("textbook-reviewer")
            drift = [sk for sk, h in digests.items() if h != base]
            err("SCRIPT-DRIFT",
                f"{name} 各副本内容不一致，与主份（textbook-reviewer）不同："
                + "、".join(drift) + "；用 cp 从主份重新同步")


# ---------- 检查 9：路由 skill 的环节表必须覆盖全部 skill ----------
# 加这条的原因是一次真实事故：v1.3.0 新增 textbook-polish，README 链条图加上了，
# 但 textbook-builder 的判定表没加——它的表固定 0–8 九步，还写着「不得自行发明
# 新环节（第 9、10 步）」。结果是第 10 个 skill 存在却永远路由不到，
# 用户在项目里问「下一步做什么」时会被引到排版，跳掉润色。
# 新增 skill 时最容易漏的就是这张表，故单列一项。
ROUTER_SKILL = "textbook-builder"


def check_router_coverage():
    p = os.path.join(SKILLS_DIR, ROUTER_SKILL, "SKILL.md")
    if not os.path.exists(p):
        warn("ROUTER", f"未找到 {ROUTER_SKILL}/SKILL.md，跳过路由覆盖校验")
        return
    text = read(p)
    all_skills = set(skill_names())
    listed = set(re.findall(r"`([a-z][a-z0-9-]+)`", text)) & all_skills
    missing = all_skills - {ROUTER_SKILL} - listed
    if missing:
        err("ROUTER", f"{ROUTER_SKILL} 的环节表未覆盖：{'、'.join(sorted(missing))}"
                      f"——新 skill 不进判定表就永远路由不到")
    # 反向：表里出现但目录里没有的，已在 check 1/2 覆盖；这里只提示
    stale = listed - set(skill_names())
    if stale:
        err("ROUTER", f"{ROUTER_SKILL} 引用了不存在的 skill：{'、'.join(sorted(stale))}")


def main():
    quiet = "--quiet" in sys.argv
    check_reference_copies()
    check_references_exist()
    check_params_consistency()
    check_sections()
    check_step_numbers()
    check_description_boundary()
    check_rule_ids()
    check_script_copies()
    check_router_coverage()

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
