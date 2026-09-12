# -*- coding: utf-8 -*-
"""FastAPI 入口：CORS、路由。啟動：uvicorn app.main:app --reload --port 8000

路由（03_介面規格 S0 ＋ 附錄 A；前綴 /api）：
  GET  /api/health              → {status, adapter_mode}
  POST /api/cases               multipart petition_image、disposition_image → 202 {case_id}；背景跑 pipeline
  GET  /api/cases               → {cases:[envelope 去掉 stages.data]}
  GET  /api/cases/{case_id}     → 附錄 A envelope
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from . import pipeline, rules, settings
from .adapters import bedrock, stub
from .adapters.base import AdapterSet, UploadedImage
from .store import CaseStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def build_adapters(mode: str) -> AdapterSet:
    if mode == "stub":
        return stub.make_adapters()
    if mode == "bedrock":
        return AdapterSet(mode="bedrock", ocr=bedrock.BedrockOCR(), extract=bedrock.BedrockExtract(),
                          retrieval=bedrock.BedrockRetrieval(), generate=bedrock.BedrockGenerate())
    raise ValueError(f"ADAPTER 只能是 stub 或 bedrock，收到 {mode!r}")


def stage_delay(mode: str) -> float:
    return settings.STUB_STAGE_DELAY_S if mode == "stub" else 0.0


REQUIRED_DATA_FILES = ("poc/07_檢核.py", "poc/06_標準答案_引用清單.json", "poc/00_標準答案_113-16_原決定書.md",
                       "poc/01_模擬訴願書.md", "poc/02_模擬書面告誡.md", "poc/03_介面規格.md",
                       "statutes.json", "precedents.json", "petitions.jsonl")


def check_data_files() -> None:
    """啟動就確認 DATA_DIR 齊全，不要等到第一個案件 S1 才 FileNotFoundError。"""
    missing = [f for f in REQUIRED_DATA_FILES if not (settings.DATA_DIR / f).exists()]
    if missing:
        raise RuntimeError(f"DATA_DIR={settings.DATA_DIR} 缺檔：{'、'.join(missing)}；請確認 repo 根目錄 data/ 已同步（或設 DATA_DIR）")


def create_app(adapters: AdapterSet | None = None, store: CaseStore | None = None, delay_s: float | None = None) -> FastAPI:
    check_data_files()
    adapters = adapters or build_adapters(settings.ADAPTER)
    store = store or CaseStore()
    delay = stage_delay(adapters.mode) if delay_s is None else delay_s

    app = FastAPI(title="訴願 POC backend", version="0.1.0")
    app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])
    app.state.adapters, app.state.store = adapters, store
    api = APIRouter(prefix="/api")

    async def read_upload(field: str, upload: UploadFile) -> UploadedImage:
        content_type = (upload.content_type or "").split(";")[0].strip().lower()
        if content_type not in settings.ALLOWED_IMAGE_TYPES:
            raise HTTPException(415, f"{field}：只接受 JPG／PNG／WebP，收到 {content_type or '未知'}")
        if upload.size and upload.size > settings.MAX_UPLOAD_BYTES:      # 先看 size，不把整檔讀進記憶體才擋
            raise HTTPException(413, f"{field}：超過 {settings.MAX_UPLOAD_BYTES // (1024 * 1024)} MB 上限")
        data = await upload.read()
        if not data:
            raise HTTPException(400, f"{field}：檔案是空的")
        if len(data) > settings.MAX_UPLOAD_BYTES:
            raise HTTPException(413, f"{field}：超過 {settings.MAX_UPLOAD_BYTES // (1024 * 1024)} MB 上限")
        return UploadedImage(field=field, filename=upload.filename or field, content_type=content_type, size=len(data), data=data)

    @api.get("/health")
    async def health():
        return {"status": "ok", "adapter_mode": adapters.mode}

    @api.post("/cases", status_code=202)
    async def create_case(background: BackgroundTasks,
                          petition_image: UploadFile = File(..., description="訴願書影像"),
                          disposition_image: UploadFile = File(..., description="原處分書影像"),
                          service_date: str | None = Form(None, description="送達日期（選填，YYYY-MM-DD 或民國 YYY-MM-DD），覆蓋 S2.served_date")):
        images = [await read_upload("petition_image", petition_image),
                  await read_upload("disposition_image", disposition_image)]
        service_date = (service_date or "").strip() or None
        if service_date and rules.parse_roc_date(service_date) is None:
            raise HTTPException(422, f"service_date 無法解析：{service_date!r}（接受 YYYY-MM-DD 或民國 YYY-MM-DD）")
        case = store.create(adapters.mode, images, service_date)
        background.add_task(pipeline.run_case, case.case_id, store, adapters, delay)
        return {"case_id": case.case_id}

    @api.get("/cases")
    async def list_cases():
        return {"cases": [c.to_summary() for c in store.list()]}

    @api.get("/cases/{case_id}")
    async def get_case(case_id: str):
        case = store.get(case_id)
        if case is None:
            raise HTTPException(404, f"case {case_id} not found")
        return case.to_envelope()

    app.include_router(api)
    return app


app = create_app()
