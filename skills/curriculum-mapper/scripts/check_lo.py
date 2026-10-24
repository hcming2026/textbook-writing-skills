#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_lo.py — 学习目标（LO）表检查（curriculum-mapper 配套）

用法：
    python check_lo.py <LO表.csv>

查六件事：表头完整、编号合法且唯一、认知层级合法、表述可测（无"了解/熟悉/掌握"
作主干）、课标条目无遗漏（同一课标条目被引用多次会提示）、单元号连续。

退出码：0 = 无 ERROR；1 = 存在 ERROR。
"""

import csv
import re
import sys
from collections import Counter
from pathlib import Path

HEADER = ["LO编号", "目标表述", "认知层级", "对应课标条目", "单元号", "拆解理由", "备注"]
LEVELS = {"识记", "理解", "应用", "分析", "评价", "创造"}
BAD_VERBS = ["了解", "熟悉", "掌握", "懂得", "体会", "培养"]
LO_RE = re.compile(r"^LO-(G|\d+)-(\d+)$")


class R:
    def __init__(self):
        self.e, self.w = [], []

    def err(self, w, m): self.e.append((w, m))
    def warn(self, w, m): self.w.append((w, m))

    def dump(self):
        for w, m in self.e: print(f"[ERROR] {w} :: {m}")
        for w, m in self.w: print(f"[WARN ] {w} :: {m}")
        print(f"\n结果：{len(self.e)} 个 ERROR，{len(self.w)} 个 WARN")
        return 1 if self.e else 0


def main(argv):
    if len(argv) != 2:
        print("用法：python check_lo.py <LO表.csv>")
        return 2
    p = Path(argv[1])
    if not p.is_file():
        print(f"文件不存在：{p}")
        return 2

    rows = list(csv.DictReader(p.open(encoding="utf-8-sig")))
    rep = R()
    if not rows:
        print("表格为空")
        return 1

    missing = [h for h in HEADER if h not in rows[0]]
    if missing:
        rep.err("表头", f"缺少列：{'、'.join(missing)}")
        return rep.dump()

    ids, per_unit, std_refs = [], Counter(), Counter()
    for i, r in enumerate(rows, 2):
        rid = (r.get("LO编号") or "").strip()
        where = f"第 {i} 行（{rid or '无编号'}）"

        m = LO_RE.match(rid)
        if not m:
            rep.err(where, "编号不合规，应为 LO-<单元>-<序号> 或 LO-G-<序号>")
        else:
            ids.append(rid)
            if m.group(1) != "G":
                per_unit[int(m.group(1))] += 1

        text = (r.get("目标表述") or "").strip()
        if not text:
            rep.err(where, "目标表述为空")
        else:
            if len(text) < 8:
                rep.err(where, f"目标表述过短（{len(text)} 字），无法判断行为标准")
            if not text.startswith("能"):
                rep.warn(where, "目标表述未以「能…」开头，可能不是可观察行为")
            head = text[:6]
            for v in BAD_VERBS:
                if v in head:
                    rep.err(where, f"以不可测动词「{v}」开头，改为行为动词（识记/理解/应用/分析/评价/创造）")

        lv = (r.get("认知层级") or "").strip()
        if lv not in LEVELS:
            rep.err(where, f"认知层级「{lv}」不合法，应为 {'/'.join(sorted(LEVELS))}")

        std = (r.get("对应课标条目") or "").strip()
        if not std:
            rep.warn(where, "未填对应课标条目（若为自拟目标，请在备注说明依据）")
        else:
            std_refs[std] += 1
            if std_refs[std] > 3:
                rep.err(where, f"课标条目「{std}」被 {std_refs[std]} 条 LO 同时引用，疑似拆解过细")

        if not (r.get("单元号") or "").strip().isdigit():
            rep.err(where, "单元号缺失或非数字")

    dup = [k for k, v in Counter(ids).items() if v > 1]
    if dup:
        rep.err("编号", f"编号重复：{'、'.join(dup)}")

    units = sorted(per_unit)
    if units and units != list(range(1, max(units) + 1)):
        rep.err("单元", f"单元号不连续，实际有：{units}")

    total = len(ids)
    if total < 20:
        rep.warn("规模", f"LO 共 {total} 条，偏少（建议 30–48 条）")
    elif total > 60:
        rep.warn("规模", f"LO 共 {total} 条，偏多（建议 30–48 条），检查是否拆得过细")

    for u in units:
        n = per_unit[u]
        if n < 3:
            rep.warn("单元", f"单元 {u} 只有 {n} 条 LO，偏少（建议 3–6 条）")
        elif n > 6:
            rep.warn("单元", f"单元 {u} 有 {n} 条 LO，偏多（建议 3–6 条）")

    return rep.dump()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
