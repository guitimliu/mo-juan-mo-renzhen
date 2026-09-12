# -*- coding: utf-8 -*-
"""run_case：依序 S1 → S2 → S2.5 → S3 → S4 → S5，每步寫回 store。

- 某步失敗：該步 status="error" 並記 error；依賴它的後續步 status="skipped"（error 註明上游），
  不依賴的步照跑（例如 S3 失敗時 S2.5 仍完成；S1 失敗則全部 skipped）。
- 整體 status：全部 done → "done"；任一步 error → "error"，envelope.error 記第一個失敗的階段。
- stub 模式每步先 sleep STUB_STAGE_DELAY_S（預設 1.5 s），讓前端六區塊逐一出現；
  elapsed_ms 只計實際工作時間，不含這個模擬延遲。
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable

from . import checker, pii, rules, settings
from .adapters.base import AdapterSet
from .store import STAGES, CaseStore

log = logging.getLogger("pipeline")


async def run_case(case_id: str, store: CaseStore, adapters: AdapterSet, delay_s: float = 0.0) -> None:
    case = store.get(case_id)
    if case is None:
        log.error("run_case: case %s not found", case_id)
        return
    case.status = "running"
    case.touch()
    ctx: dict[str, dict] = {}

    async def step(name: str, deps: tuple[str, ...], fn: Callable[[], Awaitable[dict]]) -> None:
        st = case.stages[name]
        missing = [d for d in deps if d not in ctx]
        if missing:
            st.status = "skipped"
            st.error = f"上游 {'、'.join(missing)} 未完成，略過"
            case.touch()
            return
        st.status = "running"
        case.current_stage = name
        case.touch()
        if delay_s > 0:
            await asyncio.sleep(delay_s)
        t0 = time.perf_counter()
        try:
            data = await fn()
            st.data = data
            st.status = "done"
            ctx[name] = data
        except Exception as exc:  # noqa: BLE001 — 任何例外都記進 envelope，不讓背景工作悄悄死掉
            log.exception("stage %s failed for %s", name, case_id)
            st.status = "error"
            st.error = f"{type(exc).__name__}: {exc}"
        st.elapsed_ms = int((time.perf_counter() - t0) * 1000)
        case.touch()

    async def as_async(fn, *args):
        return fn(*args)

    async def ocr_then_mask():
        """S1 之後、任何文字送模型之前做個資取代（app/pii.py）；對照表留在 case.pii_map，envelope 只有摘要。"""
        s1 = await adapters.ocr.run(case_id, case.images)
        if not settings.pii_enabled(adapters.mode) or not isinstance(s1, dict):
            return s1
        m = pii.detect([s1.get("petition_text") or "", s1.get("disposition_text") or ""])
        masked = pii.apply_to(s1, m)
        for k in ("petition_text", "disposition_text"):
            pii.count_applied(s1.get(k) or "", masked.get(k) or "", m)
        case.pii_map, case.pii = m, m.summary()
        labels = {"name": "姓名", "id": "身分證", "phone": "電話", "address": "地址", "dob": "生日"}
        masked["pii_note"] = ("已去識別化（取代法）：" + "、".join(f"{labels.get(k, k)}×{v}" for k, v in m.summary()["replaced"].items()) +
                             "；姓名改以代號 " + "／".join(m.summary()["codes"]) + " 送模型，對照表僅存本機，草稿輸出時還原") if m.enabled else "未偵測到個資"
        masked["ocr_confidence_note"] = masked["pii_note"] + "｜" + (masked.get("ocr_confidence_note") or "")   # 前端 OCR 頁直接看得到
        return masked

    await step("S1", (), ocr_then_mask)
    async def extract_with_overrides():
        s2 = await adapters.extract.run(ctx["S1"])
        # 前端「送達日期（選填）」：承辦人依送達證明填的日子比 OCR／LLM 擷取可靠，直接覆蓋
        if case.service_date and isinstance(s2, dict):
            d = rules.parse_roc_date(case.service_date)
            if d is None:
                raise ValueError(f"service_date 無法解析：{case.service_date!r}（接受 YYYY-MM-DD 或民國 YYY-MM-DD）")
            s2["served_date"] = rules.to_roc(d)
            s2["served_date_source"] = "user"
        return s2

    await step("S2", ("S1",), extract_with_overrides)
    await step("S2_5", ("S2",), lambda: as_async(rules.check_procedure, ctx["S2"], ctx["S1"].get("disposition_text")))
    await step("S3", ("S2",), lambda: adapters.retrieval.run(ctx["S2"]))
    async def generate_then_restore():
        s4 = await adapters.generate.run(ctx["S2"], ctx["S2_5"], ctx["S3"])
        return pii.restore(s4, case.pii_map) if case.pii_map else s4     # 只還原姓名；身分證／地址維持遮罩

    await step("S4", ("S2", "S2_5", "S3"), generate_then_restore)
    await step("S5", ("S4",), lambda: as_async(checker.run, ctx["S4"], ctx.get("S3")))

    failed = [n for n in STAGES if case.stages[n].status == "error"]
    case.current_stage = None
    case.status = "error" if failed else "done"
    case.error = f"階段 {failed[0]} 失敗：{case.stages[failed[0]].error}" if failed else None
    case.touch()
