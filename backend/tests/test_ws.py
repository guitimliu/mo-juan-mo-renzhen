# -*- coding: utf-8 -*-
"""WebSocket 即時進度：envelope 隨階段推送、progress／delta 轉發、串流生成、驗證。"""
import asyncio
import json

from fastapi.testclient import TestClient

from app import auth, events
from app.adapters import bedrock, stub
from app.adapters.base import AdapterSet
from app.main import create_app
from tests.test_pipeline import _FakeAgentClient, _FakeBedrockClient, _CHUNKS, _s4_reply, _fake_ocr


def files():
    return {"petition_image": ("a.jpg", b"\xff\xd8\xff", "image/jpeg"), "disposition_image": ("b.jpg", b"\xff\xd8\xff", "image/jpeg")}


def test_ws_streams_envelopes_until_done(monkeypatch):
    monkeypatch.setattr(auth, "USERNAME", "")
    c = TestClient(create_app(delay_s=0.05))                 # stub 每階段 50 ms，讓 WS 有機會看到中間狀態
    cid = c.post("/api/cases", files=files()).json()["case_id"]
    seen = []
    with c.websocket_connect(f"/api/cases/{cid}/ws") as ws:
        while True:
            msg = ws.receive_json()
            seen.append(msg)
            if msg.get("final"):
                break
    assert seen[0]["type"] == "envelope" and seen[-1]["envelope"]["status"] == "done"
    assert all(m["type"] in ("envelope", "progress", "delta", "ping") for m in seen)
    assert len([m for m in seen if m["type"] == "envelope"]) >= 2


def test_ws_requires_token_when_auth_enabled(monkeypatch):
    monkeypatch.setattr(auth, "USERNAME", "clerk"); monkeypatch.setattr(auth, "PASSWORD", "pw")
    c = TestClient(create_app(delay_s=0))
    tok = c.post("/api/login", json={"username": "clerk", "password": "pw"}).json()["token"]
    cid = c.post("/api/cases", files=files(), headers={"Authorization": f"Bearer {tok}"}).json()["case_id"]
    with c.websocket_connect(f"/api/cases/{cid}/ws?token={tok}") as ws:
        assert ws.receive_json()["type"] == "envelope"
    import pytest
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with c.websocket_connect(f"/api/cases/{cid}/ws") as ws:
            ws.receive_json()


def test_ws_unknown_case_closes(monkeypatch):
    monkeypatch.setattr(auth, "USERNAME", "")
    import pytest
    from starlette.websockets import WebSocketDisconnect
    c = TestClient(create_app(delay_s=0))
    with pytest.raises(WebSocketDisconnect):
        with c.websocket_connect("/api/cases/nope/ws") as ws:
            ws.receive_json()


class _StreamingClient(_FakeBedrockClient):
    """有 converse_stream 的假 client：把回覆切成 3 段送出。"""

    def converse_stream(self, **kw):
        self.calls.append({**kw, "_stream": True})
        text = self.replies.pop(0)
        n = max(1, len(text) // 3)
        chunks = [text[i:i + n] for i in range(0, len(text), n)]
        stream = [{"contentBlockDelta": {"delta": {"text": ch}}} for ch in chunks] + [{"metadata": {"usage": {"inputTokens": 1, "outputTokens": 2}}}]
        return {"stream": iter(stream)}


def test_generate_streams_deltas_to_subscribers():
    """有訂閱者時 Generate 走 converse_stream，delta 事件拼起來＝全文；沒有訂閱者時走一般 converse。"""
    from app.store import CaseStore
    bedrock.limiter.min_interval_s = 0
    store = CaseStore(); case = store.create("bedrock", [], None)
    q = case.subscribe()
    s3 = {"statutes": [], "precedents": [], "interpretations": [], "similar_cases": []}
    client = _StreamingClient([_s4_reply()])
    g = bedrock.BedrockGenerate(client=client)

    async def run():
        events.current_case.set(case)
        return await g.run({"case_type": "x", "disposition": {}}, {"admissible": True, "defect_flags": []}, s3)
    s4 = asyncio.run(run())
    assert client.calls[-1].get("_stream") and s4["holding"] == "訴願駁回。"
    evs = []
    while not q.empty():
        evs.append(q.get_nowait())
    deltas = "".join(e["text"] for e in evs if e["type"] == "delta")
    assert deltas == _s4_reply() and any(e["type"] == "progress" and e["stage"] == "S4" for e in evs)

    # 無訂閱者 → 一般 converse
    client2 = _StreamingClient([_s4_reply()])
    async def run2():
        events.current_case.set(None)
        return await bedrock.BedrockGenerate(client=client2).run({"case_type": "x", "disposition": {}}, {"admissible": True, "defect_flags": []}, s3)
    asyncio.run(run2())
    assert not client2.calls[-1].get("_stream")


def test_ocr_and_retrieval_emit_progress():
    from app.store import CaseStore
    bedrock.limiter.min_interval_s = 0
    store = CaseStore(); case = store.create("bedrock", [], None); q = case.subscribe()
    ocr = _fake_ocr(['{"text": "abc", "low_confidence": []}'])
    from app.adapters.base import UploadedImage
    async def run():
        events.current_case.set(case)
        await ocr.run("p", [UploadedImage("petition_image", "a.png", "image/png", 1, b"x")])
        r = bedrock.BedrockRetrieval(agent_client=_FakeAgentClient(_CHUNKS), client=_FakeBedrockClient(["{}"]))
        await r.run({"case_type": "違反洗錢防制法事件", "disposition": {"doc_no": "x", "legal_basis": []}, "appellant_claims": [], "issues": []})
    asyncio.run(run())
    msgs = [e["message"] for e in iter(q.get_nowait, None)] if False else []
    while not q.empty():
        e = q.get_nowait()
        if e["type"] == "progress": msgs.append((e["stage"], e["message"]))
    assert ("S1", "訴願書辨識完成（3 字）") in msgs and any(s == "S3" and "判解檢索完成" in m for s, m in msgs)
