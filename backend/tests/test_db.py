# -*- coding: utf-8 -*-
"""持久層：用 SQLite 走同一套 SQLAlchemy 程式（正式是 PostgreSQL）。重啟還原、草稿版本、檔案回看。"""
import io

import pytest
from fastapi.testclient import TestClient

from app import db as dbmod
from app.main import create_app
from app.store import CaseStore

PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 64


def files():
    return {"petition_image": ("p.png", io.BytesIO(PNG), "image/png"),
            "disposition_image": ("d.png", io.BytesIO(PNG), "image/png")}


@pytest.fixture
def database(tmp_path):
    return dbmod.connect(f"sqlite:///{tmp_path}/t.db")


def test_case_survives_restart(database):
    with TestClient(create_app(delay_s=0, store=CaseStore(database))) as c:
        cid = c.post("/api/cases", files=files()).json()["case_id"]
        env = c.get(f"/api/cases/{cid}").json()
        assert env["status"] == "done" and env["draft"] is None
    # 新的 store（模擬重啟）：案件、六階段、影像都從 DB 回來；case_id 序號接續
    with TestClient(create_app(delay_s=0, store=CaseStore(database))) as c:
        assert c.get("/api/health").json()["db"] is True
        env = c.get(f"/api/cases/{cid}").json()
        assert env["status"] == "done" and env["stages"]["S4"]["data"]["holding"]
        assert [x["case_id"] for x in c.get("/api/cases").json()["cases"]] == [cid]
        r = c.get(f"/api/cases/{cid}/files/petition_image")
        assert r.status_code == 200 and r.content == PNG and r.headers["content-type"] == "image/png"
        assert c.post("/api/cases", files=files()).json()["case_id"] == "poc-002"


def test_draft_versions(database):
    with TestClient(create_app(delay_s=0, store=CaseStore(database))) as c:
        cid = c.post("/api/cases", files=files()).json()["case_id"]
        ai = c.get(f"/api/cases/{cid}/drafts/current").json()
        assert ai["version"] == 0 and ai["content"]["holding"]
        v1 = c.put(f"/api/cases/{cid}/draft", json={"content": {**ai["content"], "holding": "訴願駁回。（改）"}, "note": "改主文"}).json()
        v2 = c.put(f"/api/cases/{cid}/draft", json={"content": {**ai["content"], "holding": "v2"}}).json()
        assert (v1["version"], v2["version"]) == (1, 2)
        assert c.get(f"/api/cases/{cid}/drafts/current").json()["content"]["holding"] == "v2"
        assert c.get(f"/api/cases/{cid}").json()["draft"]["version"] == 2
        assert [d["is_current"] for d in c.get(f"/api/cases/{cid}/drafts").json()["drafts"]] == [False, True]
        assert c.post(f"/api/cases/{cid}/drafts/1/restore").json()["current_version"] == 1
        assert c.get(f"/api/cases/{cid}/drafts/current").json()["content"]["holding"] == "訴願駁回。（改）"
        assert c.post(f"/api/cases/{cid}/drafts/0/restore").status_code == 200
        assert c.get(f"/api/cases/{cid}/drafts/current").json()["version"] == 0
        assert c.post(f"/api/cases/{cid}/drafts/9/restore").status_code == 404
        assert c.get("/api/cases/nope/drafts").status_code == 404


def test_without_db_returns_501():
    with TestClient(create_app(delay_s=0)) as c:
        cid = c.post("/api/cases", files=files()).json()["case_id"]
        assert c.put(f"/api/cases/{cid}/draft", json={"content": {}}).status_code == 501
