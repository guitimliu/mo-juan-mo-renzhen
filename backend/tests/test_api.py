# -*- coding: utf-8 -*-
"""HTTP 層：/api/health、POST/GET /api/cases、上傳驗證、CORS。"""
import io

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

JPG = b"\xff\xd8\xff\xe0" + b"0" * 64


@pytest.fixture
def client():
    return TestClient(create_app(delay_s=0))


def files(a=JPG, b=JPG, a_type="image/jpeg", b_type="image/jpeg"):
    return {"petition_image": ("a.jpg", io.BytesIO(a), a_type), "disposition_image": ("b.jpg", io.BytesIO(b), b_type)}


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok", "adapter_mode": "stub"}


def test_create_and_get_case(client):
    r = client.post("/api/cases", files=files())
    assert r.status_code == 202 and r.json() == {"case_id": "poc-001"}
    env = client.get("/api/cases/poc-001").json()      # TestClient 會等背景工作跑完
    assert env["case_id"] == "poc-001" and env["status"] == "done"
    assert env["stages"]["S5"]["data"]["score"]["總分"] == "30/31"
    assert env["stages"]["S4"]["data"]["citations"][0].keys() >= {"text", "source", "section", "index"}


def test_case_ids_are_sequential(client):
    ids = [client.post("/api/cases", files=files()).json()["case_id"] for _ in range(2)]
    assert ids == ["poc-001", "poc-002"]
    lst = client.get("/api/cases").json()["cases"]
    assert [c["case_id"] for c in lst] == ["poc-002", "poc-001"]
    assert "data" not in lst[0]["stages"]["S4"] and lst[0]["stages"]["S4"]["status"] == "done"


def test_get_unknown_case_404(client):
    assert client.get("/api/cases/poc-999").status_code == 404


def test_missing_field_422(client):
    r = client.post("/api/cases", files={"petition_image": ("a.jpg", io.BytesIO(JPG), "image/jpeg")})
    assert r.status_code == 422


def test_wrong_content_type_415(client):
    r = client.post("/api/cases", files=files(a_type="text/plain"))
    assert r.status_code == 415 and "petition_image" in r.json()["detail"]


def test_empty_file_400(client):
    assert client.post("/api/cases", files=files(b=b"")).status_code == 400


def test_too_large_413(client, monkeypatch):
    from app import settings
    monkeypatch.setattr(settings, "MAX_UPLOAD_BYTES", 16)
    assert client.post("/api/cases", files=files()).status_code == 413


def test_cors_allows_vite_dev_server(client):
    r = client.options("/api/cases", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"})
    assert r.status_code == 200 and r.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_missing_data_dir_fails_fast(monkeypatch, tmp_path):
    from app import settings
    from app.main import check_data_files
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    with pytest.raises(RuntimeError, match="缺檔"):
        check_data_files()


def test_timestamp_has_fixed_plus8_offset():
    from app.store import now_iso
    assert now_iso().endswith("+08:00")


def test_service_date_overrides_served_date(client):
    r = client.post("/api/cases", files=files(), data={"service_date": "2024-09-20"})
    assert r.status_code == 202
    env = client.get(f"/api/cases/{r.json()['case_id']}").json()
    s2 = env["stages"]["S2"]["data"]
    assert s2["served_date"] == "113-09-20" and s2["served_date_source"] == "user"
    assert env["stages"]["S2_5"]["data"]["checks"][0]["served"] == "113-09-20"


def test_service_date_invalid_422(client):
    assert client.post("/api/cases", files=files(), data={"service_date": "not-a-date"}).status_code == 422


def test_service_date_blank_ignored(client):
    r = client.post("/api/cases", files=files(), data={"service_date": "  "})
    env = client.get(f"/api/cases/{r.json()['case_id']}").json()
    assert env["stages"]["S2"]["data"]["served_date"] == "113-09-02" and "served_date_source" not in env["stages"]["S2"]["data"]
