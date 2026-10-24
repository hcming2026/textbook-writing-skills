#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_draft.py — 教材稿件事实性检查（unit-writer / textbook-reviewer 共用）

用法：
    python scripts/check_draft.py <稿件.md> [--json]

只查「能用规则判定」的项：六栏齐全与顺序、各栏字数区间、练习三层、
题目是否挂 LO、禁用词、跳跃推理词、句长段长、图表编号与来源、待核实标注。
不做质量评分——分数由 textbook-reviewer 依 审校标准.md 给出。

退出码：0 = 无 ERROR；1 = 存在 ERROR（不得交付）。
"""

import re
import sys
import json
from pathlib import Path

LEVEL_PARAMS = {
    "本科高年级": {"导语": (150, 250), "正文": (3000, 4500), "案例": (800, 1200), "拓展": (100, 200),
                   "练习比例": (5, 3, 2), "段限": 200},
    "MBA": {"导语": (200, 350), "正文": (2500, 3500), "案例": (1200, 2000), "拓展": (100, 200),
            "练习比例": (4, 3, 3), "段限": 180},
}
SECTIONS = ["导语", "正文", "案例", "思考", "练习", "拓展"]
BANNED = ["赋能", "抓手", "闭环", "生态位", "打法", "组合拳", "让我们一起来学习",
          "本章将带你走进", "毋庸置疑"]
JUMP = ["显然", "众所周知", "不难看出"]
LO_RE = re.compile(r"LO-\d+-\d+")
FIG_RE = re.compile(r"(图|表)\s*\d+\.\d+\.\d+")
VAGUE_RE = re.compile(r"(谈谈你的|说说你的|谈谈对|谈谈你对|你的理解|谈谈看法|有何感想)")
ZH = re.compile(r"[\u4e00-\u9fa5]")


def zh_len(t):
    return len(ZH.findall(t))


class R:
    def __init__(self):
        self.e, self.w, self.info = [], [], []

    def err(self, w, m): self.e.append((w, m))
    def warn(self, w, m): self.w.append((w, m))
    def note(self, w, m): self.info.append((w, m))

    def dump(self, as_json=False):
        if as_json:
            print(json.dumps({"errors": self.e, "warns": self.w, "info": self.info},
                             ensure_ascii=False, indent=1))
        else:
            for w, m in self.e: print(f"[ERROR] {w} :: {m}")
            for w, m in self.w: print(f"[WARN ] {w} :: {m}")
            for w, m in self.info: print(f"[INFO ] {w} :: {m}")
            print(f"\n结果：{len(self.e)} 个 ERROR，{len(self.w)} 个 WARN")
        return 1 if self.e else 0


def split_front(lines):
    if not lines or lines[0].strip() != "---":
        return {}, 0
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            fm = {}
            for raw in lines[1:i]:
                if ":" in raw and not raw.startswith(" "):
                    k, v = raw.split(":", 1)
                    fm[k.strip()] = v.strip()
            return fm, i + 1
    return {}, 0


def parse_sections(lines, start):
    secs, order, cur, buf = {}, [], None, []
    for i in range(start, len(lines)):
        line = lines[i]
        m = re.match(r"^##\s+(\S+)\s*$", line)
        if m:
            if cur: secs[cur] = "\n".join(buf)
            cur = m.group(1); order.append(cur); buf = []
        else:
            buf.append(line)
    if cur: secs[cur] = "\n".join(buf)
    return secs, order


def main(argv):
    as_json = "--json" in argv
    args = [a for a in argv[1:] if not a.startswith("--")]
    if not args:
        print("用法：python check_draft.py <稿件.md> [--json]")
        return 2
    path = Path(args[0])
    if not path.is_file():
        print(f"文件不存在：{path}")
        return 2

    lines = path.read_text(encoding="utf-8").splitlines()
    rep = R()
    fm, start = split_front(lines)

    if not fm:
        rep.err("frontmatter", "缺少 YAML frontmatter")
    level = fm.get("level", "").strip()
    if level and level not in LEVEL_PARAMS:
        rep.err("frontmatter", f"level 只能为「本科高年级」或「MBA」，实为「{level}」")
    P = LEVEL_PARAMS.get(level, LEVEL_PARAMS["MBA"])
    for k in ["course", "unit", "lesson", "title", "level", "lo"]:
        if not fm.get(k):
            rep.err("frontmatter", f"缺少字段 `{k}`")
    if fm.get("lo") and not LO_RE.search(fm["lo"]):
        rep.err("frontmatter", "`lo` 字段未给出合法的 LO 编号")

    secs, order = parse_sections(lines, start)

    # 1. 六栏齐全与顺序
    if order != SECTIONS:
        missing = [s for s in SECTIONS if s not in order]
        extra = [s for s in order if s not in SECTIONS]
        if missing: rep.err("结构", f"缺少栏目：{'、'.join(missing)}")
        if extra: rep.err("结构", f"出现未定义的栏目：{'、'.join(extra)}")
        if not missing and not extra: rep.err("结构", f"栏目顺序应为 {' → '.join(SECTIONS)}，实为 {' → '.join(order)}")

    # 2. 各栏字数
    for s in ["导语", "正文", "案例", "拓展"]:
        if s not in secs: continue
        n = zh_len(secs[s])
        lo, hi = P[s]
        if n < lo * 0.8 or n > hi * 1.2:
            rep.err(s, f"{n} 字，超出区间 {lo}–{hi}（容差 ±20%）")
        elif n < lo or n > hi:
            rep.warn(s, f"{n} 字，略超出区间 {lo}–{hi}")

    # 3. 练习分层
    if "练习" in secs:
        ps = secs["练习"]
        layers = {"基础层": [], "提高层": [], "拓展层": []}
        cur = None
        for line in ps.splitlines():
            m = re.match(r"^###\s*(\S+?)(层)?\s*$", line)
            if m:
                cur = m.group(1) + ("层" if "层" in line else "")
                cur = cur if cur in layers else (m.group(1) if m.group(1) in layers else cur)
                continue
            if cur in layers and re.match(r"^\s*\d+[\.、)]", line):
                layers[cur].append(line)
        got = {k: v for k, v in layers.items() if v}
        if not got:
            # K7 修复：结构缺失不得短路。三层小标题认不出来时，按整栏当一层继续体检，
            # 否则「题目未挂 LO」「不可评分题」等隐藏问题会被带到下一环。
            rep.err("练习", "未识别到基础层/提高层/拓展层三层小标题，以下按整栏体检")
            loose = [l for l in ps.splitlines() if re.match(r"^\s*\d+[\.、)]", l)]
            if not loose:
                rep.err("练习", "练习栏内未识别到任何编号题目")
            else:
                rep.warn("练习", f"结构缺失，暂按整体 {len(loose)} 道题检查（修好三层后须重跑本脚本）")
                no_lo = [q for q in loose if not LO_RE.search(q)]
                if no_lo:
                    rep.err("练习", f"{len(no_lo)}/{len(loose)} 道题未标注 LO，首条：{no_lo[0][:30]}…")
                vague = [q for q in loose if VAGUE_RE.search(q)]
                if vague:
                    rep.err("练习", f"{len(vague)} 道题为不可评分题（LX-07），首条：{vague[0][:30]}…")
        else:
            for k in ["基础层", "提高层", "拓展层"]:
                if k not in got:
                    rep.err("练习", f"缺少「{k}」")
            need = {"基础层": 3, "提高层": 2, "拓展层": 1}
            for k, n in need.items():
                if k in got and len(got[k]) < n:
                    rep.err("练习", f"{k}仅 {len(got[k])} 题，至少 {n} 题")
            total = sum(len(v) for v in got.values())
            if total:
                ratio = tuple(round(len(got.get(k, [])) / total, 2) for k in ["基础层", "提高层", "拓展层"])
                exp = tuple(r / 10 for r in P["练习比例"])
                if any(abs(a - b) > 0.12 for a, b in zip(ratio, exp)):
                    rep.warn("练习", f"三层比例 {ratio}，建议接近 {exp}")
                all_items = [q for k in got for q in got[k]]
                no_lo = [q for q in all_items if not LO_RE.search(q)]
                if no_lo:
                    rep.err("练习", f"{len(no_lo)} 道题未标注 LO，首条：{no_lo[0][:30]}…")
                vague = [q for q in all_items if VAGUE_RE.search(q)]
                if vague:
                    rep.err("练习", f"{len(vague)} 道题为不可评分题（LX-07），首条：{vague[0][:30]}…")

    # 4. 禁用词与跳跃词
    full = "\n".join(secs.values())
    for w in BANNED:
        c = full.count(w)
        if c:
            rep.err("语言", f"出现禁用词「{w}」×{c}（语言风格 六、禁用词表；总则 YY-01）")
    for w in JUMP:
        c = full.count(w)
        if c:
            rep.err("语言", f"出现跳跃推理词「{w}」×{c}（YY-11）")

    # 4b. 数字空格分节（YY-21）：1 098 这类写法是英文排版直译，不合 GB/T 15835
    for m in re.finditer(r"(?<![\d,.])\d{1,3}(?: \d{3})+(?![\d])", full):
        rep.warn("语言", f"数字用了空格分节「{m.group(0)}」，应为 {m.group(0).replace(' ', ',')} 或连写（YY-21）")

    # 5. 句长与段长
    para_limit = P["段限"]
    for name, body in secs.items():
        long_sent, long_para = [], []
        for para in [p for p in body.split("\n\n") if p.strip()]:
            if re.match(r"^\s*(#{1,6}|[|>]|\d+[\.、)]|[-*+])", para.strip()):
                continue
            if zh_len(para) > para_limit:
                long_para.append(zh_len(para))
            for s in re.split(r"[。！？!?；;]", para):
                if zh_len(s) > 60:
                    long_sent.append(s.strip()[:25])
        if long_sent:
            rep.warn(name, f"{len(long_sent)} 句超 60 字，首句：{long_sent[0]}…")
        if long_para:
            rep.warn(name, f"{len(long_para)} 段超 {para_limit} 字（最长 {max(long_para)}）")

    # 6. 图表编号与来源
    fig_nums = FIG_RE.findall(full)
    if fig_nums and "资料来源" not in full:
        rep.err("图表", f"出现 {len(fig_nums)} 处图表编号，但全文无「资料来源」（TY-14）")
    if "资料来源" in full and not fig_nums:
        rep.warn("图表", "有「资料来源」但无图表编号，检查编号是否漏写（TY-04）")

    # 7. 待核实
    n_th = full.count("【待核实】")
    if n_th:
        rep.note("待核实", f"共 {n_th} 处【待核实】，交付前须告知用户逐条处理")

    # 8. 案例结尾是否泄底
    if "案例" in secs:
        tail = secs["案例"].strip()[-60:]
        for bad in ["因此应当", "由此可见", "所以企业必须", "综上，企业应"]:
            if bad in tail:
                rep.warn("案例", f"结尾出现结论式表述「{bad}」，应停在待决策点（TY-08）")

    return rep.dump(as_json)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
