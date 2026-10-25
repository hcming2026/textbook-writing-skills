#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lint_polish.py — 教材语言润色定位扫描（textbook-polish / 执行步骤 2）

给**位置**，不给分数。output 的每一条都带行号，直接抄进修改说明清单的「位置」列。

用法：
    python <SKILL_DIR>/scripts/lint_polish.py <稿件.md>
    python <SKILL_DIR>/scripts/lint_polish.py <稿件.md> --paradigm chapter
    python <SKILL_DIR>/scripts/lint_polish.py <稿件.md> --mata      # 只列元叙述候选
    python <SKILL_DIR>/scripts/lint_polish.py <稿件.md> --json

两组指标，**不得混用**：
  合规组  超 60 字句、段超限、禁用词、数字空格分节 —— 依据 规范库，命中即须处理
  诊断组  元叙述候选 —— 只作线索，甲类乙类必须人工判（见 references/元叙述.md）

量纲：句长段长按**汉字数**（TY-18），断句含分号。与「含标点字符数」不是一个口径，
不要拿本脚本的数去比 references/语言风格.md 里的实测均值 49 字（那是含标点口径）。

退出码：0 正常；2 用法或文件错误。
"""

import sys
import re
import json
from pathlib import Path

# 与 规范库/语言风格.md §六 禁用词表一致。母本改了这里要跟着改。
BANNED = ["赋能", "抓手", "闭环", "生态位", "打法", "组合拳",
          "显然", "众所周知", "不难看出", "毋庸置疑",
          "一定", "必然", "绝对", "百分之百",
          "让我们一起来学习", "本章将带你走进"]
JUMP = ["研究表明", "大量研究表明", "许多研究表明", "专家认为", "业内人士指出", "有观点认为"]

ZH = re.compile(r"[\u4e00-\u9fa5]")
SENT_END = re.compile(r"[。！？!?；;]")
# 章末块：不并入最后一节，否则末节字数与段长被抬高（与 check_draft.py 同一规则）
CHAPTER_TAIL = re.compile(
    r"^\s{0,3}(?:#{1,6}\s*)?(?:本章小结|小结|内容提要|本章提要|本章重点|关键术语|术语表|"
    r"参考文献|复习与思考|思考题|习题|延伸阅读)\s*$")
CHAPTER_SEP = re.compile(r"^\s{0,3}(?:#{1,6}\s*)?(\d+)\.(\d+)[　 \t]+\S")
CHAPTER_SUB = re.compile(r"^\s{0,3}(?:#{1,6}\s*)?\d+\.\d+\.\d+[　 \t]+\S")
MATA_SUBJ = re.compile(r"本书|本章|本节|本教程|本教材|教材|我们")
MATA_VERB = re.compile(r"介绍|讨论|分为|展开|安排|带领|阐述|讲述|涵盖|给出|处理")
# 非正文段落：标题、表格行、引用、编号项、列表项、图稿元数据。
# `[-*+]\s` 与 `\*\*-` 必须带后随字符——不加的话 `**（4）环4……**` 这种加粗正文段
# 会被当成列表项跳过，加粗引导段里的超长句就全漏了（与 check_draft.py 同一规则）。
SKIP_PARA = re.compile(r"^\s*(#{1,6}\s|[|>]|\d+[\.、)]\s|[-*+]\s|\*\*-|\*\*【[图表])")


def zh_len(t):
    return len(ZH.findall(t))


def paragraphs_with_lineno(lines):
    """按空行切段，返回 [(起始行号, 段落文本)]。行号 1 基，便于作者在 Word 里找。"""
    out, buf, start = [], [], 0
    for i, ln in enumerate(lines, 1):
        if ln.strip() == "":
            if buf:
                out.append((start, "\n".join(buf)))
                buf = []
            continue
        if not buf:
            start = i
        buf.append(ln)
    if buf:
        out.append((start, "\n".join(buf)))
    return out


def scan(lines, paradigm, level):
    limit = 180 if level == "MBA" else 200
    long_sent, long_para, banned, numsplit, mata, protected_hits = [], [], [], [], [], []
    cur_sec, in_tail = "(章首)", False

    # 保护块的行号：图稿制图说明、案例说明框元数据、图表题注、编号列表。
    # 这些是给美编的指令或体例成分，不是正文——里面的禁用词不算合规问题，
    # 但也不能静默丢掉，单列成「保护块内提示」，交作者决定。
    protected = set()
    for lineno, para in paragraphs_with_lineno(lines):
        if SKIP_PARA.match(para.strip()):
            for k in range(lineno, lineno + para.count("\n") + 1):
                protected.add(k)

    for i, ln in enumerate(lines, 1):
        if paradigm == "chapter" and CHAPTER_TAIL.match(ln):
            in_tail = True
            continue
        m = CHAPTER_SEP.match(ln) and not CHAPTER_SUB.match(ln)
        if paradigm == "chapter" and m:
            in_tail = False
            cur_sec = ln.strip().lstrip("#").strip()
        for w in BANNED + JUMP:
            n = ln.count(w)
            if n:
                rec = {"行": i, "节": cur_sec, "词": w, "次": n, "原文": ln.strip()[:40]}
                (protected_hits if i in protected else banned).append(rec)
        for mm in re.finditer(r"(?<![\d,.])\d{1,3}(?: \d{3})+(?![\d])", ln):
            numsplit.append({"行": i, "节": cur_sec, "原文": mm.group(0)})

    for lineno, para in paragraphs_with_lineno(lines):
        if SKIP_PARA.match(para.strip()):
            continue
        n = zh_len(para)
        if n > limit:
            long_para.append({"行": lineno, "节": cur_sec, "字数": n, "原文": para.strip()[:40]})
        for s in SENT_END.split(para):
            m2 = zh_len(s)
            if m2 > 60:
                long_sent.append({"行": lineno, "节": cur_sec, "字数": m2, "原文": s.strip()[:30]})
            st = s.strip()
            if st and MATA_SUBJ.search(st) and MATA_VERB.search(st) and zh_len(st) <= 80:
                mata.append({"行": lineno, "节": cur_sec, "原文": st[:50]})

    return {
        "范式": "章节制" if paradigm == "chapter" else "单元制",
        "学段": level,
        "段限": limit,
        "合规": {
            "超60字句": len(long_sent),
            "最长句": max([d["字数"] for d in long_sent], default=0),
            "超80字句": sum(1 for d in long_sent if d["字数"] > 80),
            "段超限": len(long_para),
            "最长段": max([d["字数"] for d in long_para], default=0),
            "禁用词": sum(d["次"] for d in banned),
            "数字空格分节": len(numsplit),
            "_超长句明细": long_sent,
            "_超长段明细": long_para,
            "_禁用词明细": banned,
            "_数字分节明细": numsplit,
            "_保护块提示": protected_hits,
        },
        "诊断": {"元叙述候选": len(mata), "_元叙述明细": mata},
    }


def report(r, top=8):
    L = ["=" * 62, "教材语言润色 · 定位扫描", "=" * 62,
         f"范式 {r['范式']}　学段 {r['学段']}　段限 {r['段限']} 字（按汉字数，TY-18）", ""]
    c = r["合规"]
    L.append("【合规组】依据 规范库，命中须处理或写明不改的理由")
    L.append(f"  超 60 字句      {c['超60字句']:>3} 句（最长 {c['最长句']} 字；其中超 80 字 {c['超80字句']} 句）  ← YY-03")
    for d in c["_超长句明细"][:top]:
        L.append(f"      行 {d['行']:<5}{d['字数']:>3} 字  {d['原文']}…")
    L.append(f"  段超 {r['段限']} 字     {c['段超限']:>3} 段（最长 {c['最长段']} 字）  ← YY-02")
    for d in c["_超长段明细"][:top]:
        L.append(f"      行 {d['行']:<5}{d['字数']:>3} 字  {d['原文']}…")
    L.append(f"  禁用词 / 模糊归因 {c['禁用词']:>3} 处  ← 语言风格 六、YY-11（命中即处理，不得以「实义」豁免）")
    for d in c["_禁用词明细"][:top]:
        L.append(f"      行 {d['行']:<5}{d['词']}  {d['原文']}")
    if c["数字空格分节"]:
        L.append(f"  数字空格分节    {c['数字空格分节']:>3} 处  ← YY-21")
        for d in c["_数字分节明细"][:3]:
            L.append(f"      行 {d['行']:<5}{d['原文']}")
    if c["_保护块提示"]:
        L.append(f"  保护块内命中    {len(c['_保护块提示']):>3} 处（图稿说明/说明框元数据，不属正文，交作者定）")
        for d in c["_保护块提示"][:3]:
            L.append(f"      行 {d['行']:<5}{d['词']}×{d['次']}  {d['原文']}")
    L.append("")
    d = r["诊断"]
    L.append("【诊断组】只作线索，不得用于判定稿件不合格")
    L.append(f"  元叙述候选      {d['元叙述候选']:>3} 处  ← 甲类删主语 / 乙类保留，必须人工判（references/元叙述.md）")
    for x in d["_元叙述明细"][:top]:
        L.append(f"      行 {x['行']:<5}{x['原文']}")
    L.append("")
    L.append("-" * 62)
    L.append("下一步：超长句逐条判「该断还是该留」；禁用词逐条处理或写明不改理由；")
    L.append("元叙述候选逐条标甲/乙。改完重跑本脚本，合规组数值只降不升。")
    return "\n".join(L)


def main(argv):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0
    as_json = "--json" in argv
    only_mata = "--mata" in argv
    paradigm = "chapter" if "--paradigm" in argv and "chapter" in argv else "unit"
    level = "MBA" if "MBA" in argv else "本科高年级"
    args = [a for a in argv[1:] if not a.startswith("--") and a not in ("chapter", "unit", "MBA")]
    if not args:
        print("用法：python lint_polish.py <稿件.md> [--paradigm chapter] [--json] [--mata]")
        return 2
    p = Path(args[0])
    if not p.is_file():
        print(f"文件不存在：{p}")
        return 2

    lines = p.read_text(encoding="utf-8").splitlines()
    # frontmatter 里的 level / paradigm 优先于命令行
    if lines and lines[0].strip() == "---":
        for ln in lines[1:30]:
            if ln.strip() == "---":
                break
            if ":" in ln:
                k, v = ln.split(":", 1)
                if k.strip() == "level" and v.strip():
                    level = v.strip()
                if k.strip() == "paradigm" and v.strip().startswith(("章节", "chapter")):
                    paradigm = "chapter"

    r = scan(lines, paradigm, level)
    if as_json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0
    if only_mata:
        for x in r["诊断"]["_元叙述明细"]:
            print(f"行 {x['行']}\t{x['原文']}")
        return 0
    print(report(r))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
