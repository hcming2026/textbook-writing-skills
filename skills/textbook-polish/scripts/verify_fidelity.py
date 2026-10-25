#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_fidelity.py — 保真核对（textbook-polish / 执行步骤 7）

比对原文与改文，只列差异、不下判决。它替代不了人工，但能把
「改完自己觉得没丢东西」变成「逐项可查」。

用法：
    python <SKILL_DIR>/scripts/verify_fidelity.py 原文.md 改文.md
    python <SKILL_DIR>/scripts/verify_fidelity.py 原文.md 改文.md --json

查两类，共十一项：
  内容六项  数字与百分比、否定、限定与条件、引文与术语、因果连接、结构规模
  格式五项  上标注码、图表编号、不换行连字符、占位符块、表格行数
            —— 格式项最容易在润色中被顺手「修好」而没人发现，
               印出来才发现图号连不上、上标丢了。本项为新增，v1.2.0 之前没有。

退出码：0 = 无高优先级差异；1 = 存在高优先级差异（出稿前必须逐条确认去向）。
"""

import sys
import re
import json
from pathlib import Path

NUM = re.compile(r"\d+(?:\.\d+)?\s*(?:%|％|万|亿|千|百)?|百分之[一二三四五六七八九十百零]+")
NEG = ["不", "未", "无", "非", "没", "避免", "禁止", "切忌", "绝不", "难以"]
QUAL = ["可能", "也许", "大概", "约", "仅", "只", "至少", "至多", "不超过", "以上", "以下",
        "前提", "若", "除非", "一般", "通常", "部分", "大多", "主要", "限于"]
CAUSAL = ["因此", "所以", "由于", "导致", "从而", "进而", "使得", "以致", "结果是"]
QUOTED = re.compile(r"“([^”]{1,40})”|「([^」]{1,40})」|《([^》]{1,30})》|`([^`]{1,40})`|([A-Z]{2,}[A-Za-z]*)")
SUP = re.compile(r"\^\\?\[[^\]]+\\?\]\^")
FIG3 = re.compile(r"(图|表)\s*\d+\.\d+\.\d+")
FIG2 = re.compile(r"(图|表)\s*\d+\s*[-‑–—]\s*\d+")
NBH = "\u2011"          # 不换行连字符：图 1‑1 里的那个，Word 回填最易丢
PLACEHOLDER = re.compile(r"【待补】|\[待补\]|【待核实】|\[TBD\]|XXX")


def body(raw):
    return re.sub(r"^\s{0,3}#{1,6}\s.*$", "", raw, flags=re.M)


def paras(raw):
    t = body(raw)
    return [p.strip() for p in re.split(r"\n\s*\n|\n", t) if p.strip()]


def profile(raw):
    b = body(raw)
    nums = {}
    for n in NUM.findall(b):
        n = n.strip()
        nums[n] = nums.get(n, 0) + 1
    quoted = {}
    for m in QUOTED.finditer(b):
        for g in m.groups():
            if g:
                g = g.strip()
                quoted[g] = quoted.get(g, 0) + 1
    return {
        "字数(汉字)": len(re.findall(r"[\u4e00-\u9fa5]", b)),
        "段落数": len(paras(raw)),
        "数字": nums,
        "否定": {w: b.count(w) for w in NEG},
        "限定": {w: b.count(w) for w in QUAL},
        "引文": quoted,
        "因果": {w: b.count(w) for w in CAUSAL},
        "上标": len(SUP.findall(raw)),
        "图号三段": sorted(set(FIG3.findall(raw))),
        "图号两段": sorted(set(FIG2.findall(raw))),
        "不换行连字符": raw.count(NBH),
        "占位符": len(PLACEHOLDER.findall(raw)),
        "表格行": len([l for l in raw.split("\n") if l.strip().startswith("|")]),
    }


def compare(a, b):
    out = []

    def dec(key, sev, label, note=""):
        miss = {k: a[key][k] - b[key].get(k, 0) for k in a[key]}
        miss = {k: v for k, v in miss.items() if v > 0}
        if miss:
            out.append({"项": label, "级别": sev,
                        "原文": sum(a[key].values()), "改文": sum(b[key].values()),
                        "变化": "、".join(f"{k}×{v}" for k, v in sorted(miss.items(), key=lambda t: -t[1])[:8]),
                        "说明": note or "该项在改文中减少"})

    def scalar(key, sev, label, note="", human=False):
        if a[key] != b[key]:
            d = b[key] - a[key]
            out.append({"项": label, "级别": sev, "原文": a[key], "改文": b[key],
                        "变化": (f"{d:+d}" + (" 字" if human else "")), "说明": note})

    dec("数字", "高", "数字/百分比", "数字变了就是事实变了，逐条确认")
    dec("否定", "高", "否定词", "否定丢失会使主张反向")
    dec("限定", "中", "限定与条件", "合句时易把条件从句一并删掉")
    dec("引文", "高", "引文/书名/术语原文")
    dec("因果", "低", "因果连接")
    scalar("段落数", "中", "段落数", "确认是否符合预期，不按字数硬拆")
    scalar("字数(汉字)", "低", "字数", "按汉字数计（TY-18）；与字符数不是一个口径", human=True)

    # 格式保全：润色最容易在这里出事，且出事后不报错
    for k, label in (("上标", "上标注码"), ("不换行连字符", "不换行连字符"),
                     ("占位符", "占位符块"), ("表格行", "表格行数")):
        scalar(k, "高", label, "格式项：丢了不会报错，印出来才发现")
    for k, label in (("图号三段", "图表编号（三段式）"), ("图号两段", "图表编号（两段式）")):
        lost = set(a[k]) - set(b[k])
        added = set(b[k]) - set(a[k])
        if lost or added:
            out.append({"项": label, "级别": "高", "原文": len(a[k]), "改文": len(b[k]),
                        "变化": ("缺 " + "、".join(sorted(lost)) if lost else "") +
                                ("　" if lost and added else "") +
                                ("增 " + "、".join(sorted(added)) if added else ""),
                        "说明": "编号缺失/新增都要报，编号是跨章引用的锚点"})
    return out


def report(issues, a, b):
    L = ["=" * 62, "保真核对 · 差异清单（不下判决，逐条人工确认）", "=" * 62,
         f"字数(汉字) {a['字数(汉字)']} → {b['字数(汉字)']}　段数 {a['段落数']} → {b['段落数']}", ""]
    if not issues:
        L.append("未检出差异。注意：本工具只查可枚举的痕迹，语义层面的走样查不出来。")
    else:
        order = {"高": 0, "中": 1, "低": 2}
        for it in sorted(issues, key=lambda d: order.get(d["级别"], 9)):
            L.append(f"[{it['级别']}] {it['项']}：原文 {it['原文']} → 改文 {it['改文']}")
            L.append(f"      变化：{it['变化']}")
            L.append(f"      判读：{it['说明']}")
            L.append("")
    high = [i for i in issues if i["级别"] == "高"]
    L.append("-" * 62)
    if high:
        L.append(f"有 {len(high)} 项高优先级差异，出稿前必须逐条确认去向：")
        for i in high:
            L.append(f"  · {i['项']}：{i['变化']}")
        L.append("  确属合理删除的写进修改说明；误删的回补后重跑。")
    else:
        L.append("无高优先级差异。仍需人工核四项：因果方向、同义替换是否等值、")
        L.append("条件从句作用范围、指代对象——这四项脚本查不出来。")
    return "\n".join(L)


def main(argv):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if len(argv) < 3:
        print("用法：python verify_fidelity.py 原文.md 改文.md [--json]")
        return 2
    as_json = "--json" in argv
    files = [a for a in argv[1:] if not a.startswith("--")]
    if len(files) < 2:
        print("用法：python verify_fidelity.py 原文.md 改文.md [--json]")
        return 2
    pa, pb = Path(files[0]), Path(files[1])
    for p in (pa, pb):
        if not p.is_file():
            print(f"文件不存在：{p}")
            return 2
    a = profile(pa.read_text(encoding="utf-8"))
    b = profile(pb.read_text(encoding="utf-8"))
    issues = compare(a, b)
    if as_json:
        print(json.dumps({"原文": a, "改文": b, "差异": issues}, ensure_ascii=False, indent=1))
    else:
        print(report(issues, a, b))
    return 1 if any(i["级别"] == "高" for i in issues) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
