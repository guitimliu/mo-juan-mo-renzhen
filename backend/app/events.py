# -*- coding: utf-8 -*-
"""案件即時事件：pipeline 跑在背景 task，adapters 用 contextvar 找到目前案件，把子步驟／串流片段推給 WebSocket 訂閱者。

事件形狀（WS 原樣轉發）：
- {"type": "progress", "stage": "S1", "message": "訴願書辨識完成（612 字）"}
- {"type": "delta",    "stage": "S4", "text": "一、按洗錢防制法…"}        # 生成串流逐段文字
- {"type": "envelope", "envelope": {...}}                                  # 階段狀態變化（store.touch 觸發）
"""
from __future__ import annotations

import asyncio
import contextvars
from typing import Any

current_case: contextvars.ContextVar[Any] = contextvars.ContextVar("current_case", default=None)


def emit(type_: str, **payload) -> None:
    """在 event loop 內呼叫。沒有訂閱者／不在 pipeline 裡就是 no-op。"""
    case = current_case.get()
    if case is not None:
        case.emit({"type": type_, **payload})


def progress(stage: str, message: str) -> None:
    emit("progress", stage=stage, message=message)


def threadsafe_emitter(loop: asyncio.AbstractEventLoop, stage: str):
    """給 to_thread 裡的串流用：回傳一個可在別的 thread 呼叫的 on_delta(text)。"""
    case = current_case.get()
    if case is None:
        return None

    def on_delta(text: str) -> None:
        loop.call_soon_threadsafe(case.emit, {"type": "delta", "stage": stage, "text": text})
    return on_delta
