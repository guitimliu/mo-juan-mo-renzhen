# -*- coding: utf-8 -*-
import sys
import pathlib

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.adapters import stub  # noqa: E402
from app.adapters.base import UploadedImage  # noqa: E402
from app.store import CaseStore  # noqa: E402


@pytest.fixture
def adapters():
    return stub.make_adapters()


@pytest.fixture
def store():
    return CaseStore()


@pytest.fixture
def images():
    return [UploadedImage("petition_image", "a.jpg", "image/jpeg", 3, b"\xff\xd8\xff"),
            UploadedImage("disposition_image", "b.jpg", "image/jpeg", 3, b"\xff\xd8\xff")]


@pytest.fixture
def disposition_text():
    return stub.poc_document("02_模擬書面告誡.md")


@pytest.fixture
def s2_113_16(disposition_text):
    """113-16 的 S2（規格範例＋ 01/02 補齊）。"""
    import asyncio
    a = stub.make_adapters()
    s1 = asyncio.run(a.ocr.run("poc-test", []))
    return asyncio.run(a.extract.run(s1))
