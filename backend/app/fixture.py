# -*- coding: utf-8 -*-
"""用 stub pipeline 產前端保底 fixture（附錄 A envelope）→ f2e/src/data/pipeline.json。

用法：cd backend && python -m app.fixture [輸出路徑]
取代 E 的 f2e/scripts/build-demo-fixture.py（舊格式、舊工作包）；前端 demo.ts 兩種形狀都吃得下。
"""
import asyncio
import json
import pathlib
import sys

from . import settings
from .adapters import stub
from .adapters.base import UploadedImage
from .pipeline import run_case
from .store import CaseStore


def build() -> dict:
    store = CaseStore()
    images = [UploadedImage("petition_image", "01_模擬訴願書.jpg", "image/jpeg", 0, b""),
              UploadedImage("disposition_image", "02_模擬書面告誡.jpg", "image/jpeg", 0, b"")]
    case = store.create("stub", images)
    asyncio.run(run_case(case.case_id, store, stub.make_adapters(), delay_s=0))
    env = case.to_envelope()
    env["provenance"] = "後端 stub pipeline 產出的保底 fixture（python -m app.fixture）；正本改寫，非 AI 生成"
    return env


if __name__ == "__main__":
    out = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else settings.REPO_DIR / "f2e" / "src" / "data" / "pipeline.json"
    env = build()
    assert env["status"] == "done", env["error"]
    out.write_text(json.dumps(env, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print("→", out, env["stages"]["S5"]["data"]["score"])
