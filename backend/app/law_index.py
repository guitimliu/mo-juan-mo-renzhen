"""歷史決定書法條索引（data/law_index.json，由 tools/analyze_ntpc_appeals.py 從 26,607 篇新北訴願決定書統計）。

S3 檢索用：給定 S2 的案由（case_type），回傳同案型歷史決定書高頻引用的**實體**條文（程序條文另由裁決版本決定，不在此補），
以及同案型的裁決分布，讓草稿的法條清單不只依賴處分書自己寫的依據。
"""
from __future__ import annotations

import json
import re
from functools import lru_cache

from . import settings

# 裁決版本決定的程序條文，不從歷史統計補（避免駁回案被塞進 77 條）
PROCEDURAL = {("訴願法", a) for a in ("1", "2", "3", "14", "56", "77", "79", "81")} | \
             {("行政程序法", a) for a in ("48", "72", "73", "74")}


@lru_cache(maxsize=1)
def table() -> dict:
    path = settings.DATA_DIR / "law_index.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf8")).get("case_types") or {}


def _norm(s: str) -> str:
    return re.sub(r"[\s因提起訴願]+", "", s or "")


def match_case_type(case_type: str | None) -> str | None:
    """S2 案由 → 索引鍵：先精確，再去掉「違反」「事件」比對，最後子字串。"""
    if not case_type:
        return None
    t = table()
    if case_type in t:
        return case_type
    key = _norm(case_type)
    strip = lambda s: re.sub(r"^違反|事件$", "", _norm(s))  # noqa: E731
    for k in t:
        if strip(k) == strip(key):
            return k
    for k in sorted(t, key=lambda k: -t[k]["cases"]):
        if strip(k) and (strip(k) in key or strip(key) in _norm(k)):
            return k
    return None


def profile(case_type: str | None) -> dict | None:
    """同案型歷史分布：{"case_type", "cases", "outcome": {駁回, 撤銷, 不受理}}。"""
    k = match_case_type(case_type)
    if not k:
        return None
    row = t = table()[k]
    return {"case_type": k, "cases": row["cases"], "outcome": row.get("outcome") or {}}


def historical_statutes(case_type: str | None, exclude: set[tuple[str, str]] = frozenset(), limit: int = 3,
                        min_share: float = 0.08) -> list[dict]:
    """同案型高頻實體條文（全文抽取、引用率 ≥ min_share、statutes.json 有全文），依引用率排序。
    回傳 [{"law","article","share","count","cases","outcome"}]，由呼叫端補全文。"""
    k = match_case_type(case_type)
    if not k:
        return []
    row = table()[k]
    out = []
    for it in row.get("laws_in_text") or []:
        ref = (it["law"], it["article"])
        if ref in PROCEDURAL or ref in exclude or not it.get("in_statutes") or it["share"] < min_share:
            continue
        out.append({"law": it["law"], "article": it["article"], "share": it["share"], "count": it["count"],
                    "cases": row["cases"], "outcome": it.get("outcome") or {}})
        if len(out) >= limit:
            break
    return out
