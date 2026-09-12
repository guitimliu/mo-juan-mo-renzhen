# -*- coding: utf-8 -*-
"""S2.5 程序檢核：純規則引擎，不經 LLM。

輸入：S2 案件摘要（03_介面規格）＋可選的處分書全文（S1.disposition_text）。
輸出：03_介面規格 S2.5 形狀 {admissible, checks[...]}，每條 check 至少含
      {rule, pass, note, inputs}；另加 defect_flags（撤銷前置檢核）與 needs_review（無法判定、需人工確認的項目）。

規則來源：
- 訴願法第14條第1項：自處分達到之次日起 30 日內；期間計算依民法（訴願法第17條），
  末日為星期日、紀念日或其他休息日者以次日代之（民法第122條）。
- 寄存送達：以寄存日視為送達日（法務部 93 年 4 月 13 日法律字第 0930014628 號函；行政程序法第74條）。
- 訴願法第77條第3款／第18條：訴願人須為處分相對人或利害關係人。
- 訴願法第77條第8款：非行政處分不得訴願。
- 行政程序法第96條第1項第2款：書面處分應記載主旨、事實、理由及法令依據；
  事實欄空白非得補正事項（行政程序法第114條；114-18 案撤銷）→ 撤銷前置 defect_flags。

無法判定的一律 pass=False ＋ needs_review=True 留給人，不猜。
"""
from __future__ import annotations

import re
from datetime import date, timedelta

PETITION_DEADLINE_DAYS = 30
DEPOSIT_RULING = "法務部 93 年 4 月 13 日法律字第 0930014628 號函：寄存送達以寄存日為送達日"

# 國定假日（西元）。末日落在這些日子或週六日 → 依民法第122條順延到次一工作日。
# 只列固定日期與 113–115 年（2024–2026）已公告的農曆假日；表外的休息日仍可能漏，所以
# 提起日落在「順延前末日之後 3 天內」時一律 needs_review。
FIXED_HOLIDAYS = {(1, 1), (2, 28), (4, 4), (4, 5), (5, 1), (10, 10)}
LUNAR_HOLIDAYS = {
    date(2024, 2, 8), date(2024, 2, 9), date(2024, 2, 12), date(2024, 2, 13), date(2024, 2, 14),
    date(2024, 6, 10), date(2024, 9, 17),
    date(2025, 1, 27), date(2025, 1, 28), date(2025, 1, 29), date(2025, 1, 30), date(2025, 1, 31),
    date(2025, 5, 30), date(2025, 10, 6),
    date(2026, 2, 16), date(2026, 2, 17), date(2026, 2, 18), date(2026, 2, 19), date(2026, 2, 20),
    date(2026, 6, 19), date(2026, 9, 25),
}
HOLIDAY_GRACE_DAYS = 3

# 77(8) 判斷用：處分類型白名單（子字串比對）與明確非處分清單
DISPOSITION_TYPES = ("書面告誡", "告誡處分書", "告誡書", "裁處告誡", "裁處書", "罰鍰處分書", "處分書", "裁決書", "裁罰書", "沒入處分")
NEGATED_PREFIXES = ("不予", "免予", "免除", "撤銷", "廢止", "註銷")     # 「不予告誡通知書」不是告誡處分
NON_DISPOSITION_TYPES = ("陳情回覆", "陳情答復", "檢舉回覆", "回函", "復函", "說明函")
AMBIGUOUS_TYPES = ("函", "通知", "公告")            # 以函／通知為之者，是否為處分須實質認定（行政程序法第92條）

SERVICE_METHOD_ALIASES = {
    "direct": "direct", "直接": "direct", "直接送達": "direct", "本人": "direct", "親收": "direct", "郵務送達": "direct",
    "deposit": "deposit", "寄存": "deposit", "寄存送達": "deposit",
}

_FULLWIDTH_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")
MASK_CHARS = "○Ｏ〇◯"


# ---------------------------------------------------------------- 日期
def parse_roc_date(value) -> date | None:
    """民國日期 → date。接受 113-09-02、113/9/2、113.09.02、民國113年9月2日、中華民國 113 年 9 月 2 日、
    1130902、20240902；年份 > 1911 視為西元。DD/MM/YYYY 這類第三段為 4 位數的不猜，回 None。"""
    if value is None:
        return None
    if isinstance(value, date):
        return value
    s = str(value).translate(_FULLWIDTH_DIGITS)
    s = re.sub(r"\s+", "", s)
    m = re.search(r"(\d{2,4})[-/.年](\d{1,2})[-/.月](\d{1,2})(?!\d)日?", s)
    if not m:
        m = re.fullmatch(r"(\d{3}|\d{4})(\d{2})(\d{2})", s)      # 1130902 / 20240902
    if not m:
        return None
    y, mo, d = int(m[1]), int(m[2]), int(m[3])
    if y <= 1911:
        y += 1911
    if not (1990 <= y <= 2100):          # 民國 79～189 年以外一律視為解析錯誤
        return None
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def to_roc(d: date | None) -> str | None:
    return None if d is None else f"{d.year - 1911:03d}-{d.month:02d}-{d.day:02d}"


def is_rest_day(d: date) -> bool:
    return d.weekday() >= 5 or (d.month, d.day) in FIXED_HOLIDAYS or d in LUNAR_HOLIDAYS


def deadline_after(served: date, days: int = PETITION_DEADLINE_DAYS) -> tuple[date, date]:
    """(順延前末日, 順延後末日)。自送達之次日起算 N 日，末日遇休息日以次日代之（民法第122條）。"""
    raw = served + timedelta(days=days)
    end = raw
    while is_rest_day(end):
        end += timedelta(days=1)
    return raw, end


# ---------------------------------------------------------------- 各條規則
def normalize_service_method(value) -> str | None:
    """direct／deposit／None（未知）。"""
    if value is None or str(value).strip() == "":
        return "direct"
    return SERVICE_METHOD_ALIASES.get(str(value).strip().lower())


def check_deadline(served, filed, service_method: str = "direct", deposit_date=None) -> dict:
    """訴願法第14條第1項：提起日 ≤ 送達日＋30 日（末日遇休息日順延）。寄存送達以寄存日為送達日。"""
    method = normalize_service_method(service_method)
    served_d, filed_d, deposit_d = parse_roc_date(served), parse_roc_date(filed), parse_roc_date(deposit_date)
    inputs = {"served_date": served, "petition_filed_date": filed, "service_method": service_method, "deposit_date": deposit_date}
    base = {"rule": "訴願法14條 30日", "category": "程序", "served": to_roc(served_d), "filed": to_roc(filed_d), "days": None, "inputs": inputs}
    warnings: list[str] = []
    basis = "送達日"
    if method is None:
        warnings.append(f"送達方式「{service_method}」無法辨識，暫以送達日計算")
    elif method == "deposit":
        if deposit_d is not None:
            served_d, basis = deposit_d, "寄存日（視為送達日）"
        else:
            warnings.append("寄存送達但未提供寄存日，暫以送達日計算，請查送達證書")
    elif deposit_d is not None:
        warnings.append(f"另有寄存日 {to_roc(deposit_d)} 但送達方式非寄存，請確認是否應以寄存日起算")
    base["served"] = to_roc(served_d)

    if served_d is None or filed_d is None:
        missing = [k for k, v in (("送達日", served_d), ("提起日", filed_d)) if v is None]
        return {**base, "pass": False, "needs_review": True, "note": f"缺少{'、'.join(missing)}，無法計算訴願期間，請人工確認"}
    days = (filed_d - served_d).days
    if days < 0:
        return {**base, "days": days, "pass": False, "needs_review": True,
                "note": f"提起日 {to_roc(filed_d)} 早於{basis} {to_roc(served_d)}，日期疑有誤，請人工確認"}
    raw_end, end = deadline_after(served_d)
    prefix = f"{basis} {to_roc(served_d)} → 提起日 {to_roc(filed_d)}，相隔 {days} 天"
    if method == "deposit" and deposit_d is not None:
        prefix = f"寄存送達，{prefix}（{DEPOSIT_RULING}）"
    end_note = f"末日 {to_roc(end)}" + (f"（原末日 {to_roc(raw_end)} 為休息日，依民法第122條順延）" if end != raw_end else "")
    if filed_d <= end:
        note = f"{prefix}，未逾 30 日（訴願法第14條第1項；{end_note}）"
        return {**base, "days": days, "pass": True, "needs_review": bool(warnings), "note": "；".join([note, *warnings])}
    if (filed_d - end).days <= HOLIDAY_GRACE_DAYS:
        note = f"{prefix}，已逾 30 日（{end_note}），但僅逾 {(filed_d - end).days} 天，末日可能另有休息日順延，請人工確認"
        return {**base, "days": days, "pass": False, "needs_review": True, "note": "；".join([note, *warnings])}
    note = f"{prefix}，已逾 30 日（{end_note}），訴願法第77條第2款應不受理；在途期間（訴願法第16條）未計入，請人工確認"
    return {**base, "days": days, "pass": False, "needs_review": bool(warnings), "note": "；".join([note, *warnings])}


NAME_SUFFIXES = ("先生", "小姐", "女士", "君")


def _norm_name(name) -> str:
    """去空白、去尾綴（先生／小姐…）、去尾端標點。"""
    s = re.sub(r"[\s　]+", "", str(name or ""))
    s = s.rstrip("。．.，,、；;：:")
    for suf in NAME_SUFFIXES:
        if len(s) > len(suf) + 1 and s.endswith(suf):
            s = s[: -len(suf)]
    return s


def _is_masked(name: str) -> bool:
    return any(c in MASK_CHARS for c in name)


def _same_person(a: str, b: str) -> bool:
    """姓名相同；任一方含遮罩字元「○」時視為萬用字元（呼叫端要另標 needs_review）。"""
    a, b = _norm_name(a), _norm_name(b)
    if not a or not b or len(a) != len(b):
        return False
    return all(x == y or x in MASK_CHARS or y in MASK_CHARS for x, y in zip(a, b))


ADDRESSEE_LABELS = ("受告誡人", "受處分人", "受裁處人", "被處分人", "處分相對人", "受通知人", "台端")


def extract_addressee(disposition_text: str | None) -> str | None:
    """從處分書全文找「受告誡人：王小明」一類欄位；允許姓名內夾空白（OCR／對齊排版），去尾綴與標點。"""
    if not disposition_text:
        return None
    for label in ADDRESSEE_LABELS:
        m = re.search(rf"{label}\s*[：:]\s*([^\n，,、（(：:]+)", disposition_text)
        if m:
            name = _norm_name(re.split(r"\s{2,}|　", m[1].strip())[0])
            if name:
                return name
    return None


def check_standing(appellant_name, addressee) -> dict:
    """訴願法第77條第3款／第18條：訴願人＝處分相對人。"""
    inputs = {"appellant": appellant_name, "addressee": addressee}
    base = {"rule": "訴願法77(3) 當事人適格", "category": "程序", "inputs": inputs}
    a, b = _norm_name(appellant_name), _norm_name(addressee)
    if not a:
        return {**base, "pass": False, "needs_review": True, "note": "訴願書未辨識出訴願人姓名，請人工確認"}
    if not b:
        return {**base, "pass": False, "needs_review": True, "note": "無法自處分書辨識處分相對人，請人工確認訴願人是否為相對人或利害關係人（訴願法第18條）"}
    if _same_person(a, b):
        if _is_masked(a) or _is_masked(b):
            return {**base, "pass": True, "needs_review": True, "note": f"姓名經遮罩（{a}／{b}），僅比對未遮罩字元，請人工確認為同一人"}
        return {**base, "pass": True, "needs_review": False, "note": f"訴願人即處分相對人（{a}）"}
    if a in b or b in a:
        return {**base, "pass": False, "needs_review": True, "note": f"訴願人（{a}）與處分相對人（{b}）疑似同一人但格式不同，請人工確認"}
    return {**base, "pass": False, "needs_review": True,
            "note": f"訴願人（{a}）非處分相對人（{b}）；若非利害關係人，依訴願法第77條第3款不受理，請人工確認"}


def check_is_disposition(disposition_type, legal_basis=None) -> dict:
    """訴願法第77條第8款：是否為行政處分。"""
    t = re.sub(r"[\s　]+", "", str(disposition_type or ""))
    inputs = {"type": disposition_type, "legal_basis": legal_basis or []}
    base = {"rule": "訴願法77(8) 行政處分", "category": "程序", "inputs": inputs}
    if not t:
        return {**base, "pass": False, "needs_review": True, "note": "未辨識出處分書類型，請人工確認"}
    if any(t.startswith(p) for p in NEGATED_PREFIXES):
        return {**base, "pass": False, "needs_review": True, "note": f"「{t}」為否定／撤銷性質之文書，是否為對訴願人之行政處分須人工確認"}
    if "書面告誡" in t or "告誡" in t:
        return {**base, "pass": True, "needs_review": False, "note": "書面告誡為行政處分（洗防法22條2項）"}
    if any(k in t for k in DISPOSITION_TYPES):
        return {**base, "pass": True, "needs_review": False, "note": f"「{t}」為行政處分"}
    if any(k in t for k in NON_DISPOSITION_TYPES):
        return {**base, "pass": False, "needs_review": False, "note": f"「{t}」非行政處分，依訴願法第77條第8款應不受理"}
    if any(k in t for k in AMBIGUOUS_TYPES):
        return {**base, "pass": False, "needs_review": True,
                "note": f"「{t}」形式上非處分書；是否為行政處分須依內容實質認定（行政程序法第92條），請人工確認"}
    return {**base, "pass": False, "needs_review": True, "note": f"處分類型「{t}」不在已知清單，請人工確認是否為行政處分"}


SECTION_LABELS = ("主旨", "事實", "理由及法令依據", "理由", "法令依據", "注意事項", "說明")
_SECTION_RE = re.compile(r"^\s*(%s)\s*[：:︰]\s*(.*)$" % "|".join(SECTION_LABELS))
_LEGAL_BASIS_RE = re.compile(r"[法例則]\s*第\s*[\d一二三四五六七八九十百]+\s*條")


def parse_disposition_sections(text: str | None) -> dict[str, str]:
    """把處分書全文切成 {段名: 內容}；只認行首「主旨：」「事實：」「理由及法令依據：」等標籤。
    同一標籤出現兩次（例如 OCR 把附件也讀進來）時內容合併，不覆蓋。"""
    sections: dict[str, str] = {}
    if not text:
        return sections
    current = None
    for line in text.splitlines():
        m = _SECTION_RE.match(line)
        if m:
            current = m[1]
            sections[current] = (sections.get(current, "") + "\n" + m[2]).strip()
        elif current:
            sections[current] = (sections[current] + "\n" + line).strip()
    return sections


def check_defects(disposition_text: str | None, s2: dict | None = None) -> tuple[dict, list[dict]]:
    """撤銷前置檢核：行政程序法第96條第1項第2款 應記載事項是否欠缺。回傳 (check, defect_flags)。
    有處分書全文時看段落；沒有時退回 S2 的 facts_by_agency／legal_basis（此時一律 needs_review）。
    函形式（只有主旨／說明）的處分，事實理由寫在說明欄，不報欄位缺漏，改 needs_review。"""
    s2 = s2 or {}
    flags: list[dict] = []
    sections = parse_disposition_sections(disposition_text)
    source = "處分書全文" if sections else "S2 案件摘要"
    needs_review = False
    note_extra = ""
    s2_basis = bool((s2.get("disposition") or {}).get("legal_basis"))
    if sections:
        has_facts_label = "事實" in sections
        has_reasons_label = "理由" in sections or "理由及法令依據" in sections
        facts = sections.get("事實", "")
        reasons = "\n".join(x for x in (sections.get("理由及法令依據", ""), sections.get("理由", "")) if x.strip())
        basis_text = "\n".join(x for x in (sections.get("法令依據", ""), reasons, sections.get("說明", ""), sections.get("主旨", "")) if x)
        has_basis = bool(_LEGAL_BASIS_RE.search(basis_text)) or s2_basis
        if not has_facts_label and not has_reasons_label and "說明" in sections:
            needs_review = True
            note_extra = "函形式處分（主旨／說明），事實與理由記載於說明欄，請人工確認是否完備"
        else:
            if not has_facts_label:
                flags.append({"flag": "facts_missing", "law": "行政程序法第96條第1項第2款", "note": "處分書無「事實」欄"})
            elif not facts.strip():
                flags.append({"flag": "facts_blank", "law": "行政程序法第96條第1項第2款", "note": "處分書事實欄空白；事實非得於訴願程序終結前補正之事項（行政程序法第114條），屬撤銷事由（參 114-18 案）"})
            if not has_reasons_label:
                flags.append({"flag": "reasons_missing", "law": "行政程序法第96條第1項第2款", "note": "處分書無「理由」欄"})
            elif not reasons.strip():
                flags.append({"flag": "reasons_blank", "law": "行政程序法第96條第1項第2款", "note": "處分書理由欄空白（得於訴願程序終結前補正，行政程序法第114條第1項第2款）"})
        if not has_basis:
            flags.append({"flag": "legal_basis_missing", "law": "行政程序法第96條第1項第2款", "note": "處分書未載法令依據"})
    else:
        needs_review = True
        if not str(s2.get("facts_by_agency") or "").strip():
            flags.append({"flag": "facts_blank", "law": "行政程序法第96條第1項第2款", "note": "案件摘要無機關認定事實，處分書事實欄疑空白，請人工確認"})
        if not s2_basis:
            flags.append({"flag": "legal_basis_missing", "law": "行政程序法第96條第1項第2款", "note": "案件摘要無法令依據"})
        note_extra = "無處分書全文，僅依案件摘要判斷，請人工確認"
    notes = [f["note"] for f in flags] or (["主旨、事實、理由及法令依據俱全"] if not note_extra else [])
    if note_extra:
        notes.append(note_extra)
    check = {
        "rule": "行政程序法96條 處分書應記載事項", "category": "瑕疵",
        "pass": not flags, "needs_review": needs_review,
        "inputs": {"source": source, "sections_found": sorted(sections)},
        "note": "；".join(notes),
    }
    return check, flags


# ---------------------------------------------------------------- 入口
def check_procedure(s2: dict, disposition_text: str | None = None) -> dict:
    """S2（＋處分書全文）→ S2.5。對非 dict 的欄位寬容（LLM 擷取偶爾給字串）。"""
    s2 = s2 if isinstance(s2, dict) else {}
    disp = s2.get("disposition") if isinstance(s2.get("disposition"), dict) else {}
    appellant_obj = s2.get("appellant")
    appellant = appellant_obj.get("name") if isinstance(appellant_obj, dict) else appellant_obj
    addressee = disp.get("addressee") or extract_addressee(disposition_text)

    checks = [
        check_deadline(s2.get("served_date"), s2.get("petition_filed_date"),
                       s2.get("service_method", "direct"), s2.get("deposit_date")),
        check_standing(appellant, addressee),
        check_is_disposition(disp.get("type"), disp.get("legal_basis")),
    ]
    defect_check, flags = check_defects(disposition_text, {**s2, "disposition": disp})
    checks.append(defect_check)

    procedural = [c for c in checks if c["category"] == "程序"]
    return {
        "admissible": all(c["pass"] for c in procedural),
        "needs_review": [c["rule"] for c in checks if c.get("needs_review")],
        "checks": checks,
        "defect_flags": flags,
    }
