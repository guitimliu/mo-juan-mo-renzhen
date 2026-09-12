# -*- coding: utf-8 -*-
"""環境設定：全部可用環境變數覆蓋，預設值以本地 stub 開發為準。"""
import os
import pathlib

BACKEND_DIR = pathlib.Path(__file__).resolve().parents[1]
REPO_DIR = BACKEND_DIR.parent

# stub | bedrock；bedrock 的 OCR、Extract、Retrieval 已實作，Generate 仍為空殼（跑到 S4 會 NotImplementedError）
ADAPTER = os.environ.get("ADAPTER", "stub").strip().lower()

# 工作包（唯一真相來源是 hackathon/data/poc，repo 根目錄 data/poc 為同步副本）
DATA_DIR = pathlib.Path(os.environ.get("DATA_DIR", REPO_DIR / "data")).resolve()
POC_DIR = DATA_DIR / "poc"

# stub 模式每階段的模擬延遲（秒），讓前端六區塊逐一出現；pytest 設 0
STUB_STAGE_DELAY_S = float(os.environ.get("STUB_STAGE_DELAY_S", "1.5"))

# 與 E 的前端一致：單檔 10 MB
MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
ALLOWED_IMAGE_TYPES = ("image/jpeg", "image/png", "image/webp")

CORS_ORIGINS = [o.strip() for o in os.environ.get(
    "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",") if o.strip()]

TZ = "Asia/Taipei"
