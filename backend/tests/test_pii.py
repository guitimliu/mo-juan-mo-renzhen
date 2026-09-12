# -*- coding: utf-8 -*-
"""個資前處理（取代法）：S1 後遮罩、S4 後還原；對照表不進 envelope。"""
import asyncio
import json

import pytest

from app import pii, pipeline, settings
from app.adapters import stub
from app.adapters.base import AdapterSet
from app.store import CaseStore

PETITION = ("訴願書\n訴願人：王小明　出生年月日：民國 85 年 3 月 12 日\n住址：新北市新店區北新路二段88號5樓　電話：0912-345-678\n"
            "原處分機關：新北市政府警察局新店分局\n代理人：李大華\n一、訴願人被騙……。\n收受原處分日期：113 年 9 月 2 日\n訴願人：王小明（簽名）\n中華民國 113 年 9 月 5 日")
DISPOSITION = ("新北市政府警察局新店分局 書面告誡\n受告誡人：王小明\n身分證統一編號：A123456789\n住址：新北市新店區北新路二段88號5樓\n"
               "主旨：台端違反洗錢防制法第22條第1項規定。\n事實：嗣陳○超等6名被害人遭詐騙……王小明坦承上情。\n理由及法令依據：略。")


def test_detect_and_apply_masks_all_categories():
    m = pii.detect([PETITION, DISPOSITION])
    assert m.names == {"王小明": "甲○○", "李大華": "乙○○"}            # 依出現順序給代號；陳○超已遮罩不動
    out_p, out_d = pii.apply(PETITION, m), pii.apply(DISPOSITION, m)
    for real in ("王小明", "李大華", "A123456789", "0912-345-678", "北新路二段88號5樓", "3 月 12 日"):
        assert real not in out_p and real not in out_d
    assert "甲○○" in out_p and "受告誡人：甲○○" in out_d and "陳○超" in out_d
    assert "民國 85年○月○日" in out_p and "新北市新店區○○路○段○○號" in out_p and "A1○○○○○○○○" in out_d
    assert "新北市政府警察局新店分局" in out_d                            # 機關名不是個資
    pii.count_applied(PETITION, out_p, m); pii.count_applied(DISPOSITION, out_d, m)
    s = m.summary()
    assert s["codes"] == ["乙○○", "甲○○"] and s["replaced"]["name"] == 5 and s["replaced"]["id"] == 1 and s["replaced"]["dob"] == 1
    assert "王小明" not in json.dumps(s, ensure_ascii=False)               # 摘要不含原值


def test_restore_only_names():
    m = pii.detect([PETITION, DISPOSITION])
    draft = {"header": {"appellant": "甲○○"}, "facts": "緣甲○○於……乙○○代理", "reasons": ["一、甲○○主張", "A1○○○○○○○○"]}
    r = pii.restore(draft, m)
    assert r["header"]["appellant"] == "王小明" and r["facts"] == "緣王小明於……李大華代理" and r["reasons"] == ["一、王小明主張", "A1○○○○○○○○"]


def test_no_pii_is_noop():
    m = pii.detect(["主旨：略。", ""])
    assert not m.enabled and pii.apply("主旨：略。", m) == "主旨：略。" and pii.restore({"a": "b"}, m) == {"a": "b"}


class _OCR:
    async def run(self, case_id, images):
        return {"case_id": case_id, "petition_text": PETITION, "disposition_text": DISPOSITION, "ocr_confidence_note": "test"}


class _Extract:
    def __init__(self): self.seen = None
    async def run(self, s1):
        self.seen = s1
        return {"appellant": {"name": "甲○○"}, "agency": "新北市政府警察局新店分局", "disposition": {"type": "書面告誡", "addressee": "甲○○", "legal_basis": ["洗錢防制法第22條第1項"]},
                "served_date": "113-09-02", "petition_filed_date": "113-09-05", "case_type": "違反洗錢防制法事件", "facts_by_agency": "x", "appellant_claims": [], "issues": []}


class _Gen:
    async def run(self, s2, s2_5, s3):
        return {"header": {"appellant": s2["appellant"]["name"]}, "holding": "訴願駁回。", "facts": f"緣{s2['appellant']['name']}……", "reasons": ["一、按", "二、綜上論結，依訴願法第79條第1項"], "instruction": "", "citations": [], "gaps": []}


def _run(monkeypatch, mask):
    monkeypatch.setattr(settings, "PII_MASK", "1" if mask else "0")
    store = CaseStore()
    ext = _Extract()
    adapters = AdapterSet(mode="bedrock", ocr=_OCR(), extract=ext, retrieval=stub.StubRetrieval(), generate=_Gen())
    case = store.create("bedrock", [], None)
    asyncio.run(pipeline.run_case(case.case_id, store, adapters, delay_s=0))
    return case, ext


def test_pipeline_masks_before_model_and_restores_draft(monkeypatch):
    case, ext = _run(monkeypatch, mask=True)
    env = case.to_envelope()
    assert env["status"] == "done", env["error"]
    # 送進 Extract（＝送模型）的 S1 已無真名／身分證，且 envelope 的 S1 也是遮罩版
    assert "王小明" not in json.dumps(ext.seen, ensure_ascii=False) and "A123456789" not in json.dumps(ext.seen, ensure_ascii=False)
    assert "甲○○" in env["stages"]["S1"]["data"]["petition_text"] and env["stages"]["S1"]["data"]["pii_note"].startswith("已去識別化")
    # 規則引擎用代號比對仍通過
    assert env["stages"]["S2_5"]["data"]["admissible"] is True
    # S4 還原真名；S2 保持代號（就是送出去的樣子）
    assert env["stages"]["S4"]["data"]["header"]["appellant"] == "王小明" and env["stages"]["S4"]["data"]["facts"].startswith("緣王小明")
    assert env["stages"]["S2"]["data"]["appellant"]["name"] == "甲○○"
    # envelope 摘要有類別筆數、無原值；對照表不在 envelope
    assert env["pii"]["codes"] == ["乙○○", "甲○○"] and env["pii"]["replaced"]["name"] >= 4
    assert "王小明" not in json.dumps({k: v for k, v in env.items() if k != "stages"}, ensure_ascii=False)


def test_pipeline_mask_off(monkeypatch):
    case, ext = _run(monkeypatch, mask=False)
    env = case.to_envelope()
    assert env["pii"] is None and "王小明" in ext.seen["petition_text"] and "pii_note" not in env["stages"]["S1"]["data"]


def test_stub_mode_default_off():
    assert settings.pii_enabled("stub") is False and settings.pii_enabled("bedrock") is True
