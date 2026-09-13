# -*- coding: utf-8 -*-
"""PostgreSQL 持久層（docs/persistence_design.md 方案 B 的最小版）。

DATABASE_URL 沒設＝關閉，store 維持純記憶體（pytest／本機 stub 不需要 DB）。
設了（docker compose 預設 postgresql+psycopg://mjmr:mjmr@db:5432/mjmr）：
- cases／stage_results：每次 Case.touch() upsert，重啟後 GET /api/cases、/api/cases/{id} 還在。
- case_files：上傳影像本體（bytea），重跑不必再上傳；GET /api/cases/{id}/files/{field} 可回看。
- drafts：承辦人修改後的決定書草稿，版本遞增、可還原 AI 版（version 0 ＝ S4 原稿，不另存）。
PII 對照表（case.pii_map）刻意不進 DB；重啟後 S4 的真名還原需重跑 S1。
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import (JSON, Column, DateTime, Integer, LargeBinary, MetaData, String, Table, Text, UniqueConstraint,
                        create_engine, delete, func, insert, select, update)
from sqlalchemy.engine import Engine

log = logging.getLogger("app.db")
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

metadata = MetaData()

cases = Table(
    "cases", metadata,
    Column("case_id", String(32), primary_key=True),
    Column("seq", Integer, nullable=False),
    Column("owner", String(64)),
    Column("adapter_mode", String(16), nullable=False),
    Column("status", String(16), nullable=False),
    Column("current_stage", String(8)),
    Column("service_date", String(16)),
    Column("pii", JSON),
    Column("error", Text),
    Column("created_at", String(32), nullable=False),
    Column("updated_at", String(32), nullable=False),
)

case_files = Table(
    "case_files", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("case_id", String(32), nullable=False, index=True),
    Column("field", String(32), nullable=False),
    Column("filename", String(255)),
    Column("content_type", String(64)),
    Column("size", Integer),
    Column("content", LargeBinary, nullable=False),
    UniqueConstraint("case_id", "field", name="uq_case_field"),
)

stage_results = Table(
    "stage_results", metadata,
    Column("case_id", String(32), primary_key=True),
    Column("stage", String(8), primary_key=True),
    Column("status", String(16), nullable=False),
    Column("data", JSON),
    Column("error", Text),
    Column("elapsed_ms", Integer),
)

drafts = Table(
    "drafts", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("case_id", String(32), nullable=False, index=True),
    Column("version", Integer, nullable=False),
    Column("content", JSON, nullable=False),          # S4 形狀（header/holding/facts/reasons/instruction/citations…）
    Column("note", Text),
    Column("edited_by", String(64)),
    Column("edited_at", String(32), nullable=False),
    Column("is_current", Integer, nullable=False, default=1),
    UniqueConstraint("case_id", "version", name="uq_case_version"),
)


class Database:
    def __init__(self, url: str) -> None:
        self.url = url
        self.engine: Engine = create_engine(url, pool_pre_ping=True, future=True)
        metadata.create_all(self.engine)
        log.info("DB ready: %s", url.split("@")[-1] if "@" in url else url)

    # ---- cases ----
    def next_seq(self) -> int:
        with self.engine.begin() as c:
            return int(c.execute(select(func.coalesce(func.max(cases.c.seq), 0))).scalar_one()) + 1

    def upsert_case(self, env: dict, seq: int, service_date: str | None, owner: str | None = None) -> None:
        row = {"case_id": env["case_id"], "seq": seq, "owner": owner, "adapter_mode": env["adapter_mode"],
               "status": env["status"], "current_stage": env["current_stage"], "service_date": service_date,
               "pii": env.get("pii"), "error": env.get("error"), "created_at": env["created_at"], "updated_at": env["updated_at"]}
        with self.engine.begin() as c:
            if c.execute(select(cases.c.case_id).where(cases.c.case_id == env["case_id"])).first():
                c.execute(update(cases).where(cases.c.case_id == env["case_id"]).values(**row))
            else:
                c.execute(insert(cases).values(**row))
            c.execute(delete(stage_results).where(stage_results.c.case_id == env["case_id"]))
            c.execute(insert(stage_results), [
                {"case_id": env["case_id"], "stage": name, "status": st["status"], "data": st["data"],
                 "error": st["error"], "elapsed_ms": st["elapsed_ms"]} for name, st in env["stages"].items()])

    def save_files(self, case_id: str, images: list) -> None:
        with self.engine.begin() as c:
            c.execute(delete(case_files).where(case_files.c.case_id == case_id))
            c.execute(insert(case_files), [
                {"case_id": case_id, "field": im.field, "filename": im.filename, "content_type": im.content_type,
                 "size": im.size, "content": im.data} for im in images])

    def load_case(self, case_id: str) -> dict | None:
        """回 {"case": row, "stages": {name: row}, "images": [row...]}；沒有回 None。"""
        with self.engine.begin() as c:
            row = c.execute(select(cases).where(cases.c.case_id == case_id)).mappings().first()
            if not row:
                return None
            stages = {r["stage"]: dict(r) for r in c.execute(
                select(stage_results).where(stage_results.c.case_id == case_id)).mappings()}
            images = [dict(r) for r in c.execute(select(case_files).where(case_files.c.case_id == case_id)).mappings()]
        return {"case": dict(row), "stages": stages, "images": images}

    def list_case_ids(self) -> list[str]:
        with self.engine.begin() as c:
            return [r[0] for r in c.execute(select(cases.c.case_id).order_by(cases.c.seq.desc()))]

    def get_file(self, case_id: str, field: str) -> dict | None:
        with self.engine.begin() as c:
            r = c.execute(select(case_files).where(case_files.c.case_id == case_id, case_files.c.field == field)).mappings().first()
            return dict(r) if r else None

    # ---- drafts ----
    def add_draft(self, case_id: str, content: dict, note: str | None, edited_by: str | None) -> dict:
        with self.engine.begin() as c:
            ver = int(c.execute(select(func.coalesce(func.max(drafts.c.version), 0)).where(drafts.c.case_id == case_id)).scalar_one()) + 1
            c.execute(update(drafts).where(drafts.c.case_id == case_id).values(is_current=0))
            row = {"case_id": case_id, "version": ver, "content": content, "note": note, "edited_by": edited_by,
                   "edited_at": _now(), "is_current": 1}
            c.execute(insert(drafts).values(**row))
        return row

    def list_drafts(self, case_id: str) -> list[dict]:
        with self.engine.begin() as c:
            return [_draft_meta(r) for r in c.execute(
                select(drafts).where(drafts.c.case_id == case_id).order_by(drafts.c.version)).mappings()]

    def get_draft(self, case_id: str, version: int | None = None) -> dict | None:
        q = select(drafts).where(drafts.c.case_id == case_id)
        q = q.where(drafts.c.version == version) if version is not None else q.where(drafts.c.is_current == 1)
        with self.engine.begin() as c:
            r = c.execute(q).mappings().first()
            return dict(r) if r else None

    def set_current(self, case_id: str, version: int) -> bool:
        with self.engine.begin() as c:
            if not c.execute(select(drafts.c.id).where(drafts.c.case_id == case_id, drafts.c.version == version)).first():
                return False
            c.execute(update(drafts).where(drafts.c.case_id == case_id).values(is_current=0))
            c.execute(update(drafts).where(drafts.c.case_id == case_id, drafts.c.version == version).values(is_current=1))
            return True

    def clear_current(self, case_id: str) -> None:
        """「還原 AI 版」＝沒有 current 草稿，前端回頭讀 S4。"""
        with self.engine.begin() as c:
            c.execute(update(drafts).where(drafts.c.case_id == case_id).values(is_current=0))


def _now() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def _draft_meta(r) -> dict:
    return {k: r[k] for k in ("version", "note", "edited_by", "edited_at")} | {"is_current": bool(r["is_current"])}


def connect(url: str | None = None) -> Database | None:
    url = DATABASE_URL if url is None else url
    if not url:
        return None
    return Database(url)
