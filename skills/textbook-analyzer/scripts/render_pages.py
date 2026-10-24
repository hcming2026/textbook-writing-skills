#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render_pages.py — 教材 PDF 探测与页面渲染（textbook-analyzer 配套）

用途：教材多为扫描件，文本抽取会返回空。本脚本先判断有无文本层，
再把指定页渲染成 PNG，供逐页识读（目录、栏目、正文风格都要看图才准）。

用法：
    python render_pages.py <教材.pdf> --probe
    python render_pages.py <教材.pdf> --pages 12-20 --dpi 110 --outdir ./pages

参数：
    --probe            只报告页数、是否含文本层、书签数量，不渲染
    --pages A-B        渲染区间，1-based，含两端；也可写单页 5
    --dpi N            渲染分辨率，默认 110（正文识读够用；表格密时用 150）
    --outdir DIR       输出目录，默认 ./pages

依赖：pymupdf（pip install pymupdf）。缺失时脚本会给出安装提示并退出 2。
"""

import sys
import argparse
from pathlib import Path


def probe(doc):
    n = doc.page_count
    total = 0
    for i in range(0, n, max(1, n // 8)):
        try:
            total += len((doc[i].get_text() or "").strip())
        except Exception:
            pass
    has_text = total > 200
    try:
        toc = doc.get_toc()
    except Exception:
        toc = []
    real_toc = [t for t in toc if not str(t[1]).strip().isdigit()]
    return {
        "pages": n,
        "text_layer": "yes" if has_text else "no",
        "sampled_chars": total,
        "bookmarks": len(toc),
        "meaningful_bookmarks": len(real_toc),
    }


def parse_pages(expr, n):
    if "-" in expr:
        a, b = expr.split("-", 1)
        a, b = int(a), int(b)
    else:
        a = b = int(expr)
    a = max(1, a)
    b = min(n, b)
    return range(a, b + 1)


def main(argv):
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("pdf")
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--pages")
    ap.add_argument("--dpi", type=int, default=110)
    ap.add_argument("--outdir", default="./pages")
    args = ap.parse_args(argv[1:])

    try:
        import pymupdf
    except ImportError:
        try:
            import fitz as pymupdf  # 旧版包名
        except ImportError:
            print("缺少 pymupdf。请先：pip install pymupdf")
            return 2

    src = Path(args.pdf)
    if not src.is_file():
        print(f"文件不存在：{src}")
        return 2

    doc = pymupdf.open(str(src))
    info = probe(doc)
    print("=== 探测 ===")
    for k, v in info.items():
        print(f"{k}: {v}")

    if info["text_layer"] == "no":
        print("\n结论：无文本层（扫描件）。文本抽取会返回空，必须走渲染识读路线。")
    else:
        print("\n结论：含文本层，可先尝试直接抽取，再用渲染页复核表格与图表。")

    if info["bookmarks"] and info["meaningful_bookmarks"] == 0:
        print("提示：书签全是页码数字，不是真实目录结构，需自行从目录页识读。")

    if args.probe or not args.pages:
        return 0

    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    made = 0
    for p in parse_pages(args.pages, info["pages"]):
        page = doc[p - 1]
        pix = page.get_pixmap(dpi=args.dpi)
        dst = out / f"p{p:03d}.png"
        pix.save(str(dst))
        made += 1
    print(f"\n已渲染 {made} 页 → {out.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
