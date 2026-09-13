"""把 data/ntpc_appeals/decisions.jsonl（188 MB）壓成後端可載入的精簡索引 data/decisions_slim.jsonl.gz。
每篇：eano, year, date, case_type, outcome, agency, laws, title, holding(主文), gist(理由前 400 字), intro(導言前 500 字，供排除本案), url。
用法：python tools/build_decisions_slim.py
"""
from __future__ import annotations

import gzip
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "data" / "ntpc_appeals" / "decisions.jsonl"
IDX = ROOT / "data" / "ntpc_appeals" / "index.jsonl"
DST = ROOT / "data" / "decisions_slim.jsonl.gz"
ROC = re.compile(r"(\d+)\s*年\s*(\d+)\s*月\s*(\d+)\s*日")


def section(full: str, head: str, nxt: str) -> str:
    m = re.search(rf"{head}\s*\n", full)
    if not m:
        return ""
    rest = full[m.end():]
    e = re.search(rf"\n\s*{nxt}\s*\n", rest)
    return re.sub(r"\s+", " ", rest[: e.start()] if e else rest).strip()


def main() -> None:
    urls = {json.loads(l)["eano"]: json.loads(l)["url"] for l in IDX.open(encoding="utf8")}
    n = 0
    with gzip.open(DST, "wt", encoding="utf8") as out:
        for line in SRC.open(encoding="utf8"):
            d = json.loads(line)
            full = d["full_text"]
            m = ROC.search(d.get("date") or "")
            holding = section(full, r"主\s*文", r"(?:事\s*實|理\s*由)")[:200]
            reason = section(full, r"理\s*由", r"(?:訴願審議委員會|如不服本決定)")
            intro = re.sub(r"\s+", " ", full[:500])
            out.write(json.dumps({
                "eano": d["eano"], "year": d["year"],
                "date": f"{int(m[1]) + 1911}-{int(m[2]):02d}-{int(m[3]):02d}" if m else None,
                "case_type": d.get("case_type"), "outcome": d.get("outcome"), "agency": d.get("agency"),
                "laws": d.get("laws") or [], "title": d.get("title"), "doc_no": d.get("doc_no"),
                "holding": holding, "gist": reason[:400], "intro": intro,
                "url": "https://web.law.ntpc.gov.tw" + urls.get(d["eano"], ""),
            }, ensure_ascii=False) + "\n")
            n += 1
    print(f"{n} → {DST} ({DST.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
