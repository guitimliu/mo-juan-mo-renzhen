# -*- coding: utf-8 -*-
"""S2.5 規則引擎：30 日、寄存送達、77 條各款、96 條瑕疵。"""
from datetime import date

import pytest

from app import rules


# ---------------------------------------------------------------- 日期解析
@pytest.mark.parametrize("raw, expected", [
    ("113-09-02", date(2024, 9, 2)),
    ("113/9/2", date(2024, 9, 2)),
    ("113.09.02", date(2024, 9, 2)),
    ("民國113年9月2日", date(2024, 9, 2)),
    ("中華民國 113 年 9 月 5 日", date(2024, 9, 5)),
    ("１１３年９月２日", date(2024, 9, 2)),
    ("2024-09-02", date(2024, 9, 2)),
    ("", None), (None, None), ("無日期", None), ("113-13-40", None),
])
def test_parse_roc_date(raw, expected):
    assert rules.parse_roc_date(raw) == expected


def test_to_roc():
    assert rules.to_roc(date(2024, 9, 2)) == "113-09-02"
    assert rules.to_roc(None) is None


# ---------------------------------------------------------------- 訴願法 14 條 30 日
def test_deadline_113_16_three_days():
    c = rules.check_deadline("113-09-02", "113-09-05")
    assert c["pass"] is True and c["days"] == 3 and c["served"] == "113-09-02" and c["filed"] == "113-09-05"
    assert c["rule"] == "訴願法14條 30日" and c["inputs"]["service_method"] == "direct"
    assert "未逾 30 日" in c["note"]


@pytest.mark.parametrize("filed, ok, review", [
    ("113-10-02", True, False),    # 第 30 日（週三）：末日仍可提起
    ("113-10-03", False, True),    # 第 31 日：逾期，但在 3 天寬限內 → 留人工確認是否另有休息日順延
    ("113-10-15", False, False),   # 逾期 13 天：明確不受理
])
def test_deadline_boundary(filed, ok, review):
    c = rules.check_deadline("113-09-02", filed)
    assert c["pass"] is ok and c["needs_review"] is review
    if not ok:
        assert "已逾 30 日" in c["note"]
    if not ok and not review:
        assert "77條第2款" in c["note"]


def test_deadline_end_on_sunday_rolls_to_monday():
    """送達 113-09-06（五）→ 第 30 日 113-10-06 是星期日 → 依民法第122條末日順延至 10-07（一）。"""
    raw, end = rules.deadline_after(date(2024, 9, 6))
    assert (raw, end) == (date(2024, 10, 6), date(2024, 10, 7))
    c = rules.check_deadline("113-09-06", "113-10-07")
    assert c["pass"] is True and c["days"] == 31 and "順延" in c["note"] and "民法第122條" in c["note"]
    assert rules.check_deadline("113-09-06", "113-10-08")["pass"] is False


def test_deadline_end_on_national_holiday_rolls_forward():
    """送達 113-09-10 → 第 30 日 113-10-10 國慶日 → 順延到 10-11（五）。"""
    assert rules.deadline_after(date(2024, 9, 10)) == (date(2024, 10, 10), date(2024, 10, 11))
    assert rules.check_deadline("113-09-10", "113-10-11")["pass"] is True


def test_deadline_end_before_lunar_new_year():
    """送達 114-12-29 → 第 30 日 115-01-28 是週三工作日，不順延；送達 115-01-17（六）→ 末日 115-02-16 除夕 → 順延到 2-23（一）。"""
    assert rules.deadline_after(date(2025, 12, 29))[1] == date(2026, 1, 28)
    assert rules.deadline_after(date(2026, 1, 17)) == (date(2026, 2, 16), date(2026, 2, 23))


@pytest.mark.parametrize("raw, expected", [
    ("1130902", date(2024, 9, 2)), ("20240902", date(2024, 9, 2)),
    ("02/09/2024", None),            # DD/MM/YYYY 不猜
    ("1913-09-20", None),            # 民國 79 年以前／不合理年份
    ("寄存送達 113年9月2日", date(2024, 9, 2)),
])
def test_parse_roc_date_more_forms(raw, expected):
    assert rules.parse_roc_date(raw) == expected


def test_deadline_same_day():
    assert rules.check_deadline("113-09-02", "113-09-02")["days"] == 0


def test_deadline_filed_before_served_needs_review():
    c = rules.check_deadline("113-09-05", "113-09-02")
    assert c["pass"] is False and c["needs_review"] is True and c["days"] == -3


def test_deadline_missing_dates():
    c = rules.check_deadline(None, "113-09-05")
    assert c["pass"] is False and c["needs_review"] is True and "送達日" in c["note"]
    c = rules.check_deadline("113-09-02", "")
    assert c["pass"] is False and "提起日" in c["note"]


def test_deadline_accepts_verbose_dates():
    c = rules.check_deadline("民國 113 年 9 月 2 日", "中華民國113年9月5日")
    assert c["pass"] is True and c["days"] == 3


# ---------------------------------------------------------------- 寄存送達
def test_deposit_service_uses_deposit_date():
    """寄存 8/25、本人 9/20 才領取、10/1 提起 → 以寄存日起算 37 天，逾期。"""
    c = rules.check_deadline(served="113-09-20", filed="113-10-01", service_method="deposit", deposit_date="113-08-25")
    assert c["served"] == "113-08-25" and c["days"] == 37 and c["pass"] is False
    assert "寄存" in c["note"] and "0930014628" in c["note"]


def test_deposit_service_within_deadline():
    c = rules.check_deadline(served=None, filed="113-09-20", service_method="deposit", deposit_date="113-09-01")
    assert c["pass"] is True and c["days"] == 19 and c["inputs"]["service_method"] == "deposit"


def test_deposit_without_deposit_date_falls_back_to_served_and_flags_review():
    c = rules.check_deadline(served="113-09-02", filed="113-09-05", service_method="deposit")
    assert c["pass"] is True and c["served"] == "113-09-02" and c["needs_review"] is True
    assert "未提供寄存日" in c["note"] and "寄存日（視為送達日）" not in c["note"]


@pytest.mark.parametrize("method", ["寄存送達", "寄存", "DEPOSIT", " deposit "])
def test_service_method_aliases(method):
    c = rules.check_deadline(served="113-09-20", filed="113-10-01", service_method=method, deposit_date="113-08-25")
    assert c["served"] == "113-08-25" and c["pass"] is False


def test_unknown_service_method_needs_review():
    c = rules.check_deadline(served="113-09-02", filed="113-09-05", service_method="鴿子")
    assert c["pass"] is True and c["needs_review"] is True and "無法辨識" in c["note"]


def test_deposit_date_with_direct_method_needs_review():
    c = rules.check_deadline(served="113-09-02", filed="113-09-05", service_method="direct", deposit_date="113-08-01")
    assert c["pass"] is True and c["needs_review"] is True and "寄存日" in c["note"]


# ---------------------------------------------------------------- 77(3) 當事人適格
def test_standing_same_person():
    c = rules.check_standing("王小明", "王小明")
    assert c["pass"] is True and c["note"] == "訴願人即處分相對人（王小明）" and c["rule"] == "訴願法77(3) 當事人適格"


def test_standing_masked_name_matches_but_needs_review():
    c = rules.check_standing("王○明", "王小明")
    assert c["pass"] is True and c["needs_review"] is True and "遮罩" in c["note"]
    c = rules.check_standing("王 小 明", "王小明")
    assert c["pass"] is True and c["needs_review"] is False


@pytest.mark.parametrize("addressee", ["王小明先生", "王小明。", "王 小 明", "王小明　"])
def test_standing_tolerates_suffix_space_punctuation(addressee):
    assert rules.check_standing("王小明", addressee)["pass"] is True


def test_standing_similar_but_different_format_needs_review():
    c = rules.check_standing("王小明", "王小明公司")
    assert c["pass"] is False and c["needs_review"] is True and "疑似同一人" in c["note"]


def test_standing_different_person_needs_review():
    c = rules.check_standing("王小明", "李大華")
    assert c["pass"] is False and c["needs_review"] is True and "77條第3款" in c["note"]


def test_standing_unknown_addressee_needs_review():
    c = rules.check_standing("王小明", None)
    assert c["pass"] is False and c["needs_review"] is True


def test_extract_addressee(disposition_text):
    assert rules.extract_addressee(disposition_text) == "王小明"
    assert rules.extract_addressee("受處分人：陳○任（下稱訴願人）") == "陳○任"
    assert rules.extract_addressee("受告誡人：王 小 明\n出生年月日：…") == "王小明"
    assert rules.extract_addressee("受處分人：王小明先生。") == "王小明"
    assert rules.extract_addressee("受告誡人：王小明　　出生年月日：民國 85 年") == "王小明"
    assert rules.extract_addressee("沒有欄位") is None
    assert rules.extract_addressee(None) is None


# ---------------------------------------------------------------- 77(8) 行政處分
@pytest.mark.parametrize("kind, ok, review", [
    ("書面告誡", True, False),
    ("告誡處分書", True, False),
    ("裁處書", True, False),
    ("罰鍰處分書", True, False),
    ("陳情回覆", False, False),
    ("函", False, True),
    ("通知", False, True),
    ("神秘文件", False, True),
    ("不予告誡通知書", False, True),
    ("撤銷告誡函", False, True),
    ("", False, True),
    (None, False, True),
])
def test_is_disposition(kind, ok, review):
    c = rules.check_is_disposition(kind)
    assert c["pass"] is ok and c["needs_review"] is review and c["rule"] == "訴願法77(8) 行政處分"


def test_is_disposition_note_matches_spec_example():
    assert rules.check_is_disposition("書面告誡")["note"] == "書面告誡為行政處分（洗防法22條2項）"


# ---------------------------------------------------------------- 行政程序法 96 條 撤銷前置檢核
def test_defects_none_for_113_16(disposition_text):
    check, flags = rules.check_defects(disposition_text)
    assert flags == [] and check["pass"] is True and check["category"] == "瑕疵"
    assert "事實" in check["inputs"]["sections_found"]


def test_defects_blank_facts_like_114_18():
    text = "新北市政府警察局中和分局 告誡處分書\n主旨：台端違反洗錢防制法第22條第1項。\n事實：\n\n理由及法令依據：\n一、洗錢防制法第22條第1項。\n"
    check, flags = rules.check_defects(text)
    assert [f["flag"] for f in flags] == ["facts_blank"]
    assert flags[0]["law"] == "行政程序法第96條第1項第2款" and "114" in flags[0]["note"]
    assert check["pass"] is False


def test_defects_missing_sections():
    check, flags = rules.check_defects("主旨：裁處告誡。\n")
    assert {f["flag"] for f in flags} == {"facts_missing", "reasons_missing", "legal_basis_missing"}


def test_defects_fallback_to_s2_when_no_text():
    check, flags = rules.check_defects(None, {"facts_by_agency": "", "disposition": {"legal_basis": []}})
    assert {f["flag"] for f in flags} == {"facts_blank", "legal_basis_missing"} and check["inputs"]["source"] == "S2 案件摘要"
    assert check["needs_review"] is True
    check, flags = rules.check_defects(None, {"facts_by_agency": "有事實", "disposition": {"legal_basis": ["洗錢防制法第22條"]}})
    assert flags == [] and check["needs_review"] is True


def test_check_procedure_tolerates_string_fields():
    r = rules.check_procedure({"appellant": "王小明", "disposition": "書面告誡", "served_date": "113-09-02", "petition_filed_date": "113-09-05"})
    assert [c["rule"] for c in r["checks"]][:3] == ["訴願法14條 30日", "訴願法77(3) 當事人適格", "訴願法77(8) 行政處分"]
    assert r["checks"][0]["pass"] is True and r["checks"][2]["needs_review"] is True


def test_parse_sections_multiline():
    s = rules.parse_disposition_sections("主旨：A\n事實：\n第一行\n第二行\n理由：B")
    assert s == {"主旨": "A", "事實": "第一行\n第二行", "理由": "B"}


def test_parse_sections_duplicate_label_merges_not_overwrites():
    s = rules.parse_disposition_sections("事實：有內容\n理由：X\n（附件）\n事實：\n理由：")
    assert s["事實"] == "有內容" and s["理由"].startswith("X")
    check, flags = rules.check_defects("主旨：告誡\n事實：有內容\n理由：洗錢防制法第 22 條\n事實：\n")
    assert flags == []


def test_defects_letter_form_disposition_needs_review_not_flags():
    text = "主旨：台端違反洗錢防制法第22條第1項，裁處告誡。\n說明：\n一、台端於 113 年 8 月 1 日交付提款卡…\n二、依洗錢防制法第22條第2項。"
    check, flags = rules.check_defects(text)
    assert flags == [] and check["pass"] is True and check["needs_review"] is True and "函形式" in check["note"]


def test_defects_reasons_label_variants():
    text = "主旨：A\n事實：B\n理由及法令依據：\n理由：依洗錢防制法第 22 條第 1 項\n"
    check, flags = rules.check_defects(text)
    assert flags == [], check


# ---------------------------------------------------------------- 整合：S2 → S2.5
def test_check_procedure_113_16(s2_113_16, disposition_text):
    r = rules.check_procedure(s2_113_16, disposition_text)
    assert r["admissible"] is True and r["needs_review"] == [] and r["defect_flags"] == []
    rules_ = [c["rule"] for c in r["checks"]]
    assert rules_[:3] == ["訴願法14條 30日", "訴願法77(3) 當事人適格", "訴願法77(8) 行政處分"]
    for c in r["checks"]:
        assert set(c) >= {"rule", "pass", "note", "inputs"}
    assert r["checks"][0]["days"] == 3 and r["checks"][0]["served"] == "113-09-02" and r["checks"][0]["filed"] == "113-09-05"


def test_check_procedure_late_petition_not_admissible(s2_113_16, disposition_text):
    s2 = {**s2_113_16, "petition_filed_date": "113-10-15"}
    r = rules.check_procedure(s2, disposition_text)
    assert r["admissible"] is False and r["checks"][0]["pass"] is False


def test_check_procedure_deposit_from_s2(s2_113_16, disposition_text):
    s2 = {**s2_113_16, "service_method": "deposit", "deposit_date": "113-08-01", "petition_filed_date": "113-09-05"}
    r = rules.check_procedure(s2, disposition_text)
    assert r["checks"][0]["served"] == "113-08-01" and r["checks"][0]["pass"] is False


def test_check_procedure_addressee_from_text_when_s2_lacks_it(s2_113_16, disposition_text):
    s2 = {**s2_113_16, "disposition": {k: v for k, v in s2_113_16["disposition"].items() if k != "addressee"}}
    r = rules.check_procedure(s2, disposition_text)
    assert r["checks"][1]["pass"] is True and r["checks"][1]["inputs"]["addressee"] == "王小明"


def test_check_procedure_defect_does_not_affect_admissible(s2_113_16):
    blank = "主旨：告誡。\n事實：\n理由：X\n法令依據：洗錢防制法第22條\n"
    r = rules.check_procedure(s2_113_16, blank)
    assert r["admissible"] is True and [f["flag"] for f in r["defect_flags"]] == ["facts_blank"]
    assert r["checks"][3]["pass"] is False
