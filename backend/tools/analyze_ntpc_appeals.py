"""分析 data/ntpc_appeals/decisions.jsonl（26,607 篇新北訴願決定書），產出：
  data/law_index.json            — 法條索引：案型 → 高頻條文（含裁決分布），供 S3 檢索補法條（bedrock.statutes_for）
  data/ntpc_appeals/stats.json   — 各項統計原始數字
  docs/ntpc_appeals_analysis.md  — 人讀的分析報告
用法：python tools/analyze_ntpc_appeals.py
"""
from __future__ import annotations

import collections
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "data" / "ntpc_appeals" / "decisions.jsonl"
LAW_INDEX = ROOT / "data" / "law_index.json"
STATS = ROOT / "data" / "ntpc_appeals" / "stats.json"
REPORT = ROOT / "docs" / "ntpc_appeals_analysis.md"
STATUTES = ROOT / "data" / "statutes.json"

LAW_RE = re.compile(r"^(.+?)\s*第\s*(.+?)\s*條$")
ART77_RE = re.compile(r"第\s*77\s*條第\s*(\d+)\s*款")
COURT_RE = re.compile(r"(最高行政法院|臺北高等行政法院|臺灣[^\s，。、]{1,4}地方法院)\s*(\d+)\s*年度?\s*([一-鿿]{1,4})字第\s*(\d+)\s*號")
REASON_RE = re.compile(r"立法理由第\s*(\d+)\s*點")
TEXT_LAW_RE = re.compile(r"([\u4e00-\u9fff（）]{2,30}?(?:法|條例|規則|辦法|基準|細則|準則|規程))第\s*(\d+)\s*條(?:之\s*(\d+))?")


def text_laws(full: str, names: list[str]) -> set[tuple[str, str]]:
    """從全文抽「○○法第 N 條」，法規名以已知名稱（最長尾綴）正規化；抓不到名稱的（如「同法」）略過。"""
    out = set()
    for m in TEXT_LAW_RE.finditer(full):
        raw = m[1]
        name = next((n for n in names if raw.endswith(n)), None)
        if name:
            out.add((name, m[2] + (f"-{m[3]}" if m[3] else "")))
    return out


def expand(law_str: str) -> list[tuple[str, str]]:
    """'廢棄物清理法 第 27、50 條' → [('廢棄物清理法','27'),('廢棄物清理法','50')]；'第 15 之 2 條' → '15-2'。"""
    m = LAW_RE.match(law_str.strip())
    if not m:
        return []
    law, arts = m.group(1).strip(), m.group(2)
    out = []
    for a in re.split(r"[、,，]", arts):
        a = a.strip().replace(" ", "")
        a = re.sub(r"之", "-", a)
        if a:
            out.append((law, a))
    return out


def main() -> None:
    rows = [json.loads(l) for l in SRC.open(encoding="utf8")]
    statutes = {(r["law"], r["article"]) for r in json.loads(STATUTES.read_text(encoding="utf8"))}
    n = len(rows)

    by_year = collections.Counter(r["year"] for r in rows)
    outcome = collections.Counter(r["outcome"] for r in rows)
    outcome_year = collections.defaultdict(collections.Counter)
    ctype = collections.Counter(r["case_type"] for r in rows)
    ctype_outcome = collections.defaultdict(collections.Counter)
    agency = collections.Counter(r["agency"] for r in rows)
    agency_outcome = collections.defaultdict(collections.Counter)
    law_cnt = collections.Counter()
    law_outcome = collections.defaultdict(collections.Counter)
    ctype_law = collections.defaultdict(collections.Counter)
    ctype_law_outcome = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    tlaw_cnt = collections.Counter()
    ctype_tlaw = collections.defaultdict(collections.Counter)
    ctype_tlaw_outcome = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    names = sorted({expand(l)[0][0] for r in rows for l in r["laws"] if expand(l)} | {a for a, _ in statutes}, key=len, reverse=True)
    art77 = collections.Counter()
    courts = collections.Counter()
    reasons = collections.Counter()
    length = []

    for r in rows:
        o, ct = r["outcome"], r["case_type"] or "（未分類）"
        outcome_year[r["year"]][o] += 1
        ctype_outcome[ct][o] += 1
        agency_outcome[r["agency"] or "（未知）"][o] += 1
        seen = set()
        for l in r["laws"]:
            for ref in expand(l):
                if ref in seen:
                    continue
                seen.add(ref)
                law_cnt[ref] += 1
                law_outcome[ref][o] += 1
                ctype_law[ct][ref] += 1
                ctype_law_outcome[ct][ref][o] += 1
        for ref in text_laws(r["full_text"], names):
            tlaw_cnt[ref] += 1
            ctype_tlaw[ct][ref] += 1
            ctype_tlaw_outcome[ct][ref][o] += 1
        if o == "不受理":
            for k in set(ART77_RE.findall(r["full_text"])):
                art77[k] += 1
        for m in COURT_RE.finditer(r["full_text"]):
            courts[f"{m[1]}{m[2]}年度{m[3]}字第{m[4]}號"] += 1
        for k in REASON_RE.findall(r["full_text"]):
            reasons[k] += 1
        length.append(len(r["full_text"]))

    # ---- 法條索引：每個案型（≥30 篇）取引用率 ≥ 5% 的條文，標記是否在 statutes.json 有全文
    law_index = {}
    for ct, cnt in ctype.items():
        if not ct or cnt < 30:
            continue
        items = []
        for ref, c in ctype_law[ct].most_common(40):
            share = c / cnt
            if share < 0.05:
                break
            oc = ctype_law_outcome[ct][ref]
            items.append({"law": ref[0], "article": ref[1], "count": c, "share": round(share, 3),
                          "in_statutes": ref in statutes,
                          "outcome": {k: oc[k] for k in ("駁回", "撤銷", "不受理") if oc[k]}})
        titems = []
        for ref, c in ctype_tlaw[ct].most_common(60):
            share = c / cnt
            if share < 0.05:
                break
            oc = ctype_tlaw_outcome[ct][ref]
            titems.append({"law": ref[0], "article": ref[1], "count": c, "share": round(share, 3),
                           "in_statutes": ref in statutes,
                           "outcome": {k: oc[k] for k in ("駁回", "撤銷", "不受理") if oc[k]}})
        law_index[ct] = {"cases": cnt, "outcome": dict(ctype_outcome[ct]), "laws": items, "laws_in_text": titems}
    LAW_INDEX.write_text(json.dumps({"source": "新北市法制局訴願決定書 2004–2026（26,607 篇）", "n": n, "case_types": law_index},
                                    ensure_ascii=False, indent=1), encoding="utf8")

    stats = {
        "n": n, "by_year": dict(sorted(by_year.items())), "outcome": dict(outcome),
        "outcome_year": {y: dict(c) for y, c in sorted(outcome_year.items())},
        "case_type_top": [(k, v, dict(ctype_outcome[k])) for k, v in ctype.most_common(40)],
        "agency_top": [(k, v, dict(agency_outcome[k])) for k, v in agency.most_common(25)],
        "law_top": [(f"{a} 第 {b} 條", v, dict(law_outcome[(a, b)]), (a, b) in statutes) for (a, b), v in law_cnt.most_common(60)],
        "text_law_top": [(f"{a} 第 {b} 條", v, (a, b) in statutes) for (a, b), v in tlaw_cnt.most_common(60)],
        "art77": dict(art77.most_common()), "courts_top": courts.most_common(30), "reasons_top": reasons.most_common(10),
        "len_median": sorted(length)[len(length) // 2],
        "laws_not_in_statutes": [(f"{a} 第 {b} 條", v) for (a, b), v in law_cnt.most_common(300) if (a, b) not in statutes][:40],
    }
    STATS.write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf8")

    # ---- 報告
    def pct(c, t):
        return f"{100 * c / t:.0f}%" if t else "-"

    def oc_str(oc):
        t = sum(oc.values())
        return "／".join(f"{k} {pct(oc.get(k, 0), t)}" for k in ("駁回", "撤銷", "不受理"))

    md = [f"# 新北市訴願決定書 2004–2026 量化分析（{n:,} 篇）", "",
          "資料：`data/ntpc_appeals/decisions.jsonl`（`backend/tools/crawl_ntpc_appeals.py` 抓自法制局網站）；本報告由 `backend/tools/analyze_ntpc_appeals.py` 產生。",
          "", "## 1. 年度與裁決", "",
          f"整體：駁回 {pct(outcome['駁回'], n)}、不受理 {pct(outcome['不受理'], n)}、撤銷 {pct(outcome['撤銷'], n)}（撤銷率＝訴願人「贏」的比例）。", "",
          "| 年 | 篇數 | 駁回 | 撤銷 | 不受理 | 撤銷率 |", "|---|---|---|---|---|---|"]
    for y, c in sorted(outcome_year.items()):
        t = sum(c.values())
        md.append(f"| {y} | {t} | {c['駁回']} | {c['撤銷']} | {c['不受理']} | {pct(c['撤銷'], t)} |")
    md += ["", "## 2. 案件類型（前 25）", "", "| 案型 | 篇數 | 裁決分布 |", "|---|---|---|"]
    for k, v in ctype.most_common(25):
        md.append(f"| {k} | {v} | {oc_str(ctype_outcome[k])} |")
    md += ["", "## 3. 原處分機關（前 15）", "", "| 機關 | 篇數 | 裁決分布 |", "|---|---|---|"]
    for k, v in agency.most_common(16):
        if k:
            md.append(f"| {k} | {v} | {oc_str(agency_outcome[k])} |")
    md += ["", "## 4. 最常引用條文（前 40）", "", "「全文在 statutes.json」＝現有 2,214 條法規表已有該條全文，可直接供 S3 帶入。", "",
           "| 條文 | 篇數 | 裁決分布 | 全文在 statutes.json |", "|---|---|---|---|"]
    for name, v, oc, ok in stats["law_top"][:40]:
        md.append(f"| {name} | {v} | {oc_str(oc)} | {'✅' if ok else '❌'} |")
    md += ["", "### 4.1 高頻但 statutes.json 沒有全文的條文（前 25）— 擴充法規表的優先清單", "", "| 條文 | 篇數 |", "|---|---|"]
    for name, v in stats["laws_not_in_statutes"][:25]:
        md.append(f"| {name} | {v} |")
    md += ["", "## 5. 不受理案：訴願法第 77 條款次", "", "| 款 | 篇數 | 要件（77 條）|", "|---|---|---|"]
    art77_desc = {"1": "訴願書不合法定程式不能補正或逾期不補正", "2": "提起訴願逾法定期間", "3": "訴願人不符合第 18 條規定（非處分相對人／利害關係人）", "4": "訴願人無訴願能力而未由法定代理人代為訴願",
                  "5": "地方自治團體、法人、非法人團體未由代表人或管理人為訴願行為", "6": "行政處分已不存在", "7": "對已決定或已撤回之訴願事件重行提起", "8": "對於非行政處分或其他依法不屬訴願救濟範圍內之事項提起訴願"}
    for k, v in sorted(art77.items(), key=lambda kv: -kv[1]):
        md.append(f"| 第 {k} 款 | {v} | {art77_desc.get(k, '')} |")
    md += ["", "## 6. 決定書引用的法院判決（前 20）", "", "| 判決 | 篇數 |", "|---|---|"]
    for k, v in courts.most_common(20):
        md.append(f"| {k} | {v} |")
    md += ["", "## 7. 洗錢防制法案（demo 案型）", ""]
    ct = "違反洗錢防制法事件"
    if ct in law_index:
        li = law_index[ct]
        md += [f"篇數 {li['cases']}，裁決：{oc_str(li['outcome'])}。**「相關法條」欄位只列程序法，實體條文要從全文抽**——以下為全文抽取、引用率 ≥5% 的條文：", "", "| 條文 | 篇數 | 引用率 | 裁決分布 | statutes.json |", "|---|---|---|---|---|"]
        for it in li["laws_in_text"]:
            md.append(f"| {it['law']} 第 {it['article']} 條 | {it['count']} | {pct(it['count'], li['cases'])} | {oc_str(it['outcome'])} | {'✅' if it['in_statutes'] else '❌'} |")
        yrs = collections.Counter(r["year"] for r in rows if r["case_type"] == ct)
        md += ["", "年度分布：" + "、".join(f"{y} 年 {c}" for y, c in sorted(yrs.items()) if c)]
        md += ["", "立法理由點次引用（全體）：" + "、".join(f"第 {k} 點 {v} 篇" for k, v in reasons.most_common(6))]
    md += ["", "### 7.1 全文抽取的高頻條文（全體，前 30）", "", "| 條文 | 篇數 | statutes.json |", "|---|---|---|"]
    for name, v, ok in stats["text_law_top"][:30]:
        md.append(f"| {name} | {v} | {'✅' if ok else '❌'} |")
    md += ["", "## 8. 法條索引（`data/law_index.json`）", "",
           f"共 {len(law_index)} 個案型（≥30 篇）→ 引用率 ≥5% 的條文（`laws`＝網站「相關法條」欄位；`laws_in_text`＝全文抽取，含實體法），含裁決分布與是否有全文。S3 檢索用法：S2 的案由對到案型後，把索引裡的高頻條文（有全文者）補進 `statutes`，標註「歷史 N 篇同案型中 M% 引用」。",
           "", f"全文長度中位數 {stats['len_median']:,} 字。"]
    REPORT.write_text("\n".join(md) + "\n", encoding="utf8")
    print(f"law_index: {len(law_index)} case types → {LAW_INDEX}\nreport → {REPORT}")


if __name__ == "__main__":
    main()
