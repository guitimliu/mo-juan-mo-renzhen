# -*- coding: utf-8 -*-
"""in-memory case store（dict）。不用 DB；重啟即清空。envelope 形狀照 03_介面規格 附錄 A。"""
from __future__ import annotations

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
    status: str = "queued"
    current_stage: str | None = None
    error: str | None = None
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)
    stages: dict[str, StageState] = field(default_factory=lambda: {s: StageState() for s in STAGES})

    def touch(self) -> None:
        self.updated_at = now_iso()

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
            "error": self.error,
        }

    def to_summary(self) -> dict:
        """GET /api/cases 列表用：envelope 去掉 stages.data。"""
        env = self.to_envelope()
        env["stages"] = {name: {k: v for k, v in st.items() if k != "data"} for name, st in env["stages"].items()}
        return env


class CaseStore:
    def __init__(self) -> None:
        self._cases: dict[str, Case] = {}
        self._seq = 0

    def create(self, adapter_mode: str, images: list[UploadedImage], service_date: str | None = None) -> Case:
        self._seq += 1
        case = Case(case_id=f"poc-{self._seq:03d}", adapter_mode=adapter_mode, images=images, service_date=service_date)
        self._cases[case.case_id] = case
        return case

    def get(self, case_id: str) -> Case | None:
        return self._cases.get(case_id)

    def list(self) -> list[Case]:
        return list(reversed(self._cases.values()))     # 新的在前（dict 保留插入順序）

    def clear(self) -> None:
        self._cases.clear()
        self._seq = 0
