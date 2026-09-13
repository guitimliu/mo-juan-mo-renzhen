"""抓新北市法制局訴願決定書（https://web.law.ntpc.gov.tw/Su_search01.aspx）。

用法（在 backend/ 執行）：
  python tools/crawl_ntpc_appeals.py list  [--years 2026 2025 ...]   # 列表 → data/ntpc_appeals/index.jsonl
  python tools/crawl_ntpc_appeals.py fetch [--conc 8]                # 明細 HTML → data/ntpc_appeals/raw/<年>/<案號>.html（可續跑）
  python tools/crawl_ntpc_appeals.py parse                           # raw → data/ntpc_appeals/decisions.jsonl
  python tools/crawl_ntpc_appeals.py all                             # 依序做完三步

機制：查詢頁 302 到純 GET；列表 Su_list02.aspx?sdate&edate&page（20 筆/頁），明細 Su_contents03.aspx（全文為 HTML）。
評估文件：docs/ntpc_appeal_decisions_crawl_analysis.md。
"""
from __future__ import annotations

import argparse
import asyncio
import html as htmllib
import json
import pathlib
import re
import sys
import time

import aiohttp

BASE = "https://web.law.ntpc.gov.tw"
UA = "mo-juan-mo-renzhen hackathon crawler (contact: z111048@gmail.com)"
OUT = pathlib.Path(__file__).resolve().parents[2] / "data" / "ntpc_appeals"
RAW = OUT / "raw"
INDEX = OUT / "index.jsonl"
DECISIONS = OUT / "decisions.jsonl"
YEARS = list(range(2026, 2003, -1))  # 新到舊，中途停也保有近年資料

ROW_RE = re.compile(
    r'<a[^>]+href="(/Scripts/Su_contents03\.aspx\?[^"]*EANO=(\d+)[^"]*)"[^>]*>(.*?)</a>', re.S)
DATE_RE = re.compile(r"(\d{3})\.(\d{2})\.(\d{2})")
TOTAL_RE = re.compile(r"查詢結果共計：(\d+)筆")


async def get(session: aiohttp.ClientSession, url: str, tries: int = 5) -> str:
    for i in range(tries):
        try:
            async with session.get(url) as r:
                if r.status == 200:
                    return await r.text(errors="replace")
                if r.status in (429, 503):
                    await asyncio.sleep(2 * (i + 1))
                    continue
                raise RuntimeError(f"HTTP {r.status} {url}")
        except (aiohttp.ClientError, asyncio.TimeoutError):
            await asyncio.sleep(1.5 * (i + 1))
    raise RuntimeError(f"give up {url}")


def parse_list(page_html: str) -> list[dict]:
    rows = []
    # 每列：<tr> ... 日期 ... <a href=...>標題</a> ... 案號
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", page_html, re.S):
        m = ROW_RE.search(tr)
        if not m:
            continue
        d = DATE_RE.search(re.sub(r"<[^>]+>", " ", tr))
        rows.append({
            "eano": m.group(2),
            "date": f"{int(d.group(1)) + 1911}-{d.group(2)}-{d.group(3)}" if d else None,
            "title": htmllib.unescape(re.sub(r"<[^>]+>", "", m.group(3))).strip(),
            "url": htmllib.unescape(m.group(1)),
        })
    return rows


async def cmd_list(years: list[int], conc: int) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    seen = {json.loads(l)["eano"] for l in INDEX.open(encoding="utf8")} if INDEX.exists() else set()
    sem = asyncio.Semaphore(conc)
    async with aiohttp.ClientSession(headers={"User-Agent": UA}, timeout=aiohttp.ClientTimeout(total=30)) as s:
        with INDEX.open("a", encoding="utf8") as out:
            for y in years:
                q = f"{BASE}/Scripts/Su_list02.aspx?sdate={y}0101&edate={y}1231"
                first = await get(s, q)
                total = int(TOTAL_RE.search(first).group(1)) if TOTAL_RE.search(first) else 0
                pages = (total + 19) // 20
                rows = parse_list(first)

                async def one(p: int) -> list[dict]:
                    async with sem:
                        return parse_list(await get(s, f"{q}&page={p}"))

                for chunk in await asyncio.gather(*(one(p) for p in range(2, pages + 1))):
                    rows += chunk
                new = 0
                for r in rows:
                    if r["eano"] in seen:
                        continue
                    seen.add(r["eano"]); new += 1
                    r["year"] = y
                    out.write(json.dumps(r, ensure_ascii=False) + "\n")
                out.flush()
                print(f"[list] {y}: total={total} pages={pages} got={len(rows)} new={new}", flush=True)


async def cmd_fetch(conc: int) -> None:
    items = [json.loads(l) for l in INDEX.open(encoding="utf8")]
    todo = [it for it in items if not (RAW / str(it["year"]) / f"{it['eano']}.html").exists()]
    print(f"[fetch] index={len(items)} todo={len(todo)} conc={conc}", flush=True)
    sem = asyncio.Semaphore(conc)
    done = fail = 0
    t0 = time.time()

    async def one(s: aiohttp.ClientSession, it: dict) -> None:
        nonlocal done, fail
        p = RAW / str(it["year"]) / f"{it['eano']}.html"
        async with sem:
            try:
                body = await get(s, BASE + it["url"])
                if "cph_content_trECASE" not in body and "全 文" not in body:
                    raise RuntimeError("unexpected page")
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(body, encoding="utf8")
                done += 1
            except Exception as e:  # noqa: BLE001
                fail += 1
                print(f"[fetch] FAIL {it['eano']}: {e}", flush=True)
        if (done + fail) % 500 == 0:
            rate = (done + fail) / (time.time() - t0)
            print(f"[fetch] {done+fail}/{len(todo)} ok={done} fail={fail} {rate:.1f}/s eta={(len(todo)-done-fail)/max(rate,0.1)/60:.1f}min", flush=True)

    async with aiohttp.ClientSession(headers={"User-Agent": UA}, timeout=aiohttp.ClientTimeout(total=60),
                                     connector=aiohttp.TCPConnector(limit=conc)) as s:
        await asyncio.gather(*(one(s, it) for it in todo))
    print(f"[fetch] done ok={done} fail={fail} in {(time.time()-t0)/60:.1f}min", flush=True)


def _text(fragment: str) -> str:
    t = re.sub(r"<br\s*/?>", "\n", fragment)
    t = re.sub(r"<[^>]+>", "", t)
    t = htmllib.unescape(t).replace("\xa0", " ")
    return "\n".join(line.rstrip() for line in t.split("\n")).strip()


def parse_detail(page: str) -> dict:
    """從明細頁抽欄位。表格列形如 <tr><th>案 號：</th><td>...</td></tr>。"""
    fields: dict[str, str] = {}
    for th, td in re.findall(r"<th[^>]*>(.*?)</th>\s*<td[^>]*>(.*?)</td>", page, re.S):
        key = re.sub(r"[\s:：]+", "", _text(th))
        fields[key] = _text(td)
    m_pre = re.search(r"<pre>(.*?)</pre>", page, re.S)
    full = _text(m_pre.group(1)) if m_pre else ""
    body = re.sub(r"\s+", " ", full)
    outcome = None
    m = re.search(r"主\s*文\s*(.{0,80})", body)
    if m:
        head = m.group(1)
        outcome = ("不受理" if "不受理" in head else "撤銷" if "撤銷" in head else "駁回" if "駁回" in head else "其他")
    title = fields.get("要旨", "")
    mt = re.search(r"因(.+?事件)", title)
    agency = re.search(r"原處分機關\s*([^\n]+)", full)
    laws = [l.strip() for l in re.split(r"[\n；;]", fields.get("相關法條", "")) if l.strip()]
    return {
        "eano": fields.get("案號"),
        "doc_no": fields.get("發文字號"),
        "date": fields.get("發文日期"),
        "title": title,
        "case_type": mt.group(1) if mt else None,
        "outcome": outcome,
        "agency": agency.group(1).strip() if agency else None,
        "laws": laws,
        "full_text": full,
    }


def cmd_parse() -> None:
    n = bad = 0
    with DECISIONS.open("w", encoding="utf8") as out:
        for p in sorted(RAW.glob("*/*.html")):
            d = parse_detail(p.read_text(encoding="utf8", errors="replace"))
            d["year"] = int(p.parent.name)
            if not d["eano"]:
                d["eano"] = p.stem
            if len(d["full_text"]) < 50:
                bad += 1
            out.write(json.dumps(d, ensure_ascii=False) + "\n"); n += 1
    print(f"[parse] {n} decisions → {DECISIONS} (short/empty full_text: {bad})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["list", "fetch", "parse", "all"])
    ap.add_argument("--years", type=int, nargs="*", default=YEARS)
    ap.add_argument("--conc", type=int, default=8)
    a = ap.parse_args()
    if a.cmd in ("list", "all"):
        asyncio.run(cmd_list(a.years, a.conc))
    if a.cmd in ("fetch", "all"):
        asyncio.run(cmd_fetch(a.conc))
    if a.cmd in ("parse", "all"):
        cmd_parse()


if __name__ == "__main__":
    sys.exit(main())
