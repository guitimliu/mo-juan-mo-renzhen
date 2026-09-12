# -*- coding: utf-8 -*-
"""帳密登入（環境變數設定）。

- AUTH_USERNAME＋AUTH_PASSWORD 都有設 → /api/cases* 要帶 `Authorization: Bearer <token>`，token 由 POST /api/login 取得。
- 任一沒設 → 不驗證（本機開發／stub demo 直接用）。/api/health 的 auth_required 會告訴前端。
- token 是 HMAC 簽章的 `username:expires`（無狀態；AUTH_SECRET 沒設就每次啟動隨機一組，重啟後舊 token 失效）。
- 單一帳號、比對用 hmac.compare_digest；POC 規模夠用，不做多使用者／refresh。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time

from fastapi import Depends, HTTPException, Request

USERNAME = os.environ.get("AUTH_USERNAME", "").strip()
PASSWORD = os.environ.get("AUTH_PASSWORD", "")
SECRET = (os.environ.get("AUTH_SECRET") or secrets.token_hex(32)).encode()
TOKEN_TTL_S = int(os.environ.get("AUTH_TOKEN_TTL_S", str(12 * 3600)))


def enabled() -> bool:
    return bool(USERNAME and PASSWORD)


def _sign(payload: str) -> str:
    return hmac.new(SECRET, payload.encode(), hashlib.sha256).hexdigest()


def issue_token(username: str, ttl_s: int = TOKEN_TTL_S) -> tuple[str, int]:
    expires = int(time.time()) + ttl_s
    payload = f"{username}:{expires}"
    raw = f"{payload}:{_sign(payload)}"
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("="), expires


def verify_token(token: str) -> str | None:
    """回 username；無效／過期回 None。"""
    try:
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)).decode()
        username, expires, sig = raw.rsplit(":", 2)
    except Exception:  # noqa: BLE001
        return None
    if not hmac.compare_digest(sig, _sign(f"{username}:{expires}")):
        return None
    if int(expires) < time.time():
        return None
    return username


def check_credentials(username: str, password: str) -> bool:
    return enabled() and hmac.compare_digest(username.strip(), USERNAME) and hmac.compare_digest(password, PASSWORD)


async def require_auth(request: Request) -> str | None:
    """FastAPI dependency：驗證關閉時直接放行（回 None）。"""
    if not enabled():
        return None
    header = request.headers.get("authorization", "")
    token = header[7:].strip() if header.lower().startswith("bearer ") else ""
    user = verify_token(token) if token else None
    if not user:
        raise HTTPException(401, "請先登入", headers={"WWW-Authenticate": "Bearer"})
    return user


AuthDep = Depends(require_auth)
