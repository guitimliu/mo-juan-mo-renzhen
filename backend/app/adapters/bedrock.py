# -*- coding: utf-8 -*-
"""Bedrock adapters —— 四個階段（OCR、Extract、Retrieval、Generate）都已接 AWS。

規劃（HANDOFF.md §3）：
- OCR：Claude 多模態，Bedrock Converse API 帶 image（Textract 不支援中文）。 ← 已實作
- Extract：Claude 讀 S1 兩份全文 → S2 JSON，後處理正規化日期並用 rules.py 補漏。 ← 已實作
- Generate：主文版本（駁回／撤銷／不受理）由 S2.5 用規則決定（09 規則 5），不交給模型；Claude 的 system prompt
  ＝09_生成提示詞.md＋04_決定書模板.json＋05_few_shot.json；輸出後 header／holding／instruction 用規則覆寫，
  citations／gaps 用 stub.build_citations／find_gaps 同一套後處理（只認檢索結果裡有的）。 ← 已實作
- Retrieval：法條用 data/statutes.json 精確查表（全量 2,214 條）；判解／函釋／相似案打 Knowledge Base
  ZOMMOWFOT2（backend/README.md「Knowledge Base」）三次 retrieve，相似案的 why_similar 再用 Claude 寫一次。 ← 已實作
- 全部 ≤ 1 RPS（主辦方限制）：用 RateLimiter 這個簡單的 token bucket，所有呼叫共用 `limiter`。
- 區域 us-east-1／us-west-2；AWS 帳戶內不得放個資（影像先遮罩）。

憑證：boto3 標準鏈（AWS_PROFILE=hackathon 或 AWS_ACCESS_KEY_ID／AWS_SESSION_TOKEN 環境變數）。
boto3 只在 bedrock 模式才 import，stub 模式不需要裝。
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from functools import lru_cache

from .. import decisions, events, law_index, rules, settings
from . import stub as _stub   # 只借讀檔工具（statutes_table／petitions），不用它的假資料
from .base import UploadedImage

log = logging.getLogger(__name__)

REGION = os.environ.get("BEDROCK_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-west-2"))
# ---- 模型設定（全部可用環境變數覆寫）----
# Claude 在 Bedrock 要用 us. 開頭的 cross-region inference profile，不能用裸 anthropic.xxx。
# BEDROCK_MODEL_ID 是四個階段的共同預設；BEDROCK_<STAGE>_MODEL_ID 可個別覆寫。
# 帳戶拿不到預設模型（AccessDeniedException：not available for this account）時自動降到 BEDROCK_FALLBACK_MODEL_ID，
# 並在 log 與 /api/health 標示；設成空字串就關掉降級。
MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-5")
FALLBACK_MODEL_ID = os.environ.get("BEDROCK_FALLBACK_MODEL_ID", "us.anthropic.claude-sonnet-4-6")
OCR_MODEL_ID = os.environ.get("BEDROCK_OCR_MODEL_ID", MODEL_ID)
EXTRACT_MODEL_ID = os.environ.get("BEDROCK_EXTRACT_MODEL_ID", MODEL_ID)
RETRIEVAL_MODEL_ID = os.environ.get("BEDROCK_RETRIEVAL_MODEL_ID", MODEL_ID)     # 只做篩選＋why_similar，想省錢可設 Haiku
GENERATE_MODEL_ID = os.environ.get("BEDROCK_GENERATE_MODEL_ID", MODEL_ID)
OCR_MAX_TOKENS = int(os.environ.get("BEDROCK_OCR_MAX_TOKENS", "4096"))
GENERATE_MAX_TOKENS = int(os.environ.get("BEDROCK_GENERATE_MAX_TOKENS", "6000"))
KB_ID = os.environ.get("BEDROCK_KB_ID", "ZOMMOWFOT2")
MAX_RETRIES = 4


class RateLimiter:
    """≤ 1 request / second 的最簡 token bucket（單 process）。"""

    def __init__(self, min_interval_s: float = 1.0):
        self.min_interval_s = min_interval_s
        self._last = 0.0
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        async with self._lock:
            now = time.monotonic()
            gap = self.min_interval_s - (now - self._last)
            if gap > 0:
                await asyncio.sleep(gap)
            self._last = time.monotonic()


limiter = RateLimiter()

_client = None


def get_client():
    """共用一個 bedrock-runtime client（lazy；測試可用 BedrockOCR(client=...) 注入假物件）。"""
    global _client
    if _client is None:
        import boto3  # 只有 bedrock 模式才需要
        from botocore.config import Config
        _client = boto3.client("bedrock-runtime", region_name=REGION,
                               config=Config(read_timeout=180, connect_timeout=10, retries={"max_attempts": 0}))
    return _client


_agent_client = None


def get_agent_client():
    global _agent_client
    if _agent_client is None:
        import boto3
        from botocore.config import Config
        _agent_client = boto3.client("bedrock-agent-runtime", region_name=REGION,
                                     config=Config(read_timeout=60, retries={"max_attempts": 0}))
    return _agent_client


_model_fallbacks: dict[str, str] = {}      # 被拒的 model_id → 實際改用的 model_id（process 內記住，不重複試）


def resolve_model(model_id: str) -> str:
    return _model_fallbacks.get(model_id, model_id)


def model_config() -> dict:
    """給 /api/health：各階段設定的模型、實際使用的模型（降級後）與備援。"""
    stages = {"ocr": OCR_MODEL_ID, "extract": EXTRACT_MODEL_ID, "retrieval": RETRIEVAL_MODEL_ID, "generate": GENERATE_MODEL_ID}
    return {"default": MODEL_ID, "fallback": FALLBACK_MODEL_ID or None, "kb_id": KB_ID, "region": REGION,
            "stages": {k: {"configured": v, "active": resolve_model(v)} for k, v in stages.items()},
            "fallbacks_in_effect": dict(_model_fallbacks)}


def _is_model_unavailable(code: str, message: str) -> bool:
    msg = message.lower()
    return (code == "AccessDeniedException" and ("not available" in msg or "access" in msg)) \
        or (code in ("ResourceNotFoundException", "ValidationException") and "model" in msg)


def _converse_stream_collect(client, kwargs: dict, on_delta) -> tuple[str, dict]:
    """在 thread 裡跑 converse_stream，逐段回呼 on_delta（thread-safe 版），最後回 (全文, usage)。"""
    resp = client.converse_stream(**kwargs)
    parts: list[str] = []
    usage: dict = {}
    for ev in resp["stream"]:
        delta = (ev.get("contentBlockDelta") or {}).get("delta") or {}
        if "text" in delta:
            parts.append(delta["text"])
            if on_delta:
                on_delta(delta["text"])
        if "metadata" in ev:
            usage = ev["metadata"].get("usage") or {}
    return "".join(parts), usage


async def converse(client, model_id: str, messages: list[dict], system: str | None = None,
                   max_tokens: int = 4096, temperature: float = 0.0, stream_stage: str | None = None) -> str:
    """呼叫 Converse API，回第一段文字。自帶 1 RPS 限流 + Throttling 指數退避 + 模型不可用時降級。
    stream_stage 有給且 client 支援 converse_stream 且有 WebSocket 訂閱者時，改走串流並把片段推給前端（events.delta）。"""
    model_id = resolve_model(model_id)
    kwargs = {"modelId": model_id, "messages": messages,
              "inferenceConfig": {"maxTokens": max_tokens, "temperature": temperature}}
    if system:
        kwargs["system"] = [{"text": system}]
    on_delta = events.threadsafe_emitter(asyncio.get_running_loop(), stream_stage) if stream_stage else None
    use_stream = on_delta is not None and hasattr(client, "converse_stream")
    for attempt in range(MAX_RETRIES + 1):
        await limiter.wait()
        try:
            if use_stream:
                text, usage = await asyncio.to_thread(_converse_stream_collect, client, kwargs, on_delta)
                log.info("bedrock(stream) %s in=%s out=%s", model_id, usage.get("inputTokens"), usage.get("outputTokens"))
                return text
            resp = await asyncio.to_thread(client.converse, **kwargs)
            usage = resp.get("usage", {})
            log.info("bedrock %s in=%s out=%s", model_id, usage.get("inputTokens"), usage.get("outputTokens"))
            return "".join(c.get("text", "") for c in resp["output"]["message"]["content"])
        except Exception as e:  # botocore ClientError 也走這裡；用名稱判斷免得 import botocore
            err = (getattr(e, "response", None) or {}).get("Error") or {}      # ReadTimeoutError 等 response 是 None
            code, message = err.get("Code", type(e).__name__), str(err.get("Message") or e)
            if _is_model_unavailable(code, message) and FALLBACK_MODEL_ID and model_id != FALLBACK_MODEL_ID:
                log.warning("模型 %s 此帳戶不可用（%s），降級改用 %s", model_id, code, FALLBACK_MODEL_ID)
                for k, v in list(_model_fallbacks.items()) + [(model_id, model_id)]:
                    if v == model_id:
                        _model_fallbacks[k] = FALLBACK_MODEL_ID
                model_id = kwargs["modelId"] = FALLBACK_MODEL_ID
                continue
            retryable = code in ("ThrottlingException", "ServiceUnavailableException", "ModelNotReadyException", "InternalServerException",
                                 "ReadTimeoutError", "ConnectTimeoutError", "EndpointConnectionError", "ConnectionClosedError")
            if not retryable or attempt == MAX_RETRIES:
                raise
            backoff = 2 ** attempt
            log.warning("bedrock %s，%ss 後重試（%d/%d）", code, backoff, attempt + 1, MAX_RETRIES)
            await asyncio.sleep(backoff)
    raise RuntimeError("unreachable")


# ---------------------------------------------------------------- S1 OCR
_IMAGE_FORMATS = {"image/jpeg": "jpeg", "image/png": "png", "image/webp": "webp"}

OCR_SYSTEM = """你是台灣行政機關的文書辨識員。使用者會給你一份台灣公文或訴願書的掃描／拍照影像（可能是手寫，可能多頁）。
任務：逐字轉錄全文，繁體中文，保留原文的段落、標題、條列編號（一、二、三、（一）等）、日期與文號格式。
規則：
- 換行只放在段落、條列項目、表格列、標題、欄位（如「發文日期：…」）之間；同一句因紙張寬度折到下一行的，接回成一行，不要保留折行。
- 半形數字與中文之間不要自行加空格；日期、文號照原文字元寫（例：113年9月1日、新北警店刑字第1134082840號）。
- 「○」「×」「XX」是原文的遮罩符號，照抄，不要猜測被遮的字；遮罩前後的字要特別小心辨識。
- 不要摘要、不要翻譯、不要補全或修正原文；原文寫錯就照抄。
- 手寫勾選框或印章可略；表格以每列一行的純文字呈現。
- 完全無法辨識的字用「□」代替；不確定的字照最可能的寫，並列入 low_confidence。
- 多張影像依給定順序視為同一份文件的連續頁面，合併為一段全文。
只輸出一個 JSON 物件，不要 markdown 圍欄，形狀：
{"text": "全文", "low_confidence": ["不確定的片段（原文字串）", ...], "note": "整體觀察，如：手寫、拍照歪斜、部分遮蔽；沒有就空字串"}"""

_FIELD_LABEL = {"petition_image": "訴願書", "disposition_image": "原處分（書面告誡）"}


def extract_json(raw: str) -> dict | None:
    """模型偶爾會包 ```json 圍欄或前後多話；剝掉後取最外層 {...}。不是 dict 就回 None。"""
    s = raw.strip()
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s)
    m = re.search(r"\{.*\}", s, re.S)
    if not m:
        return None
    try:
        d = json.loads(m[0])
    except json.JSONDecodeError:
        return None
    return d if isinstance(d, dict) else None


def _parse_ocr_json(raw: str) -> dict:
    """解析失敗就整段當 text。"""
    d = extract_json(raw)
    if d is not None and isinstance(d.get("text"), str):
        return {"text": d["text"], "low_confidence": [str(x) for x in d.get("low_confidence") or []],
                "note": str(d.get("note") or "")}
    return {"text": re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip()), "low_confidence": [],
            "note": "模型未回 JSON，已整段當作全文"}


class BedrockOCR:
    def __init__(self, client=None, model_id: str = OCR_MODEL_ID):
        self._client = client
        self.model_id = model_id

    @property
    def client(self):
        return self._client or get_client()

    async def ocr_field(self, label: str, images: list[UploadedImage]) -> dict:
        content = []
        for i, img in enumerate(images, 1):
            fmt = _IMAGE_FORMATS.get(img.content_type)
            if not fmt:
                raise ValueError(f"{img.filename}：Bedrock 不支援 {img.content_type}")
            content.append({"text": f"【{label}】第 {i}/{len(images)} 頁："})
            content.append({"image": {"format": fmt, "source": {"bytes": img.data}}})
        content.append({"text": f"請轉錄以上{len(images)}頁「{label}」影像，依系統指示輸出 JSON。"})
        raw = await converse(self.client, self.model_id, [{"role": "user", "content": content}],
                             system=OCR_SYSTEM, max_tokens=OCR_MAX_TOKENS)
        return _parse_ocr_json(raw)

    async def run(self, case_id: str, images: list[UploadedImage]) -> dict:
        by_field: dict[str, list[UploadedImage]] = {}
        for img in images:
            by_field.setdefault(img.field, []).append(img)
        results: dict[str, dict] = {}
        notes: list[str] = []
        for field in ("petition_image", "disposition_image"):   # 序列呼叫：1 RPS 下並行沒好處
            label = _FIELD_LABEL[field]
            if field not in by_field:
                results[field] = {"text": "", "low_confidence": [], "note": ""}
                notes.append(f"{label}：未上傳")
                continue
            events.progress("S1", f"正在辨識{label}（{len(by_field[field])} 頁）…")
            r = await self.ocr_field(label, by_field[field])
            results[field] = r
            events.progress("S1", f"{label}辨識完成（{len(r['text'])} 字）")
            parts = [f"{label}：{len(by_field[field])} 頁"]
            if r["note"]:
                parts.append(r["note"])
            if r["low_confidence"]:
                parts.append("低信心片段 " + "、".join(f"「{x}」" for x in r["low_confidence"]))
            notes.append("，".join(parts))
        return {
            "case_id": case_id,
            "petition_text": results["petition_image"]["text"],
            "disposition_text": results["disposition_image"]["text"],
            "ocr_confidence_note": f"模型 {resolve_model(self.model_id)}；" + "；".join(notes),
        }


# ---------------------------------------------------------------- S2 Extract
EXTRACT_SYSTEM = """你是台灣地方政府法制局的訴願審查助理。使用者會給你一件訴願案的兩份 OCR 全文：訴願書、原處分書（如書面告誡）。
任務：抽取案件摘要，只輸出一個 JSON 物件（不要 markdown 圍欄、不要解釋），形狀與規則如下：
{
  "appellant": {"name": "訴願人姓名", "dob": "出生年月日", "address": "住址"},
  "agency": "原處分機關全銜",
  "disposition": {
    "date": "處分日期（發文日期）", "doc_no": "發文字號（含「字第…號」全文）", "type": "處分書類型，如 書面告誡／裁處書／罰鍰處分",
    "legal_basis": ["處分所引法令，逐條列出，格式如 洗錢防制法第22條第1項"],
    "addressee": "處分書上的相對人姓名（受告誡人／受處分人）"
  },
  "served_date": "訴願人收受原處分的日期",
  "service_method": "direct | deposit | unknown（寄存送達才填 deposit）",
  "deposit_date": "寄存送達的寄存日，沒有就 null",
  "petition_filed_date": "訴願書提起日（訴願書末尾的日期；若另有機關收文日期以收文日為準）",
  "case_type": "案由，格式如 違反洗錢防制法事件",
  "facts_by_agency": "原處分書「事實」欄全文，逐字抄，不改寫",
  "appellant_claims": ["訴願人主張，每點一句，用訴願人的立場寫"],
  "issues": ["本案爭點，每點一個名詞片語"],
  "evidence": ["兩份文件提到的卷內證據，逐項列，含日期，例：113年8月17日調查筆錄、報案三聯單、與對方LINE對話截圖"],
  "uncertain": ["你不確定或原文缺漏的欄位名稱與原因"]
}
規則：
- 所有日期一律民國格式 YYY-MM-DD（例 113-09-02）；原文沒有的欄位填 null，不要猜。
- 姓名、文號、金額、帳號末四碼等照 OCR 原文，不要「修正」；原文的遮罩符號（○、×、XX）照抄。
- legal_basis 只列處分書實際引用的條文；訴願書引的條文不算。
- appellant_claims、issues 用繁體中文，簡潔；issues 站在審查者角度歸納，3–5 點。
"""

EXTRACT_TEMPLATE = {
    "appellant": {"name": None, "dob": None, "address": None},
    "agency": None,
    "disposition": {"date": None, "doc_no": None, "type": None, "legal_basis": [], "addressee": None},
    "served_date": None, "service_method": "direct", "deposit_date": None, "petition_filed_date": None,
    "case_type": None, "facts_by_agency": None, "appellant_claims": [], "issues": [], "evidence": [], "uncertain": [],
}


def _roc(value) -> str | None:
    """模型回的日期正規化成 YYY-MM-DD；解析不了就保留原字串讓人工看得到。"""
    if value in (None, ""):
        return None
    d = rules.parse_roc_date(value)
    return rules.to_roc(d) if d else str(value)


def _str_list(v) -> list[str]:
    if isinstance(v, str):
        v = [v]
    return [str(x).strip() for x in (v or []) if str(x).strip()]


def normalize_s2(raw: dict, s1: dict) -> dict:
    """把模型輸出對齊 03 規格的 S2：補齊缺 key、日期正規化、用 rules.py 從原文補 addressee／事實／日期。"""
    s2 = json.loads(json.dumps(EXTRACT_TEMPLATE))
    for k, v in (raw or {}).items():
        if isinstance(s2.get(k), dict) and isinstance(v, dict):
            s2[k].update(v)
        else:
            s2[k] = v
    petition, disposition = s1.get("petition_text") or "", s1.get("disposition_text") or ""

    for k in ("served_date", "deposit_date", "petition_filed_date"):
        s2[k] = _roc(s2.get(k))
    s2["disposition"]["date"] = _roc(s2["disposition"].get("date"))
    s2["appellant"]["dob"] = _roc(s2["appellant"].get("dob"))
    s2["disposition"]["legal_basis"] = _str_list(s2["disposition"].get("legal_basis"))
    for k in ("appellant_claims", "issues", "evidence", "uncertain"):
        s2[k] = _str_list(s2.get(k))

    method = str(s2.get("service_method") or "").strip().lower()
    s2["service_method"] = method if method in ("direct", "deposit") else "direct"

    # 規則式補漏：模型漏了就從原文找（跟 stub 同一套 regex）
    if not s2["disposition"].get("addressee"):
        s2["disposition"]["addressee"] = rules.extract_addressee(disposition)
    if not str(s2.get("facts_by_agency") or "").strip():
        s2["facts_by_agency"] = rules.parse_disposition_sections(disposition).get("事實") or None
    if not s2.get("served_date"):
        m = re.search(r"收受(?:原處分|處分書)?日期[：:]\s*([^\n]+)", petition)
        s2["served_date"] = _roc(m[1]) if m else None
    if not s2.get("petition_filed_date"):
        m = re.search(r"中華民國\s*(\d+\s*年\s*\d+\s*月\s*\d+\s*日)\s*$", petition.strip())
        s2["petition_filed_date"] = _roc(m[1]) if m else None
    return s2


class BedrockExtract:
    def __init__(self, client=None, model_id: str = EXTRACT_MODEL_ID):
        self._client = client
        self.model_id = model_id

    @property
    def client(self):
        return self._client or get_client()

    async def run(self, s1: dict) -> dict:
        user = ("=== 訴願書（OCR 全文）===\n" + (s1.get("petition_text") or "（未上傳）") +
                "\n\n=== 原處分書（OCR 全文）===\n" + (s1.get("disposition_text") or "（未上傳）") +
                "\n\n=== OCR 備註 ===\n" + (s1.get("ocr_confidence_note") or "") +
                "\n\n請依系統指示輸出 S2 JSON。")
        events.progress("S2", "模型正在擷取案件摘要（訴願人、處分、日期、主張、爭點）…")
        raw = await converse(self.client, self.model_id, [{"role": "user", "content": [{"text": user}]}],
                             system=EXTRACT_SYSTEM, max_tokens=2048)
        data = extract_json(raw)
        if data is None:
            raise ValueError(f"Extract 模型未回 JSON：{raw[:200]!r}")
        return normalize_s2(data, s1)


# ---------------------------------------------------------------- S3 Retrieval
_statute_re = None


def statute_ref_re() -> re.Pattern:
    """只認 statutes.json 裡有的法規名（長的先比，免得「行為時洗錢防制法」被切錯）。"""
    global _statute_re
    if _statute_re is None:
        laws = sorted({r["law"] for r in _stub.statutes_table()}, key=len, reverse=True)
        _statute_re = re.compile("(" + "|".join(map(re.escape, laws)) + r")第\s*(\d+)\s*條(?:之(\d+))?")
    return _statute_re


TITLE_ID_RE = re.compile(r"^(.+?第\s*\d+\s*號)(?:行政判決|行政裁定|判決|裁定|解釋|函釋|函)?\s*[-－]\s*(.+)$")
CN_NUM = "一二三四五六七八九十"


def parse_statute_ref(text: str) -> tuple[str, str] | None:
    """「洗錢防制法第22條第1項」→ ("洗錢防制法", "22")；「第15條之2」→ "15-2"。"""
    m = statute_ref_re().search(text or "")
    if not m:
        return None
    return m[1], m[2] + (f"-{m[3]}" if m[3] else "")


def build_query(s2: dict) -> str:
    disp = s2.get("disposition") or {}
    parts = [s2.get("case_type") or "", "處分依據：" + "、".join(disp.get("legal_basis") or []),
             "機關認定事實：" + str(s2.get("facts_by_agency") or "")[:300],
             "訴願人主張：" + "；".join(s2.get("appellant_claims") or []),
             "爭點：" + "；".join(s2.get("issues") or [])]
    return "\n".join(p for p in parts if p and not p.endswith("："))


async def retrieve(client, kb_id: str, query: str, category: str | None = None, k: int = 8) -> list[dict]:
    """KB retrieve → [{text, score, uri, metadata}]。主辦方 1 RPS 限制一併套用。"""
    cfg: dict = {"numberOfResults": k}
    if category:
        cfg["filter"] = {"equals": {"key": "category", "value": category}}
    await limiter.wait()
    resp = await asyncio.to_thread(client.retrieve, knowledgeBaseId=kb_id, retrievalQuery={"text": query},
                                   retrievalConfiguration={"vectorSearchConfiguration": cfg})
    out = []
    for r in resp.get("retrievalResults") or []:
        loc = (r.get("location") or {}).get("s3Location") or {}
        out.append({"text": (r.get("content") or {}).get("text") or "", "score": float(r.get("score") or 0),
                    "uri": loc.get("uri") or "", "metadata": r.get("metadata") or {}})
    return out


def group_by_doc(chunks: list[dict]) -> list[dict]:
    """同一份文件多個 chunk → 一筆（取最高分、excerpt 取最高分 chunk），依分數排序。"""
    docs: dict[str, dict] = {}
    for c in chunks:
        key = c["uri"]
        if key not in docs or c["score"] > docs[key]["score"]:
            docs[key] = {**c, "n_chunks": docs.get(key, {}).get("n_chunks", 0)}
        docs[key]["n_chunks"] += 1
    return sorted(docs.values(), key=lambda d: -d["score"])


def _clean_excerpt(text: str, limit: int = 300) -> str:
    text = re.sub(r"\d{20,}", "", text)               # pdftotext 把頁邊行號串在一起
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def _title(doc: dict) -> str:
    md = doc.get("metadata") or {}
    if md.get("title"):
        return str(md["title"])
    from urllib.parse import unquote
    return re.sub(r"\.txt$", "", unquote(doc["uri"].rsplit("/", 1)[-1]))


def _source(doc: dict) -> str:
    from urllib.parse import unquote
    return unquote(doc["uri"]).split("/", 3)[-1] if doc.get("uri") else ""


def precedent_entry(doc: dict) -> dict:
    title = _title(doc)
    m = TITLE_ID_RE.match(title)
    ident, topic = (re.sub(r"\s+", "", m[1]), m[2].strip()) if m else (title, "")
    return {"id": ident, "topic": topic, "excerpt": _clean_excerpt(doc["text"]), "score": round(doc["score"], 3),
            "source": _source(doc)}


def legislative_reasons(chunks: list[dict]) -> list[dict]:
    """判決／決定書引用的「洗錢防制法第15條之2（現行第22條）立法理由」逐點抽出 → interpretations。
    兩種寫法都收：「立法理由略以：「……二、…三、…」」整段引，或「立法理由第3點載明：「三、…」」單點引。
    只抽檢索回來的原文，不自己編。"""
    out: dict[str, dict] = {}
    for c in chunks:
        text = re.sub(r"\d{20,}", "", c["text"])          # pdftotext 頁邊行號
        text = re.sub(r"\s+", "", text)
        for hit in re.finditer(r"立法理由", text):
            window = text[hit.end():hit.end() + 120]
            q = re.search(r"「", window)
            if not q:
                continue
            quote_start = hit.end() + q.end()
            quote_end = text.find("」", quote_start)
            body = text[quote_start:quote_end if quote_end > 0 else quote_start + 1500]
            items = re.split(r"(?:^|(?<=[。；：…]))([一二三四五六七八九十])、", body)
            for cn, txt in zip(items[1::2], items[2::2]):
                n = CN_NUM.index(cn) + 1
                ident = f"洗錢防制法第15條之2立法理由第{n}點"
                txt = txt.strip("…")
                if ident not in out and len(txt) > 10:
                    out[ident] = {"id": ident, "excerpt": txt[:300], "score": round(c["score"], 3),
                                  "source": _source(c) + "（引文）"}
    return [out[k] for k in sorted(out)]


def interpretation_entry(doc: dict) -> dict:
    title = _title(doc)
    m = TITLE_ID_RE.match(title)
    ident, topic = (re.sub(r"\s+", "", m[1]), m[2].strip()) if m else (title, "")
    return {"id": ident, "topic": topic, "excerpt": _clean_excerpt(doc["text"]), "score": round(doc["score"], 3),
            "source": _source(doc)}


def own_case_ids(s2: dict) -> set[str]:
    """本案自己的歷史決定書（demo 時 113-16 就在語料裡）：用原處分文號的數字比對 petitions.jsonl。"""
    doc_no = str((s2.get("disposition") or {}).get("doc_no") or "")
    digits = re.findall(r"\d{6,}", doc_no)
    if not digits:
        return set()
    own = set()
    for cid, row in _stub.petitions().items():
        blob = json.dumps(row.get("原處分") or {}, ensure_ascii=False)
        if any(d in blob for d in digits):
            own.add(cid)
    return own | decisions.own_by_disposition(digits)     # 26,607 篇歷史決定書也要排除


def similar_entry(doc: dict) -> dict | None:
    md = doc.get("metadata") or {}
    cid = str(md.get("doc_no") or "")
    row = _stub.petitions().get(cid)
    if not row:
        return historical_entry(cid, doc)
    return {
        "id": cid, "result": row["裁決類別"], "why_similar": "", "score": round(doc["score"], 3),
        "holding": row.get("主文"), "agency": (row.get("角色") or {}).get("原處分機關"), "decided": row.get("發文日期"),
        "case_type": row.get("案件類型"), "gist": row.get("要旨"),
        "excerpt": _clean_excerpt(doc["text"]), "source": row.get("來源檔") or _source(doc),
    }


def historical_entry(eano: str, doc: dict) -> dict | None:
    """KB 裡來自法制局網站的決定書（metadata.doc_no＝案號）→ 用精簡索引補欄位。"""
    d = decisions.get(eano)
    if not d:
        return None
    return {
        "id": eano, "result": d.get("outcome") or "", "why_similar": "", "score": round(doc["score"], 3),
        "holding": d.get("holding"), "agency": d.get("agency"), "decided": d.get("date"),
        "case_type": d.get("case_type"), "gist": d.get("gist"),
        "excerpt": _clean_excerpt(doc["text"]), "source": f"新北市政府訴願決定書 案號 {eano}（{d.get('doc_no') or ''}）{d.get('url') or ''}",
    }


SCREEN_SYSTEM = """你是訴願審查助理。給你本案摘要，以及向量檢索找回的候選資料：判解（precedents）、函釋（interpretations）、歷史訴願決定書（decisions）。
任務：
1. 判解與函釋：只保留與本案法律問題「直接相關」的（同一法條、同一類爭點或本案會用到的程序法理）；主題無關的（例如本案是洗錢防制法，候選是政府資訊公開法）剔除。
2. 決定書：為每件寫一句「為何與本案相似／可資參考」（20–40 字，繁體中文，指出相同的處分類型、事實型態、主張或程序爭點；結果不同也要點出原因）。
只輸出 JSON 物件，不要其他文字：
{"keep_precedents": ["id", ...], "keep_interpretations": ["id", ...], "why_similar": {"<案號>": "一句話", ...}}"""


def statutes_for(s2: dict, similar: list[dict], precedents: list[dict]) -> list[dict]:
    """法條＝處分依據 ∪ 相似案的裁決依據（訴願法 77／79／81）∪ 保留判解主題裡的條文 ∪ 責任條件（行政罰法 7）；
    全部精確查 statutes.json。（不從檢索段落內文撈：函釋／判決順帶引用的條文太多，會把清單弄髒。）"""
    table = {(r["law"], r["article"]): r for r in _stub.statutes_table()}
    picked: list[tuple[str, str]] = []

    def add(ref):
        if ref and ref in table and ref not in picked:
            picked.append(ref)

    for basis in (s2.get("disposition") or {}).get("legal_basis") or []:
        add(parse_statute_ref(basis))
    for sc in similar:                                    # 只取裁決依據條（77 不受理／79 駁回／81 撤銷），其餘程序條不要
        row = _stub.petitions().get(sc["id"]) or {}
        for item in row.get("相關法條") or []:
            for art in item.get("條") or []:
                if item.get("法規") == "訴願法" and str(art) in ("77", "79", "81"):
                    add(("訴願法", str(art)))
    for p in precedents:
        for m in statute_ref_re().finditer(p.get("topic") or ""):
            add((m[1], m[2] + (f"-{m[3]}" if m[3] else "")))
    blob = "".join((s2.get("appellant_claims") or []) + (s2.get("issues") or []))
    if re.search(r"故意|過失|不知情|不知道|受騙|被騙|認識", blob):          # 責任條件之爭 → 行政罰法 7
        add(("行政罰法", "7"))
    out = [{k: table[ref][k] for k in ("law", "article", "text", "version_date", "source")} for ref in picked[:8]]
    # 歷史同案型決定書高頻實體條文（26,607 篇統計，data/law_index.json）：補處分書沒寫但實務常一併引用的條文
    for h in law_index.historical_statutes(s2.get("case_type"), exclude=set(picked)):
        ref = (h["law"], h["article"])
        if ref in table:
            row = {k: table[ref][k] for k in ("law", "article", "text", "version_date", "source")}
            row["basis"] = "歷史決定書統計"
            row["note"] = f"同案型歷史決定書 {h['cases']} 篇中 {h['share']:.0%} 引用（{h['count']} 篇）"
            out.append(row)
    return out


class BedrockRetrieval:
    def __init__(self, agent_client=None, client=None, kb_id: str = KB_ID, model_id: str = RETRIEVAL_MODEL_ID):
        self._agent_client, self._client = agent_client, client
        self.kb_id, self.model_id = kb_id, model_id

    @property
    def agent_client(self):
        return self._agent_client or get_agent_client()

    @property
    def client(self):
        return self._client or get_client()

    async def screen(self, s2: dict, precedents: list[dict], interpretations: list[dict], similar: list[dict]) -> dict:
        """一次 Claude 呼叫：篩掉無關的判解／函釋 ＋ 為相似案寫 why_similar。失敗就全留、why 用固定句。"""
        fallback = {"keep_precedents": [p["id"] for p in precedents], "keep_interpretations": [i["id"] for i in interpretations], "why_similar": {}}
        if not (precedents or interpretations or similar):
            return fallback
        case = {k: s2.get(k) for k in ("case_type", "facts_by_agency", "appellant_claims", "issues")}
        case["legal_basis"] = (s2.get("disposition") or {}).get("legal_basis")
        payload = {
            "本案": case,
            "precedents": [{"id": p["id"], "topic": p["topic"], "excerpt": p["excerpt"][:200]} for p in precedents],
            "interpretations": [{"id": i["id"], "topic": i.get("topic", ""), "excerpt": i["excerpt"][:200]} for i in interpretations],
            "decisions": [{"id": x["id"], "案件類型": x["case_type"], "結果": x["result"], "要旨": x["gist"], "主文": x["holding"],
                           "節錄": x["excerpt"][:200]} for x in similar],
        }
        try:
            raw = await converse(self.client, self.model_id, [{"role": "user", "content": [{"text": json.dumps(payload, ensure_ascii=False)}]}],
                                 system=SCREEN_SYSTEM, max_tokens=800)
            d = extract_json(raw)
            if d is None:
                raise ValueError(f"screen 模型未回 JSON：{raw[:120]!r}")
            # 某個 key 沒回就當「全留」，不要因為模型漏欄位把資料清空
            return {"keep_precedents": [str(x) for x in d["keep_precedents"]] if "keep_precedents" in d else fallback["keep_precedents"],
                    "keep_interpretations": [str(x) for x in d["keep_interpretations"]] if "keep_interpretations" in d else fallback["keep_interpretations"],
                    "why_similar": {str(k): str(v) for k, v in (d.get("why_similar") or {}).items()}}
        except Exception as e:  # noqa: BLE001 — 篩選是加分項，失敗不擋整個 S3
            log.warning("screen 失敗，全部保留：%s", e)
            return fallback

    async def run(self, s2: dict) -> dict:
        query = build_query(s2)
        own = own_case_ids(s2)
        prec_chunks = await retrieve(self.agent_client, self.kb_id, query, "precedent", k=8)
        events.progress("S3", f"判解檢索完成（{len(prec_chunks)} 段）")
        interp_chunks = await retrieve(self.agent_client, self.kb_id, query, "interpretation", k=6)
        events.progress("S3", f"函釋檢索完成（{len(interp_chunks)} 段）")
        dec_chunks = await retrieve(self.agent_client, self.kb_id, query, "decision", k=12)
        events.progress("S3", f"歷史決定書檢索完成（{len(dec_chunks)} 段），模型篩選中…")

        precedents = [precedent_entry(d) for d in group_by_doc(prec_chunks)[:3]]
        interpretations = [interpretation_entry(d) for d in group_by_doc(interp_chunks)[:3]]

        similar: list[dict] = []
        for d in group_by_doc(dec_chunks):
            e = similar_entry(d)
            if e and e["id"] not in own and len(similar) < 3:
                similar.append(e)
        screened = await self.screen(s2, precedents, interpretations, similar)
        precedents = [p for p in precedents if p["id"] in screened["keep_precedents"]]
        interpretations = [i for i in interpretations if i["id"] in screened["keep_interpretations"]] \
            + legislative_reasons(prec_chunks + dec_chunks)          # 立法理由引文不經篩選：本來就只從相關判決抽出
        for x in similar:
            x["why_similar"] = screened["why_similar"].get(x["id"]) or f"同為{x['case_type']}，結果{x['result']}"

        history = law_index.profile(s2.get("case_type"))
        hist_note = ""
        if history:
            oc = history["outcome"]; n = history["cases"] or 1
            hist_note = f"；歷史同案型「{history['case_type']}」{history['cases']} 篇：" + "、".join(
                f"{k} {oc.get(k, 0) / n:.0%}" for k in ("駁回", "撤銷", "不受理"))
        return {
            "statutes": statutes_for(s2, similar, precedents),
            "precedents": precedents,
            "interpretations": interpretations,
            "similar_cases": similar,
            "history": history,
            "note": f"KB {self.kb_id} 向量檢索（Titan v2）；篩選模型 {resolve_model(self.model_id)}；法條查 statutes.json＋歷史決定書法條索引；已排除本案決定書 {sorted(own) or '無'}{hist_note}",
        }


# ---------------------------------------------------------------- S4 Generate
HOLDINGS = {
    "駁回": ["訴願駁回。"],
    "撤銷": ["原處分撤銷，由原處分機關於2個月內另為適法之處分。", "原處分撤銷。", "原處分撤銷，由原處分機關另為適法之處分。",
           "原處分撤銷，由原處分機關於2個月內另為適法之處理。"],
    "不受理": ["訴願不受理。"],
}
INSTRUCTION_TPE = "如不服本決定，得於決定書送達之次日起 2 個月內向臺北高等行政法院（地址：臺北市士林區福國路 101 號）提起行政訴訟。"
# 77 條各款：由 S2.5 哪條規則沒過對回款次
INADMISSIBLE_CLAUSE = {"訴願法14條 30日": "2", "訴願法77(3) 當事人適格": "3", "訴願法77(8) 行政處分": "8"}


def decide_outcome(s2_5: dict) -> dict:
    """09 規則 5：程序不合 → 不受理；處分書欠缺應記載事項 → 撤銷；其餘 → 駁回。不得有第四種。"""
    s2_5 = s2_5 or {}
    checks = s2_5.get("checks") or []
    if s2_5.get("admissible") is False:
        failed = [c for c in checks if c.get("category") == "程序" and not c.get("pass") and not c.get("needs_review")]
        clause = next((INADMISSIBLE_CLAUSE.get(c["rule"]) for c in failed if c.get("rule") in INADMISSIBLE_CLAUSE), None)
        return {"outcome": "不受理", "version": "不受理版（訴願法77條）", "clause": clause,
                "basis": "；".join(c.get("note", "") for c in failed) or "程序不合"}
    flags = s2_5.get("defect_flags") or []
    if flags:
        return {"outcome": "撤銷", "version": "撤銷版（訴願法81條1項）", "clause": None,
                "basis": "；".join(f.get("note", "") for f in flags)}
    return {"outcome": "駁回", "version": "駁回版（訴願法79條1項）", "clause": None, "basis": "程序合法、處分書記載完備，進入實體審查"}


@lru_cache(maxsize=1)
def generate_system_prompt() -> str:
    poc = settings.POC_DIR
    return (poc / "09_生成提示詞.md").read_text(encoding="utf8").strip() + \
        "\n\n## 決定書模板（04_決定書模板.json）\n" + (poc / "04_決定書模板.json").read_text(encoding="utf8").strip() + \
        "\n\n## 範例決定書（05_few_shot.json）\n" + (poc / "05_few_shot.json").read_text(encoding="utf8").strip()


def _slim_s3(s3: dict) -> dict:
    """給模型看的檢索結果：保留 id／條文全文／節錄，去掉 uri 之類雜訊，並標明索引（citations 的 source 要用）。"""
    out = {}
    for key in ("statutes", "precedents", "interpretations", "similar_cases"):
        rows = []
        for i, x in enumerate(s3.get(key) or []):
            if key == "statutes":
                rows.append({"source": f"statutes[{i}]", "law": x["law"], "article": x["article"], "text": x["text"], "version_date": x.get("version_date")})
            elif key == "similar_cases":
                rows.append({"source": f"similar_cases[{i}]", "id": x["id"], "result": x.get("result"), "holding": x.get("holding"),
                             "why_similar": x.get("why_similar"), "excerpt": x.get("excerpt")})
            else:
                rows.append({"source": f"{key}[{i}]", "id": x["id"], "topic": x.get("topic"), "excerpt": x.get("excerpt")})
        out[key] = rows
    return out


def normalize_reasons(reasons) -> list[str]:
    """模型偶爾回物件（{number, content}）或整段字串；統一成「一、…」字串陣列，項次重新連續編號。"""
    if isinstance(reasons, str):
        reasons = [r for r in re.split(r"\n+", reasons) if r.strip()]
    out = []
    for r in reasons or []:
        if isinstance(r, dict):
            r = str(r.get("content") or r.get("text") or "")
        r = str(r).strip()
        if not r:
            continue
        r = re.sub(r"^[一二三四五六七八九十]+[、．.]\s*", "", r)
        out.append(f"{CN_NUM[len(out)]}、{r}" if len(out) < len(CN_NUM) else r)
    return out


def _fix_holding(holding: str, outcome: str) -> str:
    allowed = HOLDINGS[outcome]
    h = re.sub(r"\s+", "", holding or "")
    return next((a for a in allowed if re.sub(r"\s+", "", a) == h), allowed[0])


def _disposition_ref(s2: dict) -> str | None:
    disp = s2.get("disposition") or {}
    d = rules.parse_roc_date(disp.get("date"))
    if not disp.get("doc_no"):
        return None
    return f"{d.year - 1911}年{d.month}月{d.day}日{disp['doc_no']}" if d else disp["doc_no"]


PROCEDURE_STATUTES = {            # S2.5 規則 → 決定書會引用的條文（不受理／撤銷版理由一）
    "訴願法14條 30日": [("訴願法", "14"), ("訴願法", "77")],
    "訴願法77(3) 當事人適格": [("訴願法", "18"), ("訴願法", "77")],
    "訴願法77(8) 行政處分": [("行政程序法", "92"), ("訴願法", "77")],
    "行政程序法96條 處分書應記載事項": [("行政程序法", "96"), ("行政程序法", "114")],
}


def add_procedure_statutes(s3: dict, s2_5: dict) -> list[str]:
    """S3 在 S2.5 之後才跑但拿不到它，所以程序法條在這裡補：只補「沒過」的規則對應條文，精確查 statutes.json，
    直接 append 進 s3["statutes"]（同一個 dict＝envelope 的 S3），citations 的 statutes[i] 才對得上。回傳補了哪些。"""
    table = {(r["law"], r["article"]): r for r in _stub.statutes_table()}
    have = {(x["law"], x["article"]) for x in s3.get("statutes") or []}
    added = []
    failed = [c["rule"] for c in (s2_5 or {}).get("checks") or [] if not c.get("pass")]
    for rule in failed:
        for ref in PROCEDURE_STATUTES.get(rule, []):
            if ref in table and ref not in have:
                row = table[ref]
                s3.setdefault("statutes", []).append({**{k: row[k] for k in ("law", "article", "text", "version_date", "source")},
                                                      "added_by": f"S2.5 {rule}"})
                have.add(ref)
                added.append(f"{ref[0]}第{ref[1]}條")
    return added


class BedrockGenerate:
    def __init__(self, client=None, model_id: str = GENERATE_MODEL_ID):
        self._client = client
        self.model_id = model_id

    @property
    def client(self):
        return self._client or get_client()

    async def run(self, s2: dict, s2_5: dict, s3: dict) -> dict:
        decision = decide_outcome(s2_5)
        added = add_procedure_statutes(s3, s2_5)
        if added:
            log.info("依 S2.5 補入程序法條：%s", "、".join(added))
        user = "\n\n".join([
            f"## 本件裁決（已由程序檢核規則決定，請直接採用，不得改變）\n{json.dumps(decision, ensure_ascii=False)}\n"
            f"→ 請用模板的「{decision['version']}」骨架；主文必須是該版本列出的句子之一。"
            + ("" if decision["outcome"] != "不受理" else f"結論句引用訴願法第77條第{decision['clause'] or '□'}款。"),
            "## S2 案件摘要\n" + json.dumps(s2, ensure_ascii=False),
            "## S2.5 程序檢核\n" + json.dumps(s2_5, ensure_ascii=False),
            "## S3 檢索結果（唯一允許引用的來源；citations.source 填這裡的 source 欄位）\n" + json.dumps(_slim_s3(s3), ensure_ascii=False),
            "## 輸出要求\n"
            "- reasons 是字串陣列，每個元素一整項，以「一、」「二、」…起首（不要拆成物件、不要另外加 number 欄位）。\n"
            "- 用到檢索結果的判解時寫完整字號並加「參照」（例：「（臺北高等行政法院114年度簡上字第13號判決參照）」）；"
            "用到立法理由時寫「立法理由第N點」並引其原文；用到法條時寫「○○法第N條第N項」。\n"
            "- 理由「二、」卷證涵攝要點出 S2.evidence 列的卷內證據（例：「此有…筆錄、…對話紀錄影本附卷可稽」）。\n"
            "- 理由「三、」逐一回應 S2.appellant_claims 每一點；主張受騙／不知情時，要分別討論：是否為但書「正當理由」、是否對構成要件毫無認識（依證據判斷有無警覺）、縱非故意是否有過失（行政罰法第7條第1項，若在檢索結果內）。\n"
            "只輸出 S4 JSON（header, holding, facts, reasons[], instruction, citations[], gaps[]），不要 markdown 圍欄。",
        ])
        events.progress("S4", f"模型依「{decision['version']}」骨架生成中…")
        raw = await converse(self.client, self.model_id, [{"role": "user", "content": [{"text": user}]}],
                             system=generate_system_prompt(), max_tokens=GENERATE_MAX_TOKENS, stream_stage="S4")
        draft = extract_json(raw)
        if draft is None:
            raise ValueError(f"Generate 模型未回 JSON：{raw[:200]!r}")

        # --- 規則覆寫：這些不交給模型 ---
        draft["reasons"] = normalize_reasons(draft.get("reasons"))
        draft["facts"] = str(draft.get("facts") or "").strip()
        draft["holding"] = _fix_holding(str(draft.get("holding") or ""), decision["outcome"])
        draft["instruction"] = "" if decision["outcome"] == "撤銷" else INSTRUCTION_TPE      # 04：撤銷不附；決定日 ≥ 112-08-15 → 臺北高等
        hdr = draft.get("header") if isinstance(draft.get("header"), dict) else {}
        draft["header"] = {
            "case_type": s2.get("case_type") or hdr.get("case_type"),
            "appellant": (s2.get("appellant") or {}).get("name") or hdr.get("appellant"),
            "agency": s2.get("agency") or hdr.get("agency"),
            "disposition_ref": _disposition_ref(s2) or hdr.get("disposition_ref"),
        }
        # citations／gaps：與 stub 同一套後處理，只認檢索結果裡有的（模型自己寫的 citations 不採信）
        draft["citations"] = _stub.build_citations(draft, s3)
        model_gaps = [str(g) for g in (draft.get("gaps") or []) if str(g).strip()]
        draft["gaps"] = _stub.find_gaps(draft, s3) + [g for g in model_gaps if g not in _stub.find_gaps(draft, s3)]
        draft["outcome"] = decision
        draft["provenance"] = f"bedrock：{resolve_model(self.model_id)} 生成；主文／教示／表頭由規則覆寫，citations 由本文比對檢索結果產生"
        return draft
