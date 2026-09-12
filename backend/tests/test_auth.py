# -*- coding: utf-8 -*-
"""帳密登入：AUTH_USERNAME／AUTH_PASSWORD 有設才驗證。"""
import pytest
from fastapi.testclient import TestClient

from app import auth
from app.main import create_app


def files():
    return {"petition_image": ("a.jpg", b"\xff\xd8\xff", "image/jpeg"), "disposition_image": ("b.jpg", b"\xff\xd8\xff", "image/jpeg")}


@pytest.fixture
def secured(monkeypatch):
    monkeypatch.setattr(auth, "USERNAME", "clerk")
    monkeypatch.setattr(auth, "PASSWORD", "s3cret")
    return TestClient(create_app(delay_s=0))


def test_auth_disabled_by_default(monkeypatch):
    monkeypatch.setattr(auth, "USERNAME", "")
    c = TestClient(create_app(delay_s=0))
    assert c.get("/api/health").json()["auth_required"] is False
    assert c.post("/api/login", json={"username": "x", "password": "y"}).json() == {"auth_required": False, "token": None}
    assert c.post("/api/cases", files=files()).status_code == 202          # 不用 token


def test_login_and_protected_routes(secured):
    c = secured
    assert c.get("/api/health").json()["auth_required"] is True             # health 本身不用登入
    assert c.get("/api/cases").status_code == 401
    assert c.post("/api/cases", files=files()).status_code == 401
    assert c.post("/api/login", json={"username": "clerk", "password": "wrong"}).status_code == 401
    assert c.post("/api/login", json={"username": "nobody", "password": "s3cret"}).status_code == 401
    r = c.post("/api/login", json={"username": "clerk", "password": "s3cret"}).json()
    assert r["auth_required"] and r["token"] and r["username"] == "clerk"
    h = {"Authorization": f"Bearer {r['token']}"}
    assert c.get("/api/me", headers=h).json() == {"auth_required": True, "username": "clerk"}
    cid = c.post("/api/cases", files=files(), headers=h).json()["case_id"]
    assert c.get(f"/api/cases/{cid}", headers=h).status_code == 200
    assert c.get(f"/api/cases/{cid}").status_code == 401
    assert c.get(f"/api/cases/{cid}", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_token_expiry_and_tamper(monkeypatch):
    monkeypatch.setattr(auth, "USERNAME", "clerk")
    monkeypatch.setattr(auth, "PASSWORD", "s3cret")
    token, _ = auth.issue_token("clerk", ttl_s=-1)
    assert auth.verify_token(token) is None                                   # 過期
    token, _ = auth.issue_token("clerk")
    assert auth.verify_token(token) == "clerk"
    assert auth.verify_token(token[:-2] + "zz") is None                        # 竄改
    assert auth.verify_token("") is None and auth.verify_token("not-base64!!") is None
