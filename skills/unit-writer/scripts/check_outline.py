#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_outline.py — 教材大纲确定性检查（outline-designer 配套脚本）

用法：
    python scripts/check_outline.py <大纲文件.md>

只做「能用规则判断」的检查：结构标记、编号连续性、目标可追溯、
学时配平、栏目完整性、篇幅区间合理性。不做质量评价——那属于
textbook-reviewer 的职责。

退出码：0 = 无 ERROR（可能有 WARN）；1 = 存在 ERROR，不得交付。
"""

import re
import sys
from pathlib import Path

FIXED_SECTIONS = ["导语", "正文", "案例", "思考", "练习", "拓展"]
REQUIRED_FM = ["course", "discipline", "level", "edition",
               "total_hours", "units", "textbook_mode", "owner"]
VALID_LEVELS = {"本科高年级", "MBA"}

UNIT_RE = re.compile(r"^##\s*单元\s*(\d+)\s+(.+?)（\s*(\d+)\s*学时\s*）\s*$")
LESSON_RE = re.compile(r"^###\s*第\s*(\d+)\s*课\s+(.+?)（\s*(\d+)\s*学时\s*）\s*$")
LO_RE = re.compile(r"LO-(\d+)-(\d+)")
LO_GLOBAL_RE = re.compile(r"LO-G-(\d+)")
BULLET_RE = re.compile(r"^-\s*(学习目标|栏目|篇幅|核心知识点|前置知识|图位)\s*[：:]\s*(.+?)\s*$")
RANGE_RE = re.compile(r"(\d+)\s*[–\-—~]\s*(\d+)\s*字")


class Report:
    def __init__(self):
        self.errors = []
        self.warns = []

    def err(self, where, msg):
        self.errors.append((where, msg))

    def warn(self, where, msg):
        self.warns.append((where, msg))

    def dump(self):
        for where, msg in self.errors:
            print(f"[ERROR] {where} :: {msg}")
        for where, msg in self.warns:
            print(f"[WARN ] {where} :: {msg}")
        print()
        print(f"结果：{len(self.errors)} 个 ERROR，{len(self.warns)} 个 WARN")
        return 1 if self.errors else 0


def split_frontmatter(lines):
    """返回 (frontmatter dict, 正文起始行号)。无 frontmatter 时返回 ({}, 0)。"""
    if not lines or lines[0].strip() != "---":
        return {}, 0
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            fm = {}
            for raw in lines[1:i]:
                if not raw.strip() or raw.lstrip().startswith("#"):
                    continue
                if ":" in raw and not raw.startswith(" "):
                    k, v = raw.split(":", 1)
                    fm[k.strip()] = v.strip().strip("'\"")
            return fm, i + 1
    return {}, 0


def parse_units(lines, start, rep):
    """解析单元与课结构。返回 [ {no, title, hours, lo_defs, lessons:[...], line} ]"""
    units = []
    cur_unit = None
    cur_lesson = None
    global_lo = set()
    in_global_zone = True

    for idx in range(start, len(lines)):
        raw = lines[idx]
        line = raw.rstrip()
        lineno = idx + 1

        m = UNIT_RE.match(line)
        if m:
            in_global_zone = False
            cur_unit = {
                "no": int(m.group(1)), "title": m.group(2), "hours": int(m.group(3)),
                "lo_defs": set(), "lo_lines": {}, "lessons": [], "line": lineno,
                "raw_block": [], "prereqs": set(),
            }
            units.append(cur_unit)
            cur_lesson = None
            continue

        m = LESSON_RE.match(line)
        if m and cur_unit is not None:
            cur_lesson = {
                "no": int(m.group(1)), "title": m.group(2), "hours": int(m.group(3)),
                "fields": {}, "line": lineno,
            }
            cur_unit["lessons"].append(cur_lesson)
            continue

        if line.startswith("## ") and cur_unit is not None:
            cur_unit = None
            cur_lesson = None
            continue

        if cur_lesson is None:
            # 单元块（或全书头部）：收集目标定义
            is_prereq = ("前置要求" in line) or ("前置知识" in line)
            for lo in LO_RE.findall(line):
                label = f"LO-{lo[0]}-{lo[1]}"
                if is_prereq:
                    # 前置要求是跨单元引用，不算定义
                    if cur_unit is not None:
                        cur_unit.setdefault("prereqs", set()).add(label)
                    continue
                if cur_unit is not None:
                    if int(lo[0]) != cur_unit["no"]:
                        rep.err(f"第 {lineno} 行",
                                f"目标 {label} 的单元号与所属单元 {cur_unit['no']} 不一致")
                    cur_unit["lo_defs"].add(label)
                    cur_unit["lo_lines"][label] = lineno
            if in_global_zone:
                for g in LO_GLOBAL_RE.findall(line):
                    global_lo.add(f"LO-G-{g}")
            continue

        m = BULLET_RE.match(line)
        if m:
            key, val = m.group(1), m.group(2)
            if key in cur_lesson["fields"]:
                rep.err(f"第 {lineno} 行", f"第 {cur_lesson['no']} 课的项目「{key}」重复")
            cur_lesson["fields"][key] = val
        elif line.strip() and not line.strip().startswith("#"):
            cur_lesson.setdefault("extras", []).append(line.strip())

    return units, global_lo


def check_lesson_fields(lesson, unit_no, rep):
    where = f"单元 {unit_no} 第 {lesson['no']} 课"
    f = lesson["fields"]

    for key in ["学习目标", "栏目", "篇幅", "核心知识点", "前置知识", "图位"]:
        if key not in f or not f[key].strip():
            rep.err(where, f"缺少必填项「- {key}：」")

    if "栏目" in f:
        got = [x.strip() for x in re.split(r"[/／、,，]", f["栏目"]) if x.strip()]
        if got != FIXED_SECTIONS:
            rep.err(where, f"栏目应为「{' / '.join(FIXED_SECTIONS)}」，实为「{' / '.join(got)}」")

    if "篇幅" in f:
        seg = f["篇幅"]
        body = None
        for part in re.split(r"[；;]", seg):
            if part.strip().startswith("正文"):
                body = part
                break
        if body is None:
            rep.err(where, "篇幅未给出「正文」字数区间")
        else:
            m = RANGE_RE.search(body)
            if not m:
                rep.err(where, f"正文篇幅未写成「X–Y 字」区间：{body.strip()}")
            else:
                lo, hi = int(m.group(1)), int(m.group(2))
                if lo >= hi:
                    rep.err(where, f"正文篇幅区间下限不小于上限：{lo}–{hi}")
                elif hi / lo > 1.5:
                    rep.err(where, f"正文篇幅区间跨度过大（{lo}–{hi}，超过 1.5 倍），无法约束写作")

    if "图位" in f and "【图" not in f["图位"]:
        rep.err(where, "图位未使用「【图 X-Y 建议：…】」标记")

    if lesson["hours"] not in (2, 4):
        rep.warn(where, f"单课学时为 {lesson['hours']}，规范值为 2 或 4")

    return f


def main(argv):
    if len(argv) != 2:
        print("用法：python check_outline.py <大纲文件.md>")
        return 2

    path = Path(argv[1])
    if not path.is_file():
        print(f"文件不存在：{path}")
        return 2

    lines = path.read_text(encoding="utf-8").splitlines()
    rep = Report()

    fm, body_start = split_frontmatter(lines)
    if not fm:
        rep.err("frontmatter", "缺少 YAML frontmatter（--- ... ---）")
    else:
        for key in REQUIRED_FM:
            if key not in fm or not fm[key]:
                rep.err("frontmatter", f"缺少必填字段 `{key}`")
        level = fm.get("level", "")
        if level and level not in VALID_LEVELS:
            rep.err("frontmatter", f"level 只能为「本科高年级」或「MBA」，实为「{level}」")
        for key in ["total_hours", "units", "edition"]:
            if fm.get(key) and not fm[key].isdigit():
                rep.err("frontmatter", f"`{key}` 必须为整数，实为「{fm[key]}」")

    units, global_lo = parse_units(lines, body_start, rep)
    if not units:
        rep.err("结构", "未解析到任何单元标题（应形如「## 单元 1 标题（8 学时）」）")
        return rep.dump()

    # 单元编号连续
    for i, u in enumerate(units, 1):
        if u["no"] != i:
            rep.err(f"第 {u['line']} 行", f"单元编号应为 {i}，实为 {u['no']}（须连续从 1 开始）")

    if fm.get("units", "").isdigit() and int(fm["units"]) != len(units):
        rep.err("frontmatter", f"`units` 声明 {fm['units']} 个，实际解析到 {len(units)} 个")

    unit_hours_total = 0
    for u in units:
        where_u = f"单元 {u['no']}"
        if not u["lo_defs"]:
            rep.err(where_u, "未定义任何单元目标（LO-<单元号>-<序号>）")
        if not 3 <= len(u["lessons"]) <= 5:
            rep.warn(where_u, f"课数为 {len(u['lessons'])}，规范区间为 3–5")

        refs = set()
        lesson_hours = 0
        for i, l in enumerate(u["lessons"], 1):
            if l["no"] != i:
                rep.err(f"第 {l['line']} 行",
                        f"单元 {u['no']} 内课编号应为 {i}，实为 {l['no']}（须连续）")
            lesson_hours += l["hours"]
            f = check_lesson_fields(l, u["no"], rep)

            seg = f.get("学习目标", "")
            ids = [f"LO-{a}-{b}" for a, b in LO_RE.findall(seg)]
            ids += [f"LO-G-{g}" for g in LO_GLOBAL_RE.findall(seg)]
            if not ids:
                rep.err(where_u, f"第 {l['no']} 课未引用任何学习目标")
            for lo in ids:
                refs.add(lo)
                if lo.startswith("LO-G-"):
                    if global_lo and lo not in global_lo:
                        rep.err(where_u, f"第 {l['no']} 课引用了未定义的全局目标 {lo}")
                elif lo not in u["lo_defs"]:
                    rep.err(where_u, f"第 {l['no']} 课引用的 {lo} 未在本单元目标中定义")

        if lesson_hours != u["hours"]:
            rep.err(where_u, f"课学时合计 {lesson_hours} ≠ 单元学时 {u['hours']}")
        unit_hours_total += u["hours"]

        for lo, ln in u["lo_lines"].items():
            if lo not in refs:
                rep.err(where_u, f"目标 {lo}（第 {ln} 行）为孤儿目标，未被任何一课引用")

    if fm.get("total_hours", "").isdigit():
        total = int(fm["total_hours"])
        if unit_hours_total != total:
            rep.err("学时", f"单元学时合计 {unit_hours_total} ≠ 总学时 {total}")

    return rep.dump()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
