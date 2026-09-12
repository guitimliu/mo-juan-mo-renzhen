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

from . import checker, rules
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

    await step("S1", (), lambda: adapters.ocr.run(case_id, case.images))
    await step("S2", ("S1",), lambda: adapters.extract.run(ctx["S1"]))
    await step("S2_5", ("S2",), lambda: as_async(rules.check_procedure, ctx["S2"], ctx["S1"].get("disposition_text")))
    await step("S3", ("S2",), lambda: adapters.retrieval.run(ctx["S2"]))
    await step("S4", ("S2", "S2_5", "S3"), lambda: adapters.generate.run(ctx["S2"], ctx["S2_5"], ctx["S3"]))
    await step("S5", ("S4",), lambda: as_async(checker.run, ctx["S4"], ctx.get("S3")))

    failed = [n for n in STAGES if case.stages[n].status == "error"]
    case.current_stage = None
    case.status = "error" if failed else "done"
    case.error = f"階段 {failed[0]} 失敗：{case.stages[failed[0]].error}" if failed else None
    case.touch()
