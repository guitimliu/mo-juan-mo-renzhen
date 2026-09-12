# -*- coding: utf-8 -*-
"""S5 檢核：薄包裝 data/poc/07_檢核.py 的 check()，並依 03_介面規格 附錄 C 補 summary。

回傳形狀（附錄 C）：
{
  "checks": [{group, item, pass, note}],   # 07 原樣
  "score":  {...},                          # 07 原樣
  "summary": {sections_present, citation_grounded, citation_total,
              gold_citations_recalled, gold_citations_missed, holding_match}
}
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from functools import lru_cache

from . import settings

CHECKER_FILE = settings.POC_DIR / "07_檢核.py"
GOLD_FILE = settings.POC_DIR / "06_標準答案_引用清單.json"

NORM = lambda s: re.sub(r"\s+", "", s or "")   # 與 07 相同


@lru_cache(maxsize=1)
def load_checker():
    """檔名含中文與數字開頭，不能直接 import；用 spec_from_file_location。"""
    spec = importlib.util.spec_from_file_location("poc_checker", CHECKER_FILE)
    module = importlib.util.module_from_spec(spec)
    sys.modules["poc_checker"] = module
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=1)
def load_gold() -> dict:
    return json.loads(GOLD_FILE.read_text(encoding="utf8"))


def check(draft: dict, retrieval: dict | None = None) -> dict:
    """07_檢核.py 的 check() 原樣。"""
    return load_checker().check(draft, retrieval)


def draft_from_gold() -> dict:
    """07_檢核.py 的 draft_from_gold()：把 00 正本轉成 S4 草稿（stub 生成用）。"""
    return load_checker().draft_from_gold()


# ---------------------------------------------------------------- summary（附錄 C）
def _retrieval_ids(retrieval: dict | None) -> set[str]:
    ids: set[str] = set()
    for st in (retrieval or {}).get("statutes", []) or []:
        ids.add(NORM(f"{st.get('law')}第{st.get('article')}條"))
    for key in ("precedents", "interpretations", "similar_cases"):
        for x in (retrieval or {}).get(key, []) or []:
            if x.get("id"):
                ids.add(NORM(x["id"]))
    return ids


def _covered(gold_id: str, ids: set[str]) -> bool:
    """標準答案引用是否被檢索結果涵蓋：法條比對到「法第N條」層級（項次忽略），其餘比對 id。
    用完全相等，不用 startswith——否則「訴願法第7條」會誤涵蓋「訴願法第79條」。"""
    g = NORM(gold_id)
    base = re.sub(r"第\d+項$", "", g)
    return g in ids or base in ids


def _source_resolves(source: str, retrieval: dict | None, text: str = "") -> bool:
    """citation 的 source 要指到檢索結果裡存在的項目，且 text 要對得上那個項目
    （法條：以「法第N條」起首；其餘：id 相同或 text 含 id），否則不算有據。"""
    m = re.fullmatch(r"(statutes|precedents|interpretations|similar_cases)\[(\d+)\]", str(source or ""))
    if not m:
        return False
    if retrieval is None:
        return True                       # 沒有檢索結果時只能檢查格式
    items = retrieval.get(m[1]) or []
    k = int(m[2])
    if k >= len(items) or not isinstance(items[k], dict):
        return False
    t = NORM(str(text or ""))
    if not t:
        return True
    if m[1] == "statutes":
        return t.startswith(NORM(f"{items[k].get('law')}第{items[k].get('article')}條"))
    ref = NORM(str(items[k].get("id") or ""))
    return bool(ref) and (t == ref or ref in t or t in ref)


def summarize(report: dict, draft: dict, retrieval: dict | None = None) -> dict:
    """由 checks／草稿／檢索結果算出 03 原本的 S5 摘要。
    gold_citations_recalled／missed：有檢索結果時＝標準答案引用是否被 S3 涵蓋（同 03 範例：正本三篇簡字判決列 missed）；
    沒有檢索結果時退回「草稿本文是否出現」。"""
    gold = load_gold()
    by_item = {c["item"]: c for c in report.get("checks", [])}
    sections_present = {
        name: bool(by_item.get(f"{name}存在", {}).get("pass"))
        for name in ("主文", "事實", "理由", "教示")
    }
    citations = [c for c in (draft.get("citations") or []) if isinstance(c, dict)]
    grounded = sum(1 for c in citations if _source_resolves(c.get("source"), retrieval, c.get("text")))

    expected = [g["id"] for key in ("statutes", "legislative_reasons", "judgments") for g in gold[key]]
    if retrieval is not None:
        ids = _retrieval_ids(retrieval)
        recalled = [g for g in expected if _covered(g, ids)]
    else:
        body = NORM(draft.get("facts")) + "".join(NORM(r) for r in draft.get("reasons") or [])
        recalled = [g for g in expected if NORM(g) in body
                    or all(NORM(k) in body for k in re.findall(r"第\d+條之\d+|立法理由第\d+點", g))]
    holding_item = next((c for c in report.get("checks", []) if c["item"].startswith("主文＝")), None)
    return {
        "sections_present": sections_present,
        "citation_grounded": grounded,
        "citation_total": len(citations),
        "gold_citations_recalled": recalled,
        "gold_citations_missed": [g for g in expected if g not in recalled],
        "holding_match": bool(holding_item and holding_item["pass"]),
    }


def coerce_draft(draft) -> dict:
    """把 LLM 可能給錯型別的 S4 拉回 07 能吃的形狀：dict/list/str 不對就降級成空值，不炸。"""
    d = draft if isinstance(draft, dict) else {}
    out = dict(d)
    out["header"] = d.get("header") if isinstance(d.get("header"), dict) else {}
    for k in ("holding", "facts", "instruction"):
        v = d.get(k)
        out[k] = v if isinstance(v, str) else ("" if v is None else str(v))
    reasons = d.get("reasons")
    out["reasons"] = [r if isinstance(r, str) else str(r) for r in reasons] if isinstance(reasons, list) else ([reasons] if isinstance(reasons, str) else [])
    cites = d.get("citations")
    out["citations"] = [c for c in cites if isinstance(c, dict)] if isinstance(cites, list) else []
    gaps = d.get("gaps")
    out["gaps"] = [g if isinstance(g, str) else str(g) for g in gaps] if isinstance(gaps, list) else []
    return out


def coerce_retrieval(retrieval):
    """S3 四個陣列缺就補空、元素非 dict 就丟掉；07 需要 statutes 有 law/article、其餘有 id。"""
    if not isinstance(retrieval, dict):
        return None
    out = {}
    for k in ("statutes", "precedents", "interpretations", "similar_cases"):
        items = retrieval.get(k)
        items = [x for x in items if isinstance(x, dict)] if isinstance(items, list) else []
        if k == "statutes":
            items = [x for x in items if x.get("law") and x.get("article") is not None]
        else:
            items = [x for x in items if x.get("id")]
        out[k] = items
    return out


def run(draft: dict, retrieval: dict | None = None) -> dict:
    """S5 = 07 完整輸出 + summary。輸入先做型別寬容處理，Bedrock 生成格式稍有出入也不會讓整個案件變 error。"""
    draft, retrieval = coerce_draft(draft), coerce_retrieval(retrieval)
    report = check(draft, retrieval)
    return {"checks": report["checks"], "score": report["score"], "summary": summarize(report, draft, retrieval)}
