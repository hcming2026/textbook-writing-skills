#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_draft.py — 教材稿件事实性检查（unit-writer / textbook-reviewer 共用）

用法：
    python <SKILL_DIR>/scripts/check_draft.py <稿件.md> [--json]

只查「能用规则判定」的项：六栏齐全与顺序、各栏字数区间、练习三层、
题目是否挂 LO、禁用词、跳跃推理词、句长段长、图表编号与来源、待核实标注。
不做质量评分——分数由 textbook-reviewer 依 审校标准.md 给出。

退出码：0 = 无 ERROR；1 = 存在 ERROR（不得交付）。

注意：本脚本在 unit-writer / textbook-reviewer / textbook-formatter 三处各有一份副本，
必须完全同源。改动后复制到另外两份，否则同一稿件在不同环节会得出不同结论。
"""

import re
import sys
import json
from pathlib import Path

# 学段参数：必须与 规范库/学段适配.md 及 体例规范.md TY-11 一致。
# 改规则时同步本表，并跑 python tools/consistency_check.py 校验两边是否对得上。
LEVEL_PARAMS = {
    "本科高年级": {"导语": (150, 250), "正文": (3000, 4500), "案例": (800, 1200), "拓展": (100, 200),
                   "练习比例": (5, 3, 2), "段限": 200},
    "MBA": {"导语": (200, 350), "正文": (2500, 3500), "案例": (1200, 2000), "拓展": (100, 200),
            "练习比例": (4, 3, 3), "段限": 180},
}
SECTIONS = ["导语", "正文", "案例", "思考", "练习", "拓展"]

# 章节制参数：见 规范库/体例规范.md §零.2 与 学段适配.md §二·附。
# 章节制下没有「六栏」，章是交付单位，节只是正文内部的标题层级。
# 量纲：正文按**汉字数**（TY-18）。该书「2.3 万字」是字符口径，折汉字 14,041，
# 拿字符数来比这里的 9000–15000 会把合格章判成一半容量。
CHAPTER_PARAMS = {
    "本科高年级": {"正文": (9000, 15000), "案例": (1500, 2500), "段限": 200, "节数": (6, 8)},
    "MBA": {"正文": (9000, 15000), "案例": (1500, 2500), "段限": 180, "节数": (5, 8)},
}
# 章级必备模块：章情境（TY-05）、章末三件套（TY-16）、术语表（TY-17）、参考文献（TY-19）
CHAPTER_MODULES = [
    ("章情境", ["情境", "引导段", "本章情境"], "TY-05：每章首节之前必须有 ≤400 字的引导段"),
    ("本章小结", ["本章小结", "小结", "内容提要"], "TY-16①：章末须有本章内容提要"),
    ("本章重点", ["本章重点", "重点"], "TY-16②：章末须有 3–5 条重点"),
    ("复习与思考", ["复习", "思考题", "习题", "讨论题"], "TY-16③：章末须有 ≥5 题"),
    ("关键术语", ["术语表", "关键术语"], "TY-17：章末须列 5–12 个关键术语"),
    ("参考文献", ["参考文献"], "TY-19：章末须列 ≥6 条参考文献"),
]
CHAPTER_SEP = re.compile(r"^\s{0,3}(?:#{1,6}\s*)?(\d+)\.(\d+)[　 \t]+\S")
CHAPTER_SUB = re.compile(r"^\s{0,3}(?:#{1,6}\s*)?\d+\.\d+\.\d+[　 \t]+\S")
FIG2_RE = re.compile(r"(图|表)\s*\d+\s*[-‑–—]\s*\d+")
# 章末块的独立标题行。不单独摘出来，它们会被并进最后一个「节」，
# 把那一节的段长、句长、字数全部抬高，误报成「末节异常」。
CHAPTER_TAIL = re.compile(
    r"^\s{0,3}(?:#{1,6}\s*)?(?:本章小结|小结|内容提要|本章提要|本章重点|关键术语|术语表|"
    r"参考文献|复习与思考|思考题|习题|延伸阅读)\s*$")


BANNED = ["赋能", "抓手", "闭环", "生态位", "打法", "组合拳", "让我们一起来学习",
          "本章将带你走进", "毋庸置疑"]
JUMP = ["显然", "众所周知", "不难看出"]

# 病句候选格式（YY-31/35/36）。**只用于出候选行号，不得判违规。**
# 收录标准是「高精度、低覆盖」：宁可漏，不可误报。四类病句里只有两类、
# 六个格式能写成正则，覆盖不到 YY-31 全貌，更完全查不了 YY-32（指代）、
# YY-33（因果）、YY-34（推论越界）——那三项一个字都不报，不代表没有。
# 把候选当违规报，会让作者以为「查过了」，假阴性比不查更危险（审校标准 §三 注）。
SICK_PATTERNS = [
    ("成分残缺", r"通过[^。；！？\n]{0,40}[，,]\s*使", "YY-31①"),
    ("句式杂糅", r"原因(?:是|在于)[^。；\n]{0,40}(?:造成的|所致)", "YY-31③"),
    ("句式杂糅", r"本着[^。；\n]{0,20}为原则", "YY-31③"),
    ("句式杂糅", r"靠的是[^。；\n]{0,20}(?:取得的|得来的)", "YY-31③"),
    ("搭配不当", r"开展[^。；\n]{0,12}(?:水平|程度)", "YY-31②"),
    ("搭配不当", r"提高[^。；\n]{0,10}(?:机制|体制)", "YY-31②"),
    ("数量表达", r"(?:减少|降低|下降)了?[^。；\n]{0,6}[一两二三四五六七八九十百\d]+\s*倍", "YY-36①"),
    # 只收高置信度口语词。含「啥」「搞」的一律不收——「搞清楚」「啥时候」在两可之间，
    # 误报会稀释整份候选清单的可信度。案例对话里的口语属合法，需人工看边界。
    ("口语化", r"说白了|这玩意儿|想当年|一抓一大把|没啥", "YY-35"),
]
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


def parse_chapter(lines, start):
    """章节制：按 `x.y 节标题` 切块，返回 (secs, order, preface, tail)。

    secs 的键是节标题、值是节的正文。**这一步是章节制下语言检查能跑起来的前提**：
    下游的禁用词、跳跃词、句长、段长全部只遍历 secs，
    secs 为空则这些检查一条都不执行——章节稿直喂本脚本时「0 条语言问题」就是这么来的。

    preface 是章首到第一节之间的内容（用于判 TY-05 章情境）；
    tail 是章末块（小结 / 重点 / 术语 / 参考文献），独立出来以免并进最后一节。
    """
    secs, order, cur, buf, preface, tail = {}, [], None, [], [], []
    in_tail = False
    for i in range(start, len(lines)):
        line = lines[i]
        if CHAPTER_TAIL.match(line):
            if cur:
                secs[cur] = "\n".join(buf)
            cur, buf, in_tail = None, [], True
            continue
        if CHAPTER_SEP.match(line) and not CHAPTER_SUB.match(line):
            if cur:
                secs[cur] = "\n".join(buf)
            cur = re.sub(r"^\s*#+\s*", "", line).strip()
            order.append(cur)
            buf, in_tail = [], False
            continue
        if CHAPTER_SUB.match(line):
            continue                      # 小节标题丢弃，内容归所属节
        (tail if in_tail else (buf if cur else preface)).append(line)
    if cur:
        secs[cur] = "\n".join(buf)
    return secs, order, "\n".join(preface), "\n".join(tail)


def main(argv):
    as_json = "--json" in argv
    # 范式：命令行 --paradigm chapter|章节制 优先，其次看 frontmatter 的 paradigm 字段。
    # 默认单元制——老稿件行为零变更。
    paradigm = "单元制"
    rest = argv[1:]
    if "--paradigm" in rest:
        i = rest.index("--paradigm")
        val = rest[i + 1] if i + 1 < len(rest) else ""
        paradigm = "章节制" if val.lower() in ("chapter", "章节制", "章节") else "单元制"
        rest = rest[:i] + rest[i + 2:]
    args = [a for a in rest if not a.startswith("--")]
    if not args:
        print("用法：python check_draft.py <稿件.md> [--json] [--paradigm chapter]")
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
    if str(fm.get("paradigm", "")).startswith(("章节", "chapter")):
        paradigm = "章节制"
    level = fm.get("level", "").strip()
    if level and level not in LEVEL_PARAMS:
        rep.err("frontmatter", f"level 只能为「本科高年级」或「MBA」，实为「{level}」")

    if paradigm == "章节制":
        P = CHAPTER_PARAMS.get(level, CHAPTER_PARAMS["本科高年级"])
        need = ["course", "unit", "title", "level"]
    else:
        P = LEVEL_PARAMS.get(level, LEVEL_PARAMS["MBA"])
        need = ["course", "unit", "lesson", "title", "level", "lo"]
    for k in need:
        if not fm.get(k):
            rep.err("frontmatter", f"缺少字段 `{k}`")
    if fm.get("lo") and not LO_RE.search(str(fm["lo"])):
        rep.err("frontmatter", "`lo` 字段未给出合法的 LO 编号")
    if paradigm == "章节制" and not fm.get("lo"):
        rep.note("frontmatter", "章节制未挂 LO——多为章首一组动词式学习目标，不按课挂载（学段适配 §二·附）")

    preface = tail = ""
    if paradigm == "章节制":
        secs, order, preface, tail = parse_chapter(lines, start)
    else:
        secs, order = parse_sections(lines, start)

    # 1. 结构
    if paradigm == "单元制":
        if order != SECTIONS:
            missing = [s for s in SECTIONS if s not in order]
            extra = [s for s in order if s not in SECTIONS]
            if missing: rep.err("结构", f"缺少栏目：{'、'.join(missing)}")
            if extra: rep.err("结构", f"出现未定义的栏目：{'、'.join(extra)}")
            if not missing and not extra: rep.err("结构", f"栏目顺序应为 {' → '.join(SECTIONS)}，实为 {' → '.join(order)}")
    else:
        # 章节制：六栏上提到章层，改查节数与章级模块（体例规范 §零.3）
        if len(order) < 4:
            rep.err("结构", f"章节制只识别到 {len(order)} 个 x.y 节（应形如「1.1　标题」）；"
                            f"若这是单元制稿，去掉 --paradigm chapter")
        else:
            lo_n, hi_n = P["节数"]
            if not (lo_n <= len(order) <= hi_n):
                rep.warn("结构", f"{len(order)} 节，章节制建议 {lo_n}–{hi_n} 节（学段适配 §二·附）")
        whole = preface + "\n" + "\n".join(secs.values()) + "\n" + tail
        for label, keys, rule in CHAPTER_MODULES:
            if not any(k in whole for k in keys):
                rep.err("结构", f"缺少章级模块「{label}」——{rule}")
        n_pre = zh_len(preface)
        if n_pre == 0:
            rep.err("结构", "章首无内容：TY-05 要求第一节之前有 ≤400 字引导段（章情境）")
        elif n_pre > 500:
            rep.warn("结构", f"章首引导段 {n_pre} 字，TY-05 要求 ≤400 字")

    # 2. 字数
    if paradigm == "单元制":
        for s in ["导语", "正文", "案例", "拓展"]:
            if s not in secs: continue
            n = zh_len(secs[s])
            lo, hi = P[s]
            if n < lo * 0.8 or n > hi * 1.2:
                rep.err(s, f"{n} 字，超出区间 {lo}–{hi}（容差 ±20%）")
            elif n < lo or n > hi:
                rep.warn(s, f"{n} 字，略超出区间 {lo}–{hi}")
    else:
        n = sum(zh_len(v) for v in secs.values())
        lo, hi = P["正文"]
        if n < lo * 0.8 or n > hi * 1.2:
            rep.err("正文字数", f"{n} 字，超出章级区间 {lo}–{hi}（容差 ±20%）")
        elif n < lo or n > hi:
            rep.warn("正文字数", f"{n} 字，略超出章级区间 {lo}–{hi}")

    # 3. 练习分层（单元制查三层比例；章节制查章末习题是否可评分）
    if paradigm == "单元制" and "练习" in secs:
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

    elif paradigm == "章节制":
        qs = [l for l in tail.splitlines()
              if re.match(r"^\s*(?:\d+[\.、)]|[（(]\d+[)）]|[①②③④⑤⑥⑦⑧⑨⑩])", l)]
        if not qs:
            rep.warn("练习", "章末未识别到编号习题：章节制按五类分法，无法核三层比例（见 练习设计.md）")
        else:
            vague = [q for q in qs if VAGUE_RE.search(q)]
            if vague:
                rep.err("练习", f"{len(vague)} 道题为不可评分题（LX-07），首条：{vague[0][:30]}…")

    # 4. 禁用词与跳跃词
    # preface/tail 也要算进去：章节制的章情境与章末习题在 secs 之外，
    # 只用 secs 会漏掉章首章末的禁用词。
    full = "\n".join(list(secs.values()) + [preface, tail])
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

    # 4c. 病句候选（诊断组，YY-31 / YY-35 / YY-36）
    # 只报行号，不判违规，走 INFO 级：不进 WARN 计数，不影响退出码。
    # 理由见 SICK_PATTERNS 上方注释与审校标准 §三 注。
    hits = {}
    for idx in range(start, len(lines)):
        s = lines[idx].strip()
        if not s or re.match(r"^\s*(#{1,6}|[|>]|\d+[\.、)]\s|[-*+]\s)", s):
            continue
        for label, pat, rule in SICK_PATTERNS:
            if re.search(pat, s):
                hits.setdefault((label, rule), []).append((idx + 1, s[:30]))
    for (label, rule), recs in hits.items():
        head = "；".join(f"行{r}：{t}…" for r, t in recs[:3])
        more = f"（仅列前 3 处，共 {len(recs)} 处）" if len(recs) > 3 else ""
        rep.note("病句候选", f"{label} {len(recs)} 处{more} [{rule}] 诊断组，"
                             f"须人工定判、不判不合格 —— {head}")

    # 5. 句长与段长
    para_limit = P["段限"]
    # 章节制的章首（情境、学习目标）与章末（小结、习题）不在 secs 里，
    # 但它们也是正文性质的散文，漏掉会少数超长句——实测差 1 句。
    scan_secs = dict(secs)
    if paradigm == "章节制":
        if preface.strip():
            scan_secs = dict([("章首（情境/学习目标）", preface)] + list(scan_secs.items()))
        if tail.strip():
            scan_secs["章末（小结/习题）"] = tail
    for name, body in scan_secs.items():
        long_sent, long_para = [], []
        for para in [p for p in body.split("\n\n") if p.strip()]:
            # 跳过非正文段落：标题、表格行、引用、编号项、列表项、图稿元数据。
            # 注意 `[-*+]\s` 与 `\*\*-` 必须带后随字符：原写法 `[-*+]` 会把
            # `**（4）环4　行动回到数据**` 这类**加粗正文段**也当成列表项跳过，
            # 导致加粗引导段里的超长句一律漏报（实测第 1 章漏 2 句、润色稿漏 1 句）。
            if re.match(r"^\s*(#{1,6}|[|>]|\d+[\.、)]|[-*+]\s|\*\*-)", para.strip()):
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
    if paradigm == "章节制":
        fig_nums = FIG2_RE.findall(full)
        three = FIG_RE.findall(full)
        if fig_nums and three:
            rep.err("图表", f"两段式（图 1-1）与三段式（图 1.1.1）混用：三段式 {len(three)} 处。"
                            f"章节制须全册统一为两段式（TY-04 见 §零.2）")
    else:
        fig_nums = FIG_RE.findall(full)
        two = FIG2_RE.findall(full)
        if fig_nums and two:
            rep.err("图表", f"三段式与两段式混用：两段式 {len(two)} 处。单元制须统一为三段式（TY-04）")
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
        case_tail = secs["案例"].strip()[-60:]
        for bad in ["因此应当", "由此可见", "所以企业必须", "综上，企业应"]:
            if bad in case_tail:
                rep.warn("案例", f"结尾出现结论式表述「{bad}」，应停在待决策点（TY-08）")

    return rep.dump(as_json)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
