# -*- coding: utf-8 -*-
"""四個階段的 adapter 介面。stub 與 bedrock 都照這組簽名實作，pipeline 只認這裡。

S1／S2／S3／S4 的 JSON 形狀見 data/poc/03_介面規格.md。
所有 run 都是 async：Bedrock 版會做網路 I/O，stub 版直接回傳。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class UploadedImage:
    """POST /api/cases 收到的一張影像。stub 模式不看內容，只記錄中繼資料。"""
    field: str            # petition_image | disposition_image
    filename: str
    content_type: str
    size: int
    data: bytes


class OCRAdapter(Protocol):
    async def run(self, case_id: str, images: list[UploadedImage]) -> dict:
        """影像 → S1 {case_id, petition_text, disposition_text, ocr_confidence_note}"""
        ...


class ExtractAdapter(Protocol):
    async def run(self, s1: dict) -> dict:
        """S1 → S2 案件摘要"""
        ...


class RetrievalAdapter(Protocol):
    async def run(self, s2: dict) -> dict:
        """S2 → S3 {statutes, precedents, interpretations, similar_cases}"""
        ...


class GenerateAdapter(Protocol):
    async def run(self, s2: dict, s2_5: dict, s3: dict) -> dict:
        """S2 + S2.5 + S3 → S4 決定書草稿（citations 依附錄 B 帶 section/index；沒來源的寫進 gaps）"""
        ...


@dataclass(frozen=True)
class AdapterSet:
    mode: str                     # stub | bedrock
    ocr: OCRAdapter
    extract: ExtractAdapter
    retrieval: RetrievalAdapter
    generate: GenerateAdapter
