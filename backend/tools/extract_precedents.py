# -*- coding: utf-8 -*-
"""從主辦方「司法院釋字及行政判解」PDF 取判決要旨片段 → data/precedents.json（stub 檢索用）。

用法：python tools/extract_precedents.py <司法院釋字及行政判解資料夾> [輸出檔]

只取 POC 需要的三篇（06_標準答案 acceptable_alternatives）；摘要＝判決原文中含關鍵句的段落，
不做改寫。PDF 有文字層（部分檔 pdftotext 會報 flate 警告，文字仍可用）。
"""
import json
import pathlib
import re
import subprocess
import sys

WANTED = [
    {"id": "最高行政法院108年度判字第531號", "glob": "最高行政法院108年度判字第531號*", "topic": "行政罰法7條1項 故意過失",
     "anchor": "所謂故意，係指", "before": 60, "after": 260},
    {"id": "最高行政法院109年度上字第780號", "glob": "最高行政法院109年度上字第780號*", "topic": "行政罰法7條1項 故意過失",
     "anchor": "所謂故意，係指", "before": 60, "after": 260},
    {"id": "臺北高等行政法院114年度簡上字第13號", "glob": "臺北高等行政法院114年度簡上字第13號*", "topic": "洗錢防制法22條 帳戶控制權之認定",
     "anchor": "前開立法理由所稱具有帳戶、帳號之控制權", "before": 0, "after": 200},
]


def pdf_text(path: pathlib.Path) -> str:
    out = subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True)
    return out.stdout.decode("utf8", errors="ignore")


def clean(text: str) -> str:
    """去掉司法院判決書版面：每行開頭的行號、頁碼、頁首；折行合併。"""
    lines = []
    for line in text.splitlines():
        line = re.sub(r"^\s*\d{1,2}\s+(?=\S)", "", line)   # 行號 "01 "
        line = line.strip()
        if not line or re.fullmatch(r"\d+", line):
            continue
        lines.append(line)
    return re.sub(r"\s+", "", "".join(lines))


def excerpt(text: str, anchor: str, before: int, after: int) -> str:
    i = text.find(anchor)
    if i < 0:
        raise SystemExit(f"找不到錨句：{anchor}")
    s = max(0, i - before)
    seg = text[s:i + after]
    # 對齊句界：往前找到上一個句號之後，往後截到最後一個句號
    if "。" in seg[:before + 1] and before:
        seg = seg[seg.index("。") + 1:]
    seg = seg[:seg.rfind("。") + 1] if "。" in seg else seg
    return seg.lstrip("」』）)")


def main(src: pathlib.Path, dst: pathlib.Path) -> None:
    result = []
    for w in WANTED:
        pdf = next(src.glob(w["glob"]))
        body = clean(pdf_text(pdf))
        result.append({"id": w["id"], "topic": w["topic"], "excerpt": excerpt(body, w["anchor"], w["before"], w["after"]),
                       "source": f"司法院釋字及行政判解/{pdf.name}"})
        print(w["id"], len(result[-1]["excerpt"]), "字")
    dst.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf8")
    print("→", dst)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    src = pathlib.Path(sys.argv[1])
    dst = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else pathlib.Path(__file__).resolve().parents[2] / "data" / "precedents.json"
    main(src, dst)
