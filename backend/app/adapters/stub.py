# -*- coding: utf-8 -*-
"""Stub adapters：不呼叫任何 AI／AWS，內容一律從 data/ 讀，不自己編。

【重要】stub 模式的 S4 草稿＝data/poc/00 正本改寫（07_檢核.py 的 draft_from_gold），不是 AI 生成；
demo 時前端與 README 都要標明，避免誤導評審。

各 stub 的資料來源：
- StubOCR        ← data/poc/01_模擬訴願書.md、02_模擬書面告誡.md（去 markdown 標記）
- StubExtract    ← data/poc/03_介面規格.md 的 S2 範例，再用 S1 文字補齊住址／事實／受處分人／日期
- StubRetrieval  ← data/statutes.json（相關法規 PDF 逐條切）、data/precedents.json（判解 PDF）、
                   data/petitions.jsonl（113-15、114-18）、00 正本理由三的立法理由引文、03 的 S3 範例
- StubGenerate   ← 00 正本 → S4；citations 依附錄 B 由本文比對檢索結果產生；gaps 列本文引了但檢索沒有的判決
"""
from __future__ import annotations

import json
import re
from functools import lru_cache

from .. import checker, rules, settings
from .base import UploadedImage

NORM = lambda s: re.sub(r"\s+", "", s or "")
STUB_NOTE = "stub：未實際辨識；文字取自 data/poc/01、02 模擬文件"
STUB_PROVENANCE = "stub：本草稿為 data/poc/00 正本改寫（07_檢核.py draft_from_gold），非 AI 生成"

JUDGMENT_RE = re.compile(r"(?:最高行政法院|臺北高等行政法院|臺中高等行政法院|高雄高等行政法院)?\d+年度[判裁上訴簡]+字第\d+號")


# ---------------------------------------------------------------- 讀檔
def poc_document(name: str) -> str:
    """01／02 去掉 markdown 標題與引言（# 與 > 開頭的行）後的純文字。"""
    lines = (settings.POC_DIR / name).read_text(encoding="utf8").splitlines()
    return "\n".join(l for l in lines if not l.startswith(("#", ">"))).strip()


@lru_cache(maxsize=None)
def spec_example(stage: str) -> dict:
    """從 03_介面規格.md 取某階段的 JSON 範例（例如 'S2'、'S3'）。"""
    text = (settings.POC_DIR / "03_介面規格.md").read_text(encoding="utf8")
    section = text.split(f"## {stage} ", 1)[1].split("\n## ", 1)[0]
    return json.JSONDecoder().raw_decode(section[section.index("{"):])[0]


@lru_cache(maxsize=1)
def statutes_table() -> list[dict]:
    return json.loads((settings.DATA_DIR / "statutes.json").read_text(encoding="utf8"))


@lru_cache(maxsize=1)
def precedents_table() -> list[dict]:
    return json.loads((settings.DATA_DIR / "precedents.json").read_text(encoding="utf8"))


@lru_cache(maxsize=1)
def petitions() -> dict[str, dict]:
    path = settings.DATA_DIR / "petitions.jsonl"
    rows = [json.loads(l) for l in path.read_text(encoding="utf8").splitlines() if l.strip()]
    return {r["id"]: r for r in rows}


def statute(law: str, article: str) -> dict:
    row = next(r for r in statutes_table() if r["law"] == law and r["article"] == article)
    return {k: row[k] for k in ("law", "article", "text", "version_date", "source")}


# ---------------------------------------------------------------- S1
class StubOCR:
    async def run(self, case_id: str, images: list[UploadedImage]) -> dict:
        return {
            "case_id": case_id,
            "petition_text": poc_document("01_模擬訴願書.md"),
            "disposition_text": poc_document("02_模擬書面告誡.md"),
            "ocr_confidence_note": STUB_NOTE + "；收到影像：" + "、".join(f"{i.filename}（{i.size} bytes）" for i in images),
        }


# ---------------------------------------------------------------- S2
class StubExtract:
    async def run(self, s1: dict) -> dict:
        s2 = json.loads(json.dumps(spec_example("S2"), ensure_ascii=False))   # deep copy
        petition, disposition = s1.get("petition_text") or "", s1.get("disposition_text") or ""
        # 依 01／02 補齊規格範例裡省略的欄位
        m = re.search(r"住址[：:]\s*(\S+)", petition)
        if m:
            s2["appellant"]["address"] = m[1]
        sections = rules.parse_disposition_sections(disposition)
        if sections.get("事實"):
            s2["facts_by_agency"] = sections["事實"]
        addressee = rules.extract_addressee(disposition)
        if addressee:
            s2["disposition"]["addressee"] = addressee          # 供 77(3) 比對；規格外的附加欄位
        m = re.search(r"收受原處分日期[：:]\s*([^\n]+)", petition)
        if m and rules.parse_roc_date(m[1]):
            s2["served_date"] = rules.to_roc(rules.parse_roc_date(m[1]))
        m = re.search(r"中華民國\s*(\d+\s*年\s*\d+\s*月\s*\d+\s*日)\s*$", petition.strip())
        if m and rules.parse_roc_date(m[1]):
            s2["petition_filed_date"] = rules.to_roc(rules.parse_roc_date(m[1]))
        s2.setdefault("service_method", "direct")                # 01 載明「收受原處分日期」→ 直接送達
        return s2


# ---------------------------------------------------------------- S3
def legislative_reason_excerpts() -> list[dict]:
    """立法理由第 3、5 點：正本理由三逐字引用的「三、…」「五、…」段。"""
    gold = checker.load_gold()
    draft = checker.draft_from_gold()
    quotes = re.findall(r"「(.*?)」", draft["reasons"][2])
    out = []
    for item in gold["legislative_reasons"]:
        n = re.search(r"第(\d+)點", item["id"])[1]
        cn = "一二三四五六七八九十"[int(n) - 1]
        q = next((q for q in quotes if q.startswith(f"{cn}、")), None)
        out.append({"id": item["id"], "excerpt": q or item["gist"], "source": "data/poc/00 正本理由三引文"})
    return out


class StubRetrieval:
    async def run(self, s2: dict) -> dict:
        example = spec_example("S3")
        sim = {c["id"]: c for c in example["similar_cases"]}
        rows = petitions()

        def similar(case_id: str, score: float) -> dict:
            row, ex = rows[case_id], sim[case_id]
            return {
                "id": case_id, "result": row["裁決類別"], "why_similar": ex["why_similar"], "score": score,
                "case_type": row["案件類型"], "holding": row["主文"], "agency": row["角色"]["原處分機關"], "decided": row["發文日期"],
                "excerpt": (row["理由"] or "")[:200],
                "source": row["來源檔"],
            }

        precedents = [
            {**{k: p[k] for k in ("id", "topic", "excerpt", "source")}, "score": score}
            for p, score in zip(precedents_table(), (0.81, 0.83, 0.78))
        ]
        return {
            "statutes": [statute("洗錢防制法", "22"), statute("訴願法", "79"), statute("行政罰法", "7")],
            "precedents": precedents,
            "interpretations": legislative_reason_excerpts(),
            "similar_cases": [similar("113-15", sim["113-15"]["score"]), similar("114-18", sim["114-18"]["score"])],
            "note": "stub：固定查表結果，score 為固定值，非向量檢索",
        }


# ---------------------------------------------------------------- S4
def paragraphs(draft: dict):
    """附錄 B 的 (section, index, text)。"""
    yield "facts", 0, draft.get("facts") or ""
    for i, r in enumerate(draft.get("reasons") or []):
        yield "reasons", i, r
    yield "instruction", 0, draft.get("instruction") or ""


def build_citations(draft: dict, retrieval: dict) -> list[dict]:
    """掃描草稿各段，凡出現檢索結果裡的法條／立法理由／判解／相似案，就產生一筆
    {text, source, section, index}（附錄 B）。只會引用檢索結果裡有的東西。"""
    cites: list[dict] = []
    seen: set[tuple] = set()

    def add(text, source, section, index):
        key = (text, source, section, index)
        if key not in seen:
            seen.add(key)
            cites.append({"text": text, "source": source, "section": section, "index": index})

    for section, index, raw in paragraphs(draft):
        body = NORM(raw)
        for k, st in enumerate(retrieval.get("statutes") or []):
            pat = rf"{re.escape(st['law'])}第{st['article']}條(?:第\d+項)?"
            for m in re.finditer(pat, body):
                add(m[0], f"statutes[{k}]", section, index)
        for k, it in enumerate(retrieval.get("interpretations") or []):
            keys = re.findall(r"第\d+條之\d+|立法理由第\d+點", it.get("id") or "")
            if keys and all(NORM(x) in body for x in keys):
                add(it["id"], f"interpretations[{k}]", section, index)
        for key in ("precedents", "similar_cases"):
            for k, it in enumerate(retrieval.get(key) or []):
                if it.get("id") and NORM(it["id"]) in body:
                    add(it["id"], f"{key}[{k}]", section, index)
    return cites


def find_gaps(draft: dict, retrieval: dict) -> list[str]:
    """本文引了、但檢索結果沒有的判決 → 需承辦人補查。"""
    body = "".join(NORM(t) for _, _, t in paragraphs(draft))
    ids = {NORM(x["id"]) for key in ("precedents", "interpretations", "similar_cases") for x in retrieval.get(key) or []}
    missing = []
    for j in JUDGMENT_RE.findall(body):
        if not any(NORM(j) in i or i in NORM(j) for i in ids) and j not in missing:
            missing.append(j)
    return [f"需承辦人補查：{j}（檢索結果無此判決）" for j in missing]


class StubGenerate:
    async def run(self, s2: dict, s2_5: dict, s3: dict) -> dict:
        draft = checker.draft_from_gold()
        gold_md = (settings.POC_DIR / "00_標準答案_113-16_原決定書.md").read_text(encoding="utf8")
        m = re.search(r"## 教示[^\n]*\n(.+?)(?:\n## |\Z)", gold_md, re.S)
        if m:
            draft["instruction"] = m[1].strip()                  # 正本教示（含法院地址）
        disp = s2.get("disposition") or {}
        draft["header"] = {
            "case_type": s2.get("case_type") or draft["header"].get("case_type"),
            "appellant": (s2.get("appellant") or {}).get("name") or draft["header"]["appellant"],
            "agency": s2.get("agency") or draft["header"]["agency"],
            "disposition_ref": draft["header"]["disposition_ref"] if not disp.get("doc_no") else
                               f"{rules.parse_roc_date(disp.get('date')).year - 1911}年{rules.parse_roc_date(disp.get('date')).month}月{rules.parse_roc_date(disp.get('date')).day}日{disp['doc_no']}"
                               if rules.parse_roc_date(disp.get("date")) else disp["doc_no"],
        }
        draft["citations"] = build_citations(draft, s3)
        draft["gaps"] = find_gaps(draft, s3)
        draft["provenance"] = STUB_PROVENANCE
        return draft


def make_adapters():
    from .base import AdapterSet
    return AdapterSet(mode="stub", ocr=StubOCR(), extract=StubExtract(), retrieval=StubRetrieval(), generate=StubGenerate())
