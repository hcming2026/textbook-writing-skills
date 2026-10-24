#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_exercise.py — 习题集检查（exercise-designer 配套）

用法：
    python check_exercise.py <习题.md> [--level MBA|本科高年级]

查五件事：三层齐全、各层题量与本层比例、每题挂 LO、计算题是否给单位、
拓展题是否写明交付物与评分要点。

退出码：0 = 无 ERROR；1 = 存在 ERROR。
"""

import re
import sys
from pathlib import Path

LO_RE = re.compile(r"LO-(G|\d+)-\d+")
LAYERS = ["基础层", "提高层", "拓展层"]
MINIMUM = {"基础层": 3, "提高层": 2, "拓展层": 1}
RATIO = {"本科高年级": (5, 3, 2), "MBA": (4, 3, 3)}


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
    args = [a for a in argv[1:] if not a.startswith("--")]
    level = "MBA"
    for a in argv[1:]:
        if a.startswith("--level="):
            level = a.split("=", 1)[1]
    if not args:
        print("用法：python check_exercise.py <习题.md> [--level=MBA|本科高年级]")
        return 2
    p = Path(args[0])
    if not p.is_file():
        print(f"文件不存在：{p}")
        return 2

    lines = p.read_text(encoding="utf-8").splitlines()
    rep = R()

    # 切层
    cur, blocks = None, {k: [] for k in LAYERS}
    for line in lines:
        m = re.match(r"^#{2,3}\s*(" + "|".join(LAYERS) + r")\s*$", line)
        if m:
            cur = m.group(1)
            continue
        if cur:
            blocks[cur].append(line)

    present = [k for k in LAYERS if blocks[k]]
    for k in LAYERS:
        if k not in present:
            rep.err("结构", f"缺少「{k}」")

    counts = {}
    for k in present:
        items, cur_item = [], None
        for line in blocks[k]:
            if re.match(r"^\s*\d+[\.、)]", line):
                if cur_item:
                    items.append(cur_item)
                cur_item = [line]
            elif cur_item is not None:
                cur_item.append(line)
        if cur_item:
            items.append(cur_item)
        counts[k] = len(items)
        if len(items) < MINIMUM[k]:
            rep.err(k, f"仅 {len(items)} 题，至少 {MINIMUM[k]} 题")

        for it in items:
            text = "\n".join(it)
            head = it[0]
            num = re.match(r"^\s*(\d+)", head)
            tag = f"{k} 第 {num.group(1) if num else '?'} 题"
            if not LO_RE.search(head):
                rep.err(tag, "题干未标注 [LO-x-y]")
            if k == "提高层" and re.search(r"计算|求|算出", text) and "单位" not in text and not re.search(r"[（(]\s*单位", text):
                # 仅提示：题目若含数值与单位即为合规，此处只查显式声明
                if not re.search(r"[吨万元件人次元个台]", text):
                    rep.warn(tag, "含计算要求但未给数值单位，检查已知条件是否完整")
            if k == "拓展层":
                if "交付物" not in text:
                    rep.err(tag, "拓展题未写明交付物形态（LX-06）")
                if "评分要点" not in text:
                    rep.err(tag, "拓展题未给评分要点（LX-07）")

    total = sum(counts.values())
    if total:
        got = tuple(round(counts.get(k, 0) / total, 2) for k in LAYERS)
        exp = tuple(r / 10 for r in RATIO.get(level, RATIO["MBA"]))
        if any(abs(a - b) > 0.15 for a, b in zip(got, exp)):
            rep.warn("比例", f"三层比例 {got}，{level} 建议 {exp}")

    if total > 12:
        rep.warn("规模", f"共 {total} 题，单课偏多（建议 8–12 题）")

    print(f"三层题量：{counts}")
    return rep.dump()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
