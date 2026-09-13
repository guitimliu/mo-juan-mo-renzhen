# -*- coding: utf-8 -*-
"""case store：記憶體為主（WS 訂閱者、PII 對照表只在記憶體），DATABASE_URL 有設時同步落 PostgreSQL（app/db.py）：
每次 touch() upsert 案件＋六階段，重啟後 get()／list() 從 DB 還原（影像一起載回，pii_map 不還原）。envelope 形狀照 03_介面規格 附錄 A。"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from . import settings
from .adapters.base import UploadedImage

TAIPEI = timezone(timedelta(hours=8), settings.TZ)     # 固定 +08:00，不依賴系統 tz 資料庫（Windows 沒裝 tzdata 會炸）

STAGES = ("S1", "S2", "S2_5", "S3", "S4", "S5")
STAGE_STATUSES = ("pending", "running", "done", "error", "skipped")
CASE_STATUSES = ("queued", "running", "done", "error")


def now_iso() -> str:
    return datetime.now(TAIPEI).isoformat(timespec="seconds")


@dataclass
class StageState:
    status: str = "pending"
    data: dict | None = None
    error: str | None = None
    elapsed_ms: int | None = None

    def to_dict(self) -> dict:
        return {"status": self.status, "data": self.data, "error": self.error, "elapsed_ms": self.elapsed_ms}


@dataclass
class Case:
    case_id: str
    adapter_mode: str
    images: list[UploadedImage] = field(default_factory=list, repr=False)
    service_date: str | None = None          # 承辦人在前端填的送達日（選填），覆蓋 S2.served_date
    pii_map: object = field(default=None, repr=False)   # app.pii.PIIMap：真名對照表，只在記憶體，不進 envelope
    pii: dict | None = None                  # 去識別化摘要（類別／筆數／代號），給前端顯示
    _subs: list = field(default_factory=list, repr=False)   # WebSocket 訂閱者的 asyncio.Queue（app/events.py）
    _persist: object = field(default=None, repr=False)      # CaseStore 掛上的落地 callback（DB 關閉時 None）
    seq: int = 0
    status: str = "queued"
    current_stage: str | None = None
    error: str | None = None
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)
    stages: dict[str, StageState] = field(default_factory=lambda: {s: StageState() for s in STAGES})

    def touch(self) -> None:
        self.updated_at = now_iso()
        if self._persist:
            try:
                self._persist(self)
            except Exception:                 # DB 掛了不能讓管線死；envelope 還在記憶體
                logging.getLogger("app.store").exception("persist case %s failed", self.case_id)
        self.emit({"type": "stage"})          # WS handler 收到後送完整 envelope

    # ---- 即時事件（app/events.py）----
    def subscribe(self) -> "asyncio.Queue":
        q: asyncio.Queue = asyncio.Queue()
        self._subs.append(q)
        return q

    def unsubscribe(self, q) -> None:
        if q in self._subs:
            self._subs.remove(q)

    def emit(self, event: dict) -> None:
        for q in list(self._subs):
            q.put_nowait(event)

    def to_envelope(self) -> dict:
        """附錄 A。"""
        return {
            "case_id": self.case_id,
            "status": self.status,
            "current_stage": self.current_stage,
            "adapter_mode": self.adapter_mode,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "stages": {name: st.to_dict() for name, st in self.stages.items()},
            "pii": self.pii,
            "error": self.error,
        }

    def to_summary(self) -> dict:
        """GET /api/cases 列表用：envelope 去掉 stages.data。"""
        env = self.to_envelope()
        env["stages"] = {name: {k: v for k, v in st.items() if k != "data"} for name, st in env["stages"].items()}
        return env


class CaseStore:
    def __init__(self, db=None) -> None:
        self._cases: dict[str, Case] = {}
        self.db = db
        self._seq = db.next_seq() - 1 if db else 0

    def _persist(self, case: Case) -> None:
        self.db.upsert_case(case.to_envelope(), case.seq, case.service_date)

    def create(self, adapter_mode: str, images: list[UploadedImage], service_date: str | None = None) -> Case:
        self._seq += 1
        case = Case(case_id=f"poc-{self._seq:03d}", adapter_mode=adapter_mode, images=images, service_date=service_date, seq=self._seq)
        self._cases[case.case_id] = case
        if self.db:
            case._persist = self._persist
            self._persist(case)
            self.db.save_files(case.case_id, images)
        return case

    def get(self, case_id: str) -> Case | None:
        case = self._cases.get(case_id)
        if case is None and self.db:
            case = self._rehydrate(case_id)
        return case

    def _rehydrate(self, case_id: str) -> Case | None:
        row = self.db.load_case(case_id)
        if not row:
            return None
        c, stages = row["case"], row["stages"]
        case = Case(case_id=case_id, adapter_mode=c["adapter_mode"], service_date=c["service_date"], seq=c["seq"],
                    images=[UploadedImage(field=im["field"], filename=im["filename"], content_type=im["content_type"],
                                          size=im["size"], data=bytes(im["content"])) for im in row["images"]])
        case.status, case.current_stage, case.error, case.pii = c["status"], c["current_stage"], c["error"], c["pii"]
        case.created_at, case.updated_at = c["created_at"], c["updated_at"]
        for name in STAGES:
            st = stages.get(name)
            if st:
                case.stages[name] = StageState(status=st["status"], data=st["data"], error=st["error"], elapsed_ms=st["elapsed_ms"])
        if case.status == "running":          # 重啟時管線已中斷：標成 error，讓前端不會一直等
            case.status, case.error = "error", "後端重啟，處理中斷；可重新送件"
            for st in case.stages.values():
                if st.status == "running":
                    st.status, st.error = "error", "後端重啟中斷"
        case._persist = self._persist
        self._cases[case_id] = case
        return case

    def list(self) -> list[Case]:
        if self.db:
            for cid in self.db.list_case_ids():
                if cid not in self._cases:
                    self._rehydrate(cid)
        return sorted(self._cases.values(), key=lambda c: -c.seq)     # 新的在前

    def clear(self) -> None:
        self._cases.clear()
        self._seq = 0
