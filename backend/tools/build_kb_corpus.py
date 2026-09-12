# -*- coding: utf-8 -*-
"""把主辦方 PDF 抽成純文字語料，給 Bedrock Knowledge Base 用（PDF 直接餵 KB 內建 parser 會變亂碼）。

用法：python tools/build_kb_corpus.py <PDF 根目錄> <輸出目錄>
  例：python tools/build_kb_corpus.py ~/projects/hackathon/extracted/資料集 ../data/kb_corpus

輸出：每個 PDF → <同名>.txt ＋ <同名>.txt.metadata.json（Bedrock 的 metadata sidecar，Retrieve 可過濾）。
metadata：category（法規／判解／函釋／決定書）、year、case_type、outcome、doc_no（決定書從檔名切）。
之後 `aws s3 sync <輸出目錄> s3://<bucket>/ --delete` 再 start-ingestion-job。
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

CATEGORY = {"相關法規": "statute", "司法院釋字及行政判解": "precedent", "行政函釋": "interpretation", "歷史訴願決定書": "decision"}
# 檔名例：16.113年-違反洗錢防制法事件-79I-訴願無理由-駁回.pdf 的副本.pdf
DECISION_RE = re.compile(r"^(\d+)\.(\d+)年-(.+?)-([0-9IV()、]+)-(.+?)-(.+?)\.pdf")


def pdf_text(path: pathlib.Path) -> str:
    out = subprocess.run(["pdftotext", str(path), "-"], capture_output=True)
    text = out.stdout.decode("utf8", errors="replace")
    text = text.replace("\f", "\n")
    text = re.sub(r"[ \t　]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_name(name: str) -> str:
    return re.sub(r"\.pdf( 的副本)?\.pdf$", "", name)


def metadata(rel: pathlib.Path) -> dict:
    top = rel.parts[0]
    md = {"category": CATEGORY.get(top, top), "title": clean_name(rel.name)}
    if md["category"] == "decision":
        m = DECISION_RE.match(rel.name)
        if m:
            md.update(seq=int(m[1]), year=int(m[2]), case_type=m[3], article=m[4], outcome=f"{m[5]}-{m[6]}",
                      doc_no=f"{m[2]}-{int(m[1]):02d}")
    return md


def main(src: pathlib.Path, dst: pathlib.Path) -> None:
    n_ok = n_bad = 0
    for pdf in sorted(src.rglob("*.pdf")):
        rel = pdf.relative_to(src)
        text = pdf_text(pdf)
        cjk = sum("一" <= c <= "鿿" for c in text)
        if cjk < 50:
            print(f"SKIP（中文 {cjk} 字，可能是掃描檔）: {rel}", file=sys.stderr)
            n_bad += 1
            continue
        out = dst / rel.parent / (clean_name(rel.name) + ".txt")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf8")
        (out.parent / (out.name + ".metadata.json")).write_text(
            json.dumps({"metadataAttributes": metadata(rel)}, ensure_ascii=False, indent=1), encoding="utf8")
        n_ok += 1
    print(f"done: {n_ok} 篇, 略過 {n_bad}", file=sys.stderr)


if __name__ == "__main__":
    main(pathlib.Path(sys.argv[1]).expanduser(), pathlib.Path(sys.argv[2]).expanduser())
