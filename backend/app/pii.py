# -*- coding: utf-8 -*-
"""個資前處理（取代法）：S1 OCR 之後、任何文字送 Bedrock 之前，把個資換成代號；S4 產出後在本機還原。

- 姓名 → 甲○○／乙○○…（公文慣用代號；同一人全文一致，規則引擎「訴願人＝相對人」比對照樣成立）
- 身分證字號、電話、門牌地址、出生年月日 → ○ 遮罩（保留格式，讓 LLM 知道那是什麼欄位）
- 對照表只存在 Case 物件（記憶體），不進 envelope、不進 log、不上 AWS；envelope 只放摘要（類別與筆數）。
- 純規則（regex＋標籤），不呼叫模型：偵測階段本身不能把個資送出去。
- 黑客松規範第 2 條：AWS 帳戶內不放個資。影像本身仍須送 OCR（無法避免），demo 影像已是虛構資料。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

CODES = "甲乙丙丁戊己庚辛壬癸"
# 姓名出現在這些標籤後面：「訴願人：王小明」「受告誡人：王小明」「訴願人：王小明（簽名）」
NAME_LABELS = ("訴願人", "受告誡人", "受處分人", "受裁處人", "被處分人", "處分相對人", "申請人", "代理人", "代表人", "受通知人", "姓名")
NAME_RE = re.compile(r"(?:%s)\s*[：:]\s*([一-鿿]{2,4})(?=[\s　（(，,、。；;：:]|$)" % "|".join(NAME_LABELS))
ID_RE = re.compile(r"(?<![A-Z0-9])[A-Z][12]\d{8}(?![0-9])")
PHONE_RE = re.compile(r"(?<!\d)0\d{1,2}[-‐–]?\d{3,4}[-‐–]?\d{3,4}(?!\d)|(?<!\d)09\d{2}[-‐–]?[\dX]{3}[-‐–]?[\dX]{3}(?!\d)")
ADDRESS_RE = re.compile(r"((?:[一-鿿]{1,3}(?:縣|市))(?:[一-鿿]{1,3}(?:區|鄉|鎮|市))?)([一-鿿○]{1,6}(?:路|街|大道)(?:[一-鿿○\d]{0,4}段)?(?:[一-鿿○\d]{0,4}巷)?(?:[一-鿿○\d]{0,4}弄)?[一-鿿○\d]{1,6}號(?:[一-鿿○\d]{0,4}樓)?(?:之\d+)?)")
DOB_RE = re.compile(r"((?:出生年月日|出生日期|生日)\s*[：:]\s*(?:民國)?\s*)(\d{2,3})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日")
MASKED_NAME_RE = re.compile(r"^[一-鿿][○×Ｘx]{1,2}[一-鿿]?$")   # 陳○超：原文已遮罩，不動
ROLE_WORDS = {"訴願人", "本人", "台端", "受告誡人", "原處分機關", "簽名", "蓋章", "如上", "同上", "詳如"}


@dataclass
class PIIMap:
    names: dict[str, str] = field(default_factory=dict)      # 真名 → 代號
    others: dict[str, str] = field(default_factory=dict)     # 遮罩前 → 遮罩後（身分證／電話／地址／生日）
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def enabled(self) -> bool:
        return bool(self.names or self.others or self.counts.get("dob_pattern"))

    def summary(self) -> dict:
        """給 envelope：只有類別與筆數，不含任何原值。"""
        return {"mode": "pseudonym", "replaced": {k: v for k, v in self.counts.items() if k != "dob_pattern"},
                "codes": sorted(set(self.names.values()))}


def _bump(m: PIIMap, key: str, n: int = 1) -> None:
    m.counts[key] = m.counts.get(key, 0) + n


def detect(texts: list[str]) -> PIIMap:
    """從 OCR 全文找個資，建對照表。姓名依出現順序給甲乙丙…；其他類別直接算遮罩字串。"""
    m = PIIMap()
    joined = "\n".join(t for t in texts if t)
    for cand in NAME_RE.findall(joined):
        if cand in ROLE_WORDS or MASKED_NAME_RE.match(cand) or cand in m.names:
            continue
        if len(m.names) >= len(CODES):
            break
        m.names[cand] = f"{CODES[len(m.names)]}○○"
    for idn in set(ID_RE.findall(joined)):
        m.others[idn] = idn[0] + idn[1] + "○" * 8
    for ph in set(PHONE_RE.findall(joined)):
        if "X" in ph.upper():                       # 09XX-XXX-XXX 已是遮罩
            continue
        m.others[ph] = re.sub(r"\d", "○", ph)
    for city, rest in set(ADDRESS_RE.findall(joined)):
        if "○" in rest:                             # 北新路○段○○號○樓 已遮罩
            continue
        m.others[city + rest] = city + re.sub(r"[一-鿿\d]", "○", rest[:-1]) + rest[-1] if False else city + "○○路○段○○號"
    for prefix, y, mo, d in set(DOB_RE.findall(joined)):
        m.others[f"{prefix}{y}年{mo}月{d}日"] = f"{prefix}{y}年○月○日"
    return m


def apply(text: str, m: PIIMap) -> str:
    """真名／個資 → 代號／遮罩。長字串先換，避免子字串互吃。"""
    if not text or not m.enabled:
        return text
    out = text
    for real, code in sorted(m.names.items(), key=lambda kv: -len(kv[0])):
        out = out.replace(real, code)
    for real, masked in sorted(m.others.items(), key=lambda kv: -len(kv[0])):
        out = out.replace(real, masked)
    out = DOB_RE.sub(lambda mm: f"{mm[1]}{mm[2]}年○月○日", out)      # 生日：保留年（訴願能力判斷用），月日遮
    return out


def apply_to(obj, m: PIIMap):
    """遞迴套用到 dict／list／str（S1 兩份全文＋備註）。"""
    if isinstance(obj, str):
        return apply(obj, m)
    if isinstance(obj, list):
        return [apply_to(x, m) for x in obj]
    if isinstance(obj, dict):
        return {k: apply_to(v, m) for k, v in obj.items()}
    return obj


def restore(obj, m: PIIMap):
    """代號 → 真名（只還原姓名；身分證／電話／地址本來就不該出現在決定書，維持遮罩）。"""
    if not m.names:
        return obj
    rev = sorted(((code, real) for real, code in m.names.items()), key=lambda kv: -len(kv[0]))

    def _r(s: str) -> str:
        for code, real in rev:
            s = s.replace(code, real)
        return s
    if isinstance(obj, str):
        return _r(obj)
    if isinstance(obj, list):
        return [restore(x, m) for x in obj]
    if isinstance(obj, dict):
        return {k: restore(v, m) for k, v in obj.items()}
    return obj


def count_applied(before: str, after: str, m: PIIMap) -> None:
    """統計實際替換筆數（給 summary）。"""
    for real, code in m.names.items():
        n = before.count(real)
        if n:
            _bump(m, "name", n)
    for real in m.others:
        n = before.count(real)
        if n:
            kind = "id" if ID_RE.fullmatch(real) else "phone" if PHONE_RE.fullmatch(real) else "address"
            _bump(m, kind, n)
    n = len(DOB_RE.findall(before))
    if n:
        _bump(m, "dob", n)
