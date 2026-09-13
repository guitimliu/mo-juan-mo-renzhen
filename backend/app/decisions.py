"""歷史訴願決定書精簡索引（data/decisions_slim.jsonl.gz，26,607 篇，由 tools/build_decisions_slim.py 產）。

供 S3：KB 撈回的決定書若不在 petitions.jsonl（主辦方 101 篇），改由這裡補主文／機關／日期／案型；
以及用原處分文號排除本案自己的決定書。
"""
from __future__ import annotations

import gzip
import json
from functools import lru_cache

from . import settings


@lru_cache(maxsize=1)
def table() -> dict[str, dict]:
    path = settings.DATA_DIR / "decisions_slim.jsonl.gz"
    if not path.exists():
        return {}
    with gzip.open(path, "rt", encoding="utf8") as f:
        return {d["eano"]: d for d in (json.loads(l) for l in f if l.strip())}


def get(eano: str) -> dict | None:
    return table().get(str(eano))


def own_by_disposition(digits: list[str]) -> set[str]:
    """導言含原處分文號數字（≥6 碼）的案號——就是本案自己的決定書。"""
    if not digits:
        return set()
    return {e for e, d in table().items() if any(x in d["intro"] for x in digits)}
