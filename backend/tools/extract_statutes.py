# -*- coding: utf-8 -*-
"""從主辦方「相關法規」PDF 逐條切出指定條文 → data/statutes.json（stub 檢索用的法條查表）。

用法：
  python tools/extract_statutes.py <相關法規資料夾> [輸出檔]
  例：python tools/extract_statutes.py ../../extracted/資料集/相關法規 ../data/statutes.json

預設切全部法規的全部條文（bedrock Retrieval 查表用）；加 --poc 只切 WANTED（POC 最小集合）。
PDF 皆有文字層，用 pdftotext -layout 抽取，不需 OCR。
"""
import json
import pathlib
import re
import subprocess
import sys

WANTED = {
    "洗錢防制法": ["22"],
    "訴願法": ["14", "18", "77", "79", "81"],
    "行政程序法": ["74", "96", "114"],
    "行政罰法": ["7"],
}
CN_NUM = "一二三四五六七八九十"


def pdf_text(path: pathlib.Path) -> str:
    out = subprocess.run(["pdftotext", "-layout", str(path), "-"], check=True, capture_output=True)
    return out.stdout.decode("utf8")


def version_date(text: str) -> str | None:
    m = re.search(r"修正日期[：:]\s*民國\s*(\d+)\s*年\s*(\d+)\s*月\s*(\d+)\s*日", text)
    return f"{int(m[1]):03d}-{int(m[2]):02d}-{int(m[3]):02d}" if m else None


def split_articles(text: str) -> dict[str, str]:
    """回傳 {條號: 條文原文（含項次數字）}。條號含「之N」如 15-1。"""
    flat = re.sub(r"[ \t　]+", " ", text)
    flat = re.sub(r"\n\s*\n+", "\n", flat)
    # 條文標題：行首「第 N 條」或「第 N-1 條」；後面可能直接接第 1 項
    heads = list(re.finditer(r"(?m)^\s*第\s*(\d+(?:-\d+)?)\s*條\s*", flat))
    arts = {}
    for i, h in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(flat)
        body = flat[h.end():end]
        body = re.sub(r"列印時間[：:].*", "", body)      # 頁首
        body = re.sub(r"\n\s*", "", body)                 # 折行合併
        arts[h[1]] = body.strip()
    return arts


def paragraphs(body: str) -> list[str]:
    """把「1 …2 …」項次切成陣列；無項次的條文回傳單一元素。"""
    parts = re.split(r"(?:(?<=^)|(?<=[。：︰]))\s*(\d{1,2})\s+(?=\S)", body)
    if len(parts) == 1:
        return [body]
    # parts = ['', '1', '…', '2', '…']
    out, expect = [], 1
    for num, txt in zip(parts[1::2], parts[2::2]):
        if int(num) != expect:                 # 不是連續項次 → 視為條文內數字，併回上一項
            out[-1] += num + " " + txt if out else txt
            continue
        out.append(txt.strip()); expect += 1
    return out or [body]


def article_text(paras: list[str]) -> str:
    if len(paras) == 1:
        return paras[0]
    return "".join(f"{p}（第{i}項）" for i, p in enumerate(paras, 1))


def main(src: pathlib.Path, dst: pathlib.Path, poc_only: bool = False) -> None:
    result = []
    laws = WANTED if poc_only else {p.name.split(".pdf")[0]: None for p in sorted(src.glob("*.pdf*"))}
    for law, wanted in laws.items():
        pdf = next(src.glob(f"{law}.pdf*"))
        text = pdf_text(pdf)
        ver = version_date(text)
        arts = split_articles(text)
        for no in (wanted or sorted(arts, key=lambda k: [int(x) for x in k.split("-")])):
            paras = paragraphs(arts[no])
            result.append({
                "law": law, "article": no, "version_date": ver,
                "text": article_text(paras), "paragraphs": paras,
                "source": f"相關法規/{pdf.name}",
            })
            if poc_only:
                print(f"{law}第{no}條  {len(paras)} 項  {ver}")
    dst.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf8")
    print(f"→ {dst}（{len(result)} 條）")


if __name__ == "__main__":
    poc = "--poc" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--poc"]
    src = pathlib.Path(args[0])
    dst = pathlib.Path(args[1]) if len(args) > 1 else pathlib.Path(__file__).resolve().parents[2] / "data" / "statutes.json"
    main(src, dst, poc)
