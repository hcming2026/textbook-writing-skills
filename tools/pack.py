#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pack.py — 生成交付包 dist/textbook-skills-v<版本>.zip

用法：
    python tools/pack.py <版本号>      # 例：python tools/pack.py 9.9.9
    python tools/pack.py            # 版本号从 CHANGELOG.md 第一条 v 记录读取

两处示例都用占位版本号，不写真实版本——写真实版本会随发版过期，还得再改一次。

打包内容与排除规则都写在下面两处清单里，不靠手工挑选——手工挑选必然漏。
排除项含第三方版权图书与盲评密封件，二者都不得进入交付包。
"""

import hashlib
import os
import re
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 目录 → 包内前缀
INCLUDE_DIRS = ["skills", "规范库", "docs", "tools"]
# 根目录下单文件 → 包内 meta/ 前缀
INCLUDE_ROOT_FILES = ["README.md", "CHANGELOG.md", "需求说明书.md"]

EXCLUDE_DIRS = {"__pycache__", ".work", ".workbuddy", "参考教材", "dist", ".git", ".idea", ".vscode"}
# 不随包分发的单个文件（相对仓库根）
EXCLUDE_FILES = {
    "docs/盲评包/_映射-密封勿发.md",  # 文件自身标注「不得发给评审教师」
}
EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".DS_Store", ".zip"}


def get_version():
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        return sys.argv[1]
    text = open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8").read()
    m = re.search(r"^## v(\d+\.\d+\.\d+)", text, re.M)
    if not m:
        sys.exit("未能从 CHANGELOG.md 读到版本号，请显式传入：python tools/pack.py <版本号>")
    return m.group(1)


def collect():
    files = []
    for d in INCLUDE_DIRS:
        base = os.path.join(ROOT, d)
        if not os.path.isdir(base):
            continue
        for cur, dirs, names in os.walk(base):
            dirs[:] = [x for x in dirs if x not in EXCLUDE_DIRS]
            for n in sorted(names):
                if os.path.splitext(n)[1] in EXCLUDE_SUFFIXES:
                    continue
                full = os.path.join(cur, n)
                rel = os.path.relpath(full, ROOT).replace("\\", "/")
                if rel in EXCLUDE_FILES:
                    continue
                files.append((full, rel))
    for n in INCLUDE_ROOT_FILES:
        full = os.path.join(ROOT, n)
        if os.path.isfile(full):
            files.append((full, "meta/" + n))
    return sorted(files, key=lambda x: x[1])


def main():
    ver = get_version()
    out_dir = os.path.join(ROOT, "dist")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"textbook-skills-v{ver}.zip")
    files = collect()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for full, rel in files:
            z.write(full, rel)
    data = open(out, "rb").read()
    h = hashlib.sha256(data).hexdigest()

    buckets = {}
    for _, rel in files:
        top = rel.split("/")[0]
        buckets[top] = buckets.get(top, 0) + 1
    print(f"版本 {ver}")
    print(f"文件数 {len(files)}  {buckets}")
    print(f"大小 {len(data)} bytes")
    print(f"sha256 {h[:8]}…{h[-6:]}  ({h})")
    print(f"输出 {os.path.relpath(out, ROOT)}")

    # 自检：两个必排文件不得在包内
    names = [rel for _, rel in files]
    for bad in EXCLUDE_FILES:
        if bad in names:
            sys.exit(f"打包失败：{bad} 不应进入交付包")
    if any("参考教材" in n for n in names):
        sys.exit("打包失败：参考教材 不应进入交付包")
    print("自检：密封件与版权图书均未入包")
    return 0


if __name__ == "__main__":
    sys.exit(main())
