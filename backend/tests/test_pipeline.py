# -*- coding: utf-8 -*-
"""用 stub 跑 113-16 → 檢核 30/30（不帶 retrieval）、30/31（帶 stub retrieval）；失敗傳播；envelope 形狀。"""
import asyncio
import json
import re

import pytest

from app import checker, pipeline, rules
from app.adapters import stub
from app.adapters.base import AdapterSet, UploadedImage
from app.store import STAGES


def run(store, adapters, images):
    case = store.create(adapters.mode, images)
    asyncio.run(pipeline.run_case(case.case_id, store, adapters, delay_s=0))
    return case


def test_stub_pipeline_scores(store, adapters, images):
    case = run(store, adapters, images)
    env = case.to_envelope()
    assert env["status"] == "done" and env["current_stage"] is None and env["error"] is None
    assert all(env["stages"][s]["status"] == "done" for s in STAGES)
    s3, s4, s5 = (env["stages"][s]["data"] for s in ("S3", "S4", "S5"))
    assert s5["score"]["總分"] == "30/31"
    failed = [c for c in s5["checks"] if not c["pass"]]
    assert len(failed) == 1 and failed[0]["item"].startswith("引用判決皆在檢索結果內")
    assert checker.check(s4)["score"]["總分"] == "30/30"          # 不帶 retrieval
    assert checker.check(s4, s3)["score"]["總分"] == "30/31"      # 帶 stub retrieval


def test_s1_s2_from_workpackage(store, adapters, images):
    case = run(store, adapters, images)
    s1, s2 = case.stages["S1"].data, case.stages["S2"].data
    assert s1["case_id"] == case.case_id and s1["petition_text"].startswith("訴　願　書") and "#" not in s1["petition_text"]
    assert s1["ocr_confidence_note"].startswith("stub：未實際辨識") and "a.jpg" in s1["ocr_confidence_note"]
    assert s2["served_date"] == "113-09-02" and s2["petition_filed_date"] == "113-09-05"
    assert s2["appellant"]["name"] == "王小明" and s2["disposition"]["doc_no"] == "新北警店刑字第1134082840號"
    assert s2["appellant"]["address"] != "…" and s2["facts_by_agency"].startswith("台端於民國 113 年 8 月 1 日")


def test_s2_5_is_rules_output(store, adapters, images):
    case = run(store, adapters, images)
    s25 = case.stages["S2_5"].data
    assert s25["admissible"] is True and [c["pass"] for c in s25["checks"]] == [True] * 4
    assert s25["checks"][0]["days"] == 3


def test_s3_contents(store, adapters, images):
    s3 = run(store, adapters, images).stages["S3"].data
    statutes = {(s["law"], s["article"]): s for s in s3["statutes"]}
    assert ("洗錢防制法", "22") in statutes and ("訴願法", "79") in statutes
    assert "任何人不得將自己或他人向金融機構申請開立之帳戶" in statutes[("洗錢防制法", "22")]["text"]
    assert "（第2項）" in statutes[("洗錢防制法", "22")]["text"] and statutes[("洗錢防制法", "22")]["version_date"] == "113-07-31"
    assert "訴願無理由者，受理訴願機關應以決定駁回之" in statutes[("訴願法", "79")]["text"]
    ids = {p["id"] for p in s3["precedents"]}
    assert {"最高行政法院108年度判字第531號", "最高行政法院109年度上字第780號"} <= ids
    assert all("故意" in p["excerpt"] for p in s3["precedents"] if "最高" in p["id"])
    assert [i["id"] for i in s3["interpretations"]] == ["洗錢防制法第15條之2立法理由第3點", "洗錢防制法第15條之2立法理由第5點"]
    assert s3["interpretations"][0]["excerpt"].startswith("三、本條所謂交付") and s3["interpretations"][1]["excerpt"].startswith("五、現行實務常見")
    sim = {c["id"]: c for c in s3["similar_cases"]}
    assert sim["113-15"]["result"] == "駁回" and sim["114-18"]["result"] == "撤銷"
    for c in s3["similar_cases"]:
        assert set(c) >= {"id", "result", "why_similar", "score"}


def test_s4_citations_follow_appendix_b(store, adapters, images):
    case = run(store, adapters, images)
    s3, s4 = case.stages["S3"].data, case.stages["S4"].data
    assert s4["holding"] == "訴願駁回。" and s4["instruction"].startswith("如不服本決定") and "臺北高等行政法院" in s4["instruction"]
    assert set(s4["header"]) >= {"case_type", "appellant", "agency", "disposition_ref"}
    assert s4["citations"], "必須有 citations"
    for c in s4["citations"]:
        assert set(c) >= {"text", "source", "section", "index"}
        assert c["section"] in ("facts", "reasons", "instruction")
        m = re.fullmatch(r"(statutes|precedents|interpretations|similar_cases)\[(\d+)\]", c["source"])
        assert m and int(m[2]) < len(s3[m[1]]), c
        paragraph = s4["reasons"][c["index"]] if c["section"] == "reasons" else s4[c["section"]]
        assert c["section"] != "reasons" or 0 <= c["index"] < len(s4["reasons"])
        key = re.findall(r"第\d+條之\d+|立法理由第\d+點", c["text"]) or [c["text"]]
        assert all(k in re.sub(r"\s+", "", paragraph) for k in key), c
    sources = {c["source"] for c in s4["citations"]}
    assert {"statutes[0]", "statutes[1]", "interpretations[0]", "interpretations[1]"} <= sources
    assert any(c["text"] == "訴願法第79條第1項" and c["section"] == "reasons" and c["index"] == 3 for c in s4["citations"])
    assert len(s4["gaps"]) == 3 and all(g.startswith("需承辦人補查：") for g in s4["gaps"])
    assert s4["provenance"].startswith("stub：")


def test_s5_summary_follows_appendix_c(store, adapters, images):
    s5 = run(store, adapters, images).stages["S5"].data
    assert set(s5) == {"checks", "score", "summary"}
    s = s5["summary"]
    assert s["sections_present"] == {"主文": True, "事實": True, "理由": True, "教示": True}
    assert s["citation_total"] == s["citation_grounded"] > 0 and s["holding_match"] is True
    assert "洗錢防制法第22條第1項" in s["gold_citations_recalled"]
    assert s["gold_citations_missed"] == ["臺北高等行政法院113年度簡字第243號", "高雄高等行政法院113年度簡字第125號", "臺中高等行政法院113年度簡字第21號"]


def test_envelope_shape(store, adapters, images):
    env = run(store, adapters, images).to_envelope()
    assert set(env) == {"case_id", "status", "current_stage", "adapter_mode", "created_at", "updated_at", "stages", "error"}
    assert list(env["stages"]) == list(STAGES) and env["adapter_mode"] == "stub"
    for st in env["stages"].values():
        assert set(st) == {"status", "data", "error", "elapsed_ms"} and isinstance(st["elapsed_ms"], int)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+08:00", env["created_at"])


# ---------------------------------------------------------------- 失敗傳播
class Boom:
    async def run(self, *a, **k):
        raise RuntimeError("boom")


def test_retrieval_failure_skips_dependents_only(store, adapters, images):
    broken = AdapterSet(mode="stub", ocr=adapters.ocr, extract=adapters.extract, retrieval=Boom(), generate=adapters.generate)
    env = run(store, broken, images).to_envelope()
    st = {k: v["status"] for k, v in env["stages"].items()}
    assert st == {"S1": "done", "S2": "done", "S2_5": "done", "S3": "error", "S4": "skipped", "S5": "skipped"}
    assert env["status"] == "error" and "S3" in env["error"] and "boom" in env["stages"]["S3"]["error"]
    assert "S3" in env["stages"]["S4"]["error"] and env["current_stage"] is None


def test_ocr_failure_skips_everything(store, adapters, images):
    broken = AdapterSet(mode="stub", ocr=Boom(), extract=adapters.extract, retrieval=adapters.retrieval, generate=adapters.generate)
    env = run(store, broken, images).to_envelope()
    assert env["stages"]["S1"]["status"] == "error"
    assert all(env["stages"][s]["status"] == "skipped" for s in STAGES if s != "S1")


class _FakeBedrockClient:
    """假的 bedrock-runtime client：記錄請求，依第幾次呼叫回不同的 OCR JSON。"""

    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def converse(self, **kwargs):
        self.calls.append(kwargs)
        text = self.replies.pop(0)
        return {"output": {"message": {"role": "assistant", "content": [{"text": text}]}},
                "usage": {"inputTokens": 1, "outputTokens": 1}}


def _fake_ocr(replies):
    from app.adapters import bedrock
    bedrock.limiter.min_interval_s = 0            # 測試不等 1 RPS
    return bedrock.BedrockOCR(client=_FakeBedrockClient(replies))


def test_bedrock_ocr_builds_s1_from_converse(images):
    import json
    ocr = _fake_ocr([json.dumps({"text": "訴願書全文", "low_confidence": ["1134082840"], "note": "手寫"}),
                     "```json\n" + json.dumps({"text": "告誡全文", "low_confidence": []}) + "\n```"])
    s1 = asyncio.run(ocr.run("poc-x", images))
    assert s1["case_id"] == "poc-x"
    assert s1["petition_text"] == "訴願書全文" and s1["disposition_text"] == "告誡全文"
    assert "手寫" in s1["ocr_confidence_note"] and "「1134082840」" in s1["ocr_confidence_note"]
    calls = ocr.client.calls
    assert len(calls) == 2 and all(c["modelId"] == ocr.model_id for c in calls)
    img_blocks = [b for b in calls[0]["messages"][0]["content"] if "image" in b]
    assert img_blocks == [{"image": {"format": "jpeg", "source": {"bytes": b"\xff\xd8\xff"}}}]


def test_bedrock_ocr_tolerates_non_json_reply(images):
    ocr = _fake_ocr(["這不是 JSON 只是全文", "{}"])
    s1 = asyncio.run(ocr.run("poc-y", images))
    assert s1["petition_text"] == "這不是 JSON 只是全文"
    assert s1["disposition_text"] == "{}"
    assert "未回 JSON" in s1["ocr_confidence_note"]


def test_bedrock_ocr_groups_pages_and_reports_missing_field():
    ocr = _fake_ocr(['{"text": "p1+p2", "low_confidence": []}'])
    pages = [UploadedImage("petition_image", f"{n}.png", "image/png", 1, b"x") for n in (1, 2)]
    s1 = asyncio.run(ocr.run("poc-z", pages))
    assert s1["petition_text"] == "p1+p2" and s1["disposition_text"] == ""
    assert "原處分（書面告誡）：未上傳" in s1["ocr_confidence_note"]
    content = ocr.client.calls[0]["messages"][0]["content"]
    assert sum("image" in b for b in content) == 2


def test_bedrock_extract_normalizes_and_backfills(disposition_text):
    from app.adapters import bedrock
    bedrock.limiter.min_interval_s = 0
    reply = json.dumps({
        "appellant": {"name": "王小明", "dob": "民國85年3月12日"},
        "agency": "新北市政府警察局新店分局",
        "disposition": {"date": "113/9/1", "doc_no": "新北警店刑字第1134082840號", "type": "書面告誡",
                        "legal_basis": "洗錢防制法第22條第1項"},         # 字串而非陣列、缺 addressee
        "served_date": "中華民國 113 年 9 月 2 日", "service_method": "DIRECT",
        "petition_filed_date": None,                                       # 讓後處理從訴願書補
        "case_type": "違反洗錢防制法事件", "facts_by_agency": "",        # 讓後處理從處分書補
        "appellant_claims": ["遭詐騙不知情"], "issues": ["正當理由範圍"],
    }, ensure_ascii=False)
    ext = bedrock.BedrockExtract(client=_FakeBedrockClient([reply]))
    s1 = {"petition_text": stub.poc_document("01_模擬訴願書.md"), "disposition_text": disposition_text, "ocr_confidence_note": "x"}
    s2 = asyncio.run(ext.run(s1))
    assert s2["appellant"]["dob"] == "085-03-12" and s2["disposition"]["date"] == "113-09-01"
    assert s2["served_date"] == "113-09-02" and s2["petition_filed_date"] == "113-09-05"
    assert s2["service_method"] == "direct" and s2["deposit_date"] is None
    assert s2["disposition"]["legal_basis"] == ["洗錢防制法第22條第1項"]
    assert s2["disposition"]["addressee"] == "王小明"
    assert s2["facts_by_agency"].startswith("台端於民國 113 年 8 月 1 日")
    assert s2["uncertain"] == []
    s25 = rules.check_procedure(s2, disposition_text)
    assert s25["admissible"] is True and s25["needs_review"] == []
    prompt = ext.client.calls[0]["messages"][0]["content"][0]["text"]
    assert "訴願書（OCR 全文）" in prompt and disposition_text[:20] in prompt


def test_bedrock_extract_rejects_non_json():
    from app.adapters import bedrock
    bedrock.limiter.min_interval_s = 0
    ext = bedrock.BedrockExtract(client=_FakeBedrockClient(["我不想輸出 JSON"]))
    with pytest.raises(ValueError, match="未回 JSON"):
        asyncio.run(ext.run({"petition_text": "a", "disposition_text": "b"}))


class _FakeAgentClient:
    """假的 bedrock-agent-runtime：依 filter 的 category 回不同 chunk。"""

    def __init__(self, by_category):
        self.by_category, self.calls = by_category, []

    def retrieve(self, **kw):
        self.calls.append(kw)
        cat = kw["retrievalConfiguration"]["vectorSearchConfiguration"].get("filter", {}).get("equals", {}).get("value")
        return {"retrievalResults": [
            {"content": {"text": t}, "score": sc, "location": {"s3Location": {"uri": u}}, "metadata": md}
            for t, sc, u, md in self.by_category.get(cat, [])]}


_KB = "s3://mo-juan-mo-renzhen-kb-text/"
_LR_QUOTE = ("行為時洗錢防制法第15條之2增訂之立法理由略以：「……二、於第1項定明任何人除基於正當理由以外不得交付帳戶之法定義務。"
             "三、本條所謂交付、提供帳戶、帳號予他人使用，係指將帳戶、帳號之控制權交予他人。五、現行實務常見以申辦貸款、應徵工作等方式要求他人交付人頭帳戶。」")
_CHUNKS = {
    "precedent": [
        (_LR_QUOTE, 0.77, _KB + "司法院釋字及行政判解/臺北高等行政法院114年度簡上字第13號判決-洗錢防制法第22條.txt",
         {"category": "precedent", "title": "臺北高等行政法院114年度簡上字第13號判決-洗錢防制法第22條"}),
        ("資訊分離原則……", 0.73, _KB + "司法院釋字及行政判解/最高行政法院106年度判字第557號行政判決-資訊分離原則.txt",
         {"category": "precedent", "title": "最高行政法院106年度判字第557號行政判決-資訊分離原則"}),
    ],
    "interpretation": [
        ("任何人明知或可得而知無正當理由交付帳戶者，由警察機關裁處告誡……", 0.72, _KB + "行政函釋/法務部113年10月17日法律字11303514230號函-行政程序第128條第2款程序再開.txt",
         {"category": "interpretation", "title": "法務部113年10月17日法律字11303514230號函-行政程序第128條第2款程序再開"}),
    ],
    "decision": [
        ("本案答辯……", 0.86, _KB + "歷史訴願決定書/113年/16.txt", {"category": "decision", "doc_no": "113-16"}),   # 本案自己，要排除
        ("訴願人主張……", 0.80, _KB + "歷史訴願決定書/113年/18.txt", {"category": "decision", "doc_no": "113-18"}),
        ("訴願人主張……第二段", 0.79, _KB + "歷史訴願決定書/113年/18.txt", {"category": "decision", "doc_no": "113-18"}),   # 同一件第二個 chunk
        ("……", 0.78, _KB + "歷史訴願決定書/113年/15.txt", {"category": "decision", "doc_no": "113-15"}),
        ("……", 0.70, _KB + "歷史訴願決定書/113年/99.txt", {"category": "decision", "doc_no": "999-99"}),           # petitions.jsonl 沒有 → 略過
    ],
}


def _s2_113_16():
    return {"case_type": "違反洗錢防制法事件", "facts_by_agency": "交付提款卡", "appellant_claims": ["受騙"], "issues": ["正當理由"],
            "disposition": {"doc_no": "新北警店刑字第1134082840號", "legal_basis": ["洗錢防制法第22條第1項", "洗錢防制法第22條第2項"]}}


def test_bedrock_retrieval_assembles_s3():
    from app.adapters import bedrock
    bedrock.limiter.min_interval_s = 0
    screen = json.dumps({"keep_precedents": ["臺北高等行政法院114年度簡上字第13號"], "keep_interpretations": [],
                         "why_similar": {"113-18": "同為交付帳戶、主張受騙"}}, ensure_ascii=False)
    r = bedrock.BedrockRetrieval(agent_client=_FakeAgentClient(_CHUNKS), client=_FakeBedrockClient([screen]))
    s3 = asyncio.run(r.run(_s2_113_16()))
    # 三次 retrieve 各帶 category filter
    cats = [c["retrievalConfiguration"]["vectorSearchConfiguration"]["filter"]["equals"]["value"] for c in r.agent_client.calls]
    assert cats == ["precedent", "interpretation", "decision"]
    # 法條：處分依據 + 相似案的訴願法條，且都查得到全文
    assert [(x["law"], x["article"]) for x in s3["statutes"]][:1] == [("洗錢防制法", "22")]
    assert all(x["text"] and x["version_date"] for x in s3["statutes"])
    assert {("訴願法", "79"), ("訴願法", "81")} & {(x["law"], x["article"]) for x in s3["statutes"]}
    # 判解：無關的被篩掉；id／topic 從檔名切
    assert [p["id"] for p in s3["precedents"]] == ["臺北高等行政法院114年度簡上字第13號"]
    assert s3["precedents"][0]["topic"] == "洗錢防制法第22條"
    # 函釋被篩掉，但立法理由引文從判決原文抽出來
    assert [i["id"] for i in s3["interpretations"]] == [f"洗錢防制法第15條之2立法理由第{n}點" for n in (2, 3, 5)]
    assert s3["interpretations"][1]["excerpt"].startswith("本條所謂交付")
    # 相似案：排除 113-16 本案、同件多 chunk 合併、petitions.jsonl 沒有的略過、why_similar 有回就用、沒回用固定句
    assert [x["id"] for x in s3["similar_cases"]] == ["113-18", "113-15"]
    assert s3["similar_cases"][0]["why_similar"] == "同為交付帳戶、主張受騙" and s3["similar_cases"][0]["result"] in ("撤銷", "駁回", "不受理")
    assert s3["similar_cases"][1]["why_similar"].startswith("同為")
    assert "113-16" in s3["note"]
    # 附錄 B／S5：正本改寫的草稿配這份 S3，gold 法條與立法理由都被涵蓋
    s4 = asyncio.run(stub.StubGenerate().run(_s2_113_16(), {}, s3))
    summary = checker.run(s4, s3)["summary"]
    assert "洗錢防制法第15條之2立法理由第3點" in summary["gold_citations_recalled"]
    assert summary["citation_grounded"] == summary["citation_total"]


def test_bedrock_retrieval_survives_bad_screen_reply():
    from app.adapters import bedrock
    bedrock.limiter.min_interval_s = 0
    r = bedrock.BedrockRetrieval(agent_client=_FakeAgentClient(_CHUNKS), client=_FakeBedrockClient(["not json"]))
    s3 = asyncio.run(r.run(_s2_113_16()))
    assert len(s3["precedents"]) == 2 and s3["similar_cases"][0]["why_similar"].startswith("同為")   # 篩選失敗 → 全留


def _s4_reply(holding="訴願駁回。"):
    """假的 Generate 回覆：模仿模型常見的偏差（reasons 回物件、holding 多空白、header 亂填）。"""
    return json.dumps({
        "header": {"case_type": "亂填", "appellant": "亂填", "agency": "亂填", "disposition_ref": "亂填"},
        "holding": holding,
        "facts": "緣訴願人交付提款卡……訴願人不服，提起本件訴願，並據原處分機關檢卷答辯到府。茲摘敘訴辯意旨於次：一、訴願意旨略謂：受騙等語。二、答辯意旨略謂：坦承等語。",
        "reasons": [{"number": "一", "content": "按洗錢防制法第22條第1項規定：「…」。"},
                    "卷查訴願人交付提款卡，此有113年8月17日調查筆錄附卷可稽。",
                    "三、至訴願人主張受騙等語。惟查：洗錢防制法第15條之2立法理由第3點載明控制權（臺北高等行政法院114年度簡上字第13號判決參照），另臺北高等行政法院113年度簡字第243號判決亦同，尚難採據。",
                    "綜上論結，本件訴願為無理由，依訴願法第79條第1項規定，決定如主文。"],
        "instruction": "模型自己寫的教示（會被規則覆寫）",
        "citations": [{"text": "幻覺法第1條", "source": "statutes[9]"}],
        "gaps": ["需承辦人補查：模型自己標的"],
    }, ensure_ascii=False)


def _s3_fixture():
    from app.adapters import bedrock
    bedrock.limiter.min_interval_s = 0
    screen = json.dumps({"keep_precedents": ["臺北高等行政法院114年度簡上字第13號"], "keep_interpretations": [], "why_similar": {}}, ensure_ascii=False)
    r = bedrock.BedrockRetrieval(agent_client=_FakeAgentClient(_CHUNKS), client=_FakeBedrockClient([screen]))
    return asyncio.run(r.run(_s2_113_16()))


def test_bedrock_generate_rules_override_model(disposition_text):
    from app.adapters import bedrock
    s2 = {**_s2_113_16(), "appellant": {"name": "王小明"}, "agency": "新北市政府警察局新店分局",
          "disposition": {**_s2_113_16()["disposition"], "date": "113-09-01", "type": "書面告誡", "addressee": "王小明"},
          "served_date": "113-09-02", "petition_filed_date": "113-09-05"}
    s2_5 = rules.check_procedure(s2, disposition_text)
    s3 = _s3_fixture()
    g = bedrock.BedrockGenerate(client=_FakeBedrockClient([_s4_reply(" 訴願駁回。 ")]))
    s4 = asyncio.run(g.run(s2, s2_5, s3))
    assert s4["outcome"]["outcome"] == "駁回" and s4["holding"] == "訴願駁回。"
    assert s4["header"] == {"case_type": "違反洗錢防制法事件", "appellant": "王小明", "agency": "新北市政府警察局新店分局",
                            "disposition_ref": "113年9月1日新北警店刑字第1134082840號"}
    assert "臺北高等行政法院" in s4["instruction"] and "2 個月" in s4["instruction"]
    assert [r[:2] for r in s4["reasons"]] == ["一、", "二、", "三、", "四、"] and s4["reasons"][0].startswith("一、按")
    # citations 只認檢索結果裡有的（模型的幻覺引用被丟掉），source 用附錄 B 格式
    assert all(re.match(r"(statutes|precedents|interpretations|similar_cases)\[\d+\]$", c["source"]) for c in s4["citations"])
    assert not any("幻覺" in c["text"] for c in s4["citations"])
    assert {"洗錢防制法第22條第1項", "訴願法第79條第1項", "洗錢防制法第15條之2立法理由第3點", "臺北高等行政法院114年度簡上字第13號"} <= {c["text"] for c in s4["citations"]}
    # gaps：本文引了但檢索沒有的判決 + 模型自己標的
    assert any("113年度簡字第243號" in g for g in s4["gaps"]) and "需承辦人補查：模型自己標的" in s4["gaps"]
    # system prompt 帶 09＋04＋05
    sysmsg = g.client.calls[0]["system"][0]["text"]
    assert "訴願審議承辦人" in sysmsg and "決定書模板" in sysmsg and "113-15" in sysmsg
    assert "駁回版" in g.client.calls[0]["messages"][0]["content"][0]["text"]
    # S5 能跑且 gold 法條／立法理由 recalled
    summary = checker.run(s4, s3)["summary"]
    assert summary["holding_match"] and "洗錢防制法第15條之2立法理由第3點" in summary["gold_citations_recalled"]


def test_bedrock_generate_outcome_follows_procedure_check():
    from app.adapters import bedrock
    assert bedrock.decide_outcome({"admissible": True, "defect_flags": []})["outcome"] == "駁回"
    assert bedrock.decide_outcome({"admissible": True, "defect_flags": [{"flag": "facts_blank", "note": "事實欄空白"}]})["outcome"] == "撤銷"
    late = bedrock.decide_outcome({"admissible": False, "checks": [{"rule": "訴願法14條 30日", "category": "程序", "pass": False, "needs_review": False, "note": "逾期"}]})
    assert late["outcome"] == "不受理" and late["clause"] == "2"
    # 撤銷：主文限定在模板句、不附教示
    s3 = _s3_fixture()
    g = bedrock.BedrockGenerate(client=_FakeBedrockClient([_s4_reply("原處分撤銷啦")]))
    s4 = asyncio.run(g.run(_s2_113_16(), {"admissible": True, "defect_flags": [{"flag": "facts_blank", "note": "事實欄空白"}]}, s3))
    assert s4["holding"] == "原處分撤銷，由原處分機關於2個月內另為適法之處分。" and s4["instruction"] == ""


def test_bedrock_full_pipeline_all_stages_done(store, images):
    from app.adapters import bedrock
    from app.adapters.base import AdapterSet
    s2_reply = json.dumps({"appellant": {"name": "王小明"}, "agency": "新北市政府警察局新店分局",
                           "disposition": {"date": "113-09-01", "doc_no": "新北警店刑字第1134082840號", "type": "書面告誡", "addressee": "王小明", "legal_basis": ["洗錢防制法第22條第1項"]},
                           "served_date": "113-09-02", "petition_filed_date": "113-09-05", "case_type": "違反洗錢防制法事件",
                           "facts_by_agency": "交付提款卡", "appellant_claims": ["受騙"], "issues": ["正當理由"]}, ensure_ascii=False)
    adapters = AdapterSet(mode="bedrock", ocr=_fake_ocr(['{"text":"a"}', '{"text":"b"}']),
                          extract=bedrock.BedrockExtract(client=_FakeBedrockClient([s2_reply])),
                          retrieval=bedrock.BedrockRetrieval(agent_client=_FakeAgentClient(_CHUNKS), client=_FakeBedrockClient(["{}"])),
                          generate=bedrock.BedrockGenerate(client=_FakeBedrockClient([_s4_reply()])))
    env = run(store, adapters, images).to_envelope()
    assert env["adapter_mode"] == "bedrock" and env["status"] == "done", env["error"]
    assert all(env["stages"][s]["status"] == "done" for s in STAGES)
    assert env["stages"]["S3"]["data"]["statutes"][0]["article"] == "22"
    assert env["stages"]["S4"]["data"]["holding"] == "訴願駁回。"
    assert env["stages"]["S5"]["data"]["summary"]["holding_match"] is True
