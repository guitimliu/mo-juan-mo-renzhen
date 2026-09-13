"""把 crawl_ntpc_appeals.py 的 decisions.jsonl 轉成 Bedrock KB 語料（與 build_kb_corpus.py 同格式）。

用法：python tools/export_ntpc_appeals_kb.py [--since 2020] [--out ../data/kb_corpus/新北訴願決定書]
輸出：<out>/<西元年>/<案號>.txt ＋ .txt.metadata.json
metadata：category=decision、source=ntpc_web、year（民國）、case_type、outcome、agency、doc_no（=案號）、issued（ISO 日期）。
之後：aws s3 sync ../data/kb_corpus s3://mo-juan-mo-renzhen-kb-text/ --delete → start-ingestion-job（見 backend/README.md）。
注意：backend 的 similar_entry() 目前只認 petitions.jsonl 的 doc_no（113-16 這種），要讓這批進「相似案」需再接 decisions.jsonl。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parents[2]
SRC = HERE / "data" / "ntpc_appeals" / "decisions.jsonl"
ROC_DATE = re.compile(r"(\d+)\s*年\s*(\d+)\s*月\s*(\d+)\s*日")


def iso(roc: str | None) -> str | None:
    m = ROC_DATE.search(roc or "")
    return f"{int(m[1]) + 1911}-{int(m[2]):02d}-{int(m[3]):02d}" if m else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", type=int, default=2004, help="西元年下限")
    ap.add_argument("--out", type=pathlib.Path, default=HERE / "data" / "kb_corpus" / "新北訴願決定書")
    a = ap.parse_args()
    n = 0
    for line in SRC.open(encoding="utf8"):
        d = json.loads(line)
        if d["year"] < a.since or len(d.get("full_text") or "") < 50:
            continue
        out = a.out / str(d["year"]) / f"{d['eano']}.txt"
        out.parent.mkdir(parents=True, exist_ok=True)
        header = f"{d.get('title') or ''}\n案號：{d['eano']}　{d.get('doc_no') or ''}　{d.get('date') or ''}\n相關法條：{'；'.join(d.get('laws') or [])}\n\n"
        out.write_text(header + d["full_text"], encoding="utf8")
        md = {"category": "decision", "source": "ntpc_web", "title": d.get("title") or d["eano"],
              "year": d["year"] - 1911, "case_type": d.get("case_type") or "", "outcome": d.get("outcome") or "",
              "agency": d.get("agency") or "", "doc_no": d["eano"], "issued": iso(d.get("date")) or ""}
        (out.parent / (out.name + ".metadata.json")).write_text(
            json.dumps({"metadataAttributes": md}, ensure_ascii=False, indent=1), encoding="utf8")
        n += 1
    print(f"exported {n} → {a.out}")


if __name__ == "__main__":
    main()
