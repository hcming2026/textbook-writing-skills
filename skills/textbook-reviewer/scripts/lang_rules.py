# -*- coding: utf-8 -*-
"""教材语言机械检测规则（A 级可判 / B 级须确认）。

供 check_draft.py（审校）与 lint_polish.py（润色）共用，避免两处各写一套而漂移。
本文件在多个 skill 的 scripts/ 下各存一份，内容必须逐字节一致（md5 唯一）。

## 分级

- **A 级**：格式可枚举、几乎无歧义的。命中即可判违规，报告里可直接写「违反 YY-xx」。
- **B 级**：语义上的强信号，但依赖上下文。必须给定位、原文和「要确认什么」，
  由人定判，**不得据此判稿件不合格**。

## 两条设计纪律

1. **宁可漏，不可误报。** 误报会稀释整份清单的可信度——作者一旦发现清单里
   混着不是问题的条目，就会连真问题一起忽略。所以每条规则都要过范文试金石：
   `docs/测试用例/T-03-本科版-u2-l3.md` 是成熟教材范文，在那里报出任何一条
   都算误报，必须收紧或删除该规则。

2. **报出必须给改法。** 只说「句子不通」等于没审——作者知道不通，但不知道
   往哪改。每条规则都要带 `fix` 字段。

## 依据

规则编号指向 `规范库/语言风格.md` §十一（YY-31 ~ YY-36）。
本文件只做「能不能机械命中」的判断，不做规则解释；判据以母本为准。
"""

import re

A = "A"
B = "B"

# ---------------------------------------------------------------- A 级

# (类型, 正则, 依据, 改法)
A_PATTERNS = [
    ("成分残缺",
     re.compile(r"通过[^。；！？]{0,40}[，,]\s*使"),
     "YY-31①",
     "「通过……使……」令全句失去主语：删「通过」或删「使」，二者留一。"),

    ("句式杂糅",
     re.compile(r"原因(?:是|在于)[^。；]{0,40}(?:造成的|所致)"),
     "YY-31③",
     "「原因是……造成的」把两种句式揉在一起：删「造成的」，或改成「导致……的原因是……」。"),

    ("句式杂糅",
     re.compile(r"本着[^。；]{0,20}为原则"),
     "YY-31③",
     "「本着……为原则」二选一：「本着……的原则」或「以……为原则」。"),

    ("句式杂糅",
     re.compile(r"靠的是[^。；]{0,20}(?:取得的|得来的)"),
     "YY-31③",
     "「靠的是……取得的」二选一：删「取得的」，或改「……是靠……取得的」。"),

    ("搭配不当",
     re.compile(r"(?:开展|推进)[^。；，]{0,10}(?:水平|程度)"),
     "YY-31②",
     "「开展／推进……水平」动宾不搭：改「提高……水平」，或把宾语换成「……工作」「……建设」。"),

    ("搭配不当",
     re.compile(r"进行[^。；，]{0,10}水平"),
     "YY-31②",
     "「进行……水平」动宾不搭：改「提高……水平」。"),

    ("搭配不当",
     re.compile(r"(?:提高|提升)[^。；，]{0,8}(?:机制|体制)"),
     "YY-31②",
     "「提高……机制／体制」动宾不搭：改「健全机制」「完善体制」。"),

    ("搭配不当",
     re.compile(r"加强[^。；，]{0,8}(?:水平|程度)"),
     "YY-31②",
     "「加强……水平」动宾不搭：改「提高……水平」，或「加强……建设」。"),

    ("搭配不当",
     re.compile(r"加大[^。；，]{0,8}质量"),
     "YY-31②",
     "「加大……质量」动宾不搭：改「提高质量」。"),

    ("数量表达",
     re.compile(r"(?:减少|降低|下降)了?[^。；]{0,6}[一两二三四五六七八九十百千\d]+\s*倍"),
     "YY-36①",
     "减少／降低不得用倍数，只能给百分比：「减少了 3 倍」改「减少了 75%」（GB/T 15835）。"),

    ("口语化",
     re.compile(r"说白了|这玩意儿|想当年|一抓一大把|没啥|咋办|咱"),
     "YY-35",
     "正文叙述段出现说话体：改回书面语。若确在案例对话内，须加引号并标明说话人。"),
]

# ---------------------------------------------------------------- B 级

# 推论边界：结论句带全称量词，而前提没有任何数量/条件限定
INFER = re.compile(r"因此|所以|可见|这说明|由此|因而|从而|结论是|这意味着")
QUANT = re.compile(r"所有|全部|任何|一律|无一|必然|一定"
                   r"|都(?=[必能会应须需可该是要])|均(?=[必能会应须需可该是要])")
LIMIT = re.compile(r"多数|部分|有些|一些|个别|少数|常常|通常|往往|一般|可能|或许|也许"
                   r"|在[^。；]{0,14}(?:下|时|中|前提)|若|如果|假如|前提|条件|边界"
                   r"|样本|个案|案例中|据[^。；]{0,10}(?:调查|统计|样本|测算)")

# 因果方向：正面结果被当作负面决策的原因
CAUSE = re.compile(r"(?:因为|由于)([^。；]{2,60}?)(?:，|,)?(?:所以|因此|因而|导致|致使)([^。；]{2,60})")
POS = re.compile(r"下降|降低|减少|提高|提升|改善|增长|上升|成功|完成|通过|达标|缩短")
NEG_DEC = re.compile(r"推迟|延后|暂缓|放弃|取消|终止|缩减|压缩|搁置|暂停|退出|砍掉")

# 指代：同句两个不同代词 / 顿号并列后又用代词
PRON_ITS = re.compile(r"它")
PRON_ITS_OTHER = re.compile(r"其(?![中实余次他尤间后一])")
PRON_DEM = re.compile(r"该(?:项|个|种|套|方案|系统|模块|方法|部分)")
LISTED = re.compile(r"[^，。；、]{2,}、")

# 段落过滤：标题、表格、引用、编号项、列表项、图稿元数据
SKIP = re.compile(r"^\s*(#{1,6}|[|>]|\d+[\.、)]\s|[-*+]\s|\*\*-|\*\*【[图表])")


def split_sents(text):
    """按句末标点切句，保留中文逗号层级（分号算句末：教材分号两侧常是独立分句）。"""
    out, buf = [], ""
    for ch in text:
        buf += ch
        if ch in "。！？!?；;":
            if buf.strip():
                out.append(buf.strip())
            buf = ""
    if buf.strip():
        out.append(buf.strip())
    return out


def iter_paragraphs(lines):
    """产出 (起始行号, 段落文本)。空行分段，跳过非正文块。"""
    paras, buf, start = [], [], None
    for i, ln in enumerate(lines, 1):
        if not ln.strip():
            if buf:
                paras.append((start, "\n".join(buf)))
                buf, start = [], None
            continue
        if SKIP.match(ln):
            if buf:
                paras.append((start, "\n".join(buf)))
                buf, start = [], None
            continue
        if start is None:
            start = i
        buf.append(ln.strip())
    if buf:
        paras.append((start, "\n".join(buf)))
    return paras


def _rec(grade, kind, lineno, sent, rule, fix, why=""):
    return {"等级": grade, "类型": kind, "行": lineno, "原文": sent.strip()[:48],
            "依据": rule, "改法": fix, "判据": why}


def _detect_leap(prev, sent, lineno):
    if not INFER.search(sent) or not QUANT.search(sent):
        return None
    if LIMIT.search(sent) or LIMIT.search(prev):
        return None
    q = QUANT.search(sent).group(0)
    return _rec(B, "推论可能越界", lineno, sent, "YY-34①",
                "把全称收回到前提支持的范围内（如「部分企业」「在数据密集型行业」），"
                "或补一句说明前提为何能覆盖全部情形。",
                f"结论用「{q}」覆盖全部，但作为前提的上文没有数量或条件限定")


def _detect_causal(sent, lineno):
    m = CAUSE.search(sent)
    if not m:
        return None
    head, body = m.group(1), m.group(2)
    if POS.search(head) and NEG_DEC.search(body):
        return _rec(B, "因果方向待核", lineno, sent, "YY-33①",
                    "核对时序与因果方向：正面结果通常不会引出收缩性决策。"
                    "若确有此因果，须补出中间机制。",
                    "因句是正面结果（" + POS.search(head).group(0) +
                    "），果句却是收缩性决策（" + NEG_DEC.search(body).group(0) + "）")
    return None


def _detect_pronoun(sent, lineno):
    its = [m.start() for m in PRON_ITS.finditer(sent)]
    other = ([m.start() for m in PRON_ITS_OTHER.finditer(sent)]
             + [m.start() for m in PRON_DEM.finditer(sent)])
    if its and other:
        return _rec(B, "指代待核", lineno, sent, "YY-32",
                    "把其中一个代词换回名词。跨段回指一律用名词，不用代词。",
                    "同句出现「它」与「其／该」，两个回指对象须确认是否同一")
    # 顿号并列 + 代词：代词必须出现在**并列项之后**才构成歧义。
    # 反例（范文实测）：「系统运行越久，围绕它的自建表格、手工补丁、口头约定就越多」——
    # 「它」在并列项之前，回指「系统」唯一明确，不该报。原写法只数顿号个数，
    # 不比较位置，会把这类句子误判为歧义。
    listed = [m.end() for m in LISTED.finditer(sent)]
    if len(listed) >= 2 and (its or other):
        tail = listed[-1]
        if any(p > tail for p in its + other):
            return _rec(B, "指代待核", lineno, sent, "YY-32",
                        "换回名词，指明指的是并列项中的哪一个。",
                        "顿号并列了多个对象，其后又用代词，回指不唯一")
    return None


def scan(lines):
    """扫描稿件各行，返回记录列表。每项含 等级/类型/行/原文/依据/改法/判据。"""
    out = []
    for start, para in iter_paragraphs(lines):
        sents = split_sents(para)
        prev = ""
        for s in sents:
            for kind, pat, rule, fix in A_PATTERNS:
                if pat.search(s):
                    out.append(_rec(A, kind, start, s, rule, fix))
            for det in (_detect_pronoun(s, start),
                        _detect_causal(s, start),
                        _detect_leap(prev, s, start)):
                if det:
                    out.append(det)
            prev = s
    # 同一句可能被 A 级多条命中（如搭配+杂糅），去重键取 类型+原文
    seen, uniq = set(), []
    for r in out:
        k = (r["类型"], r["原文"], r["等级"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)
    return uniq


def summarize(recs):
    """按等级与类型汇总，供各脚本按自己的格式输出。"""
    a = [r for r in recs if r["等级"] == A]
    b = [r for r in recs if r["等级"] == B]
    by_kind = {}
    for r in a + b:
        by_kind.setdefault((r["等级"], r["类型"]), []).append(r)
    return a, b, by_kind
