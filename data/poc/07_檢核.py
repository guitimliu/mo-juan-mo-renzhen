# -*- coding: utf-8 -*-
"""S5 檢核：對 S4 決定書草稿打分，輸出 JSON 報告 + 人讀表。

用法：
  python3 07_檢核.py draft.json [retrieval.json]      # 檢核一份草稿
  python3 07_檢核.py --selftest                        # 用正本與一份弱草稿自測

草稿格式見 03_介面規格.md 的 S4；retrieval.json 為 S3 輸出（可省略，省略時跳過「引用是否經檢索」）。
"""
import json, re, sys, pathlib

HERE = pathlib.Path(__file__).resolve().parent
GOLD = json.loads((HERE / "06_標準答案_引用清單.json").read_text(encoding="utf8"))
NORM = lambda s: re.sub(r"\s+", "", s or "")
CN = "一二三四五六七八九十"
# 已知法規名（由 101 件決定書表頭彙整），用來錨定「○○法第N條」的抽取，避免把前面的動詞一起抓進來
LAWS = ["新北市政府處理違反建築法使用管理規定事件裁罰基準", "新北市裝潢修繕廢棄物簡易分類場輔導管理暫行要點", "行政院及各級行政機關訴願審議委員會審議規則", "一般廢棄物回收清除處理辦法", "化粧品衛生安全管理法", "道路交通管理處罰條例", "違章建築處理辦法", "個人資料保護法", "政府資訊公開法", "工廠管理輔導法", "空氣污染防制法", "文化資產保存法", "都市更新條例", "土地法施行法", "廢棄物清理法", "洗錢防制法", "行政訴訟法", "噪音管制法", "行政程序法", "刑事訴訟法", "行政執行法", "環境教育法", "作業要點", "行政罰法", "土地法", "建築法", "公司法", "檔案法", "訴願法", "刑法", "民法"]

def cn_ordinal(s):
    m = re.match(r"([%s]+)、" % CN, s)
    if not m: return None
    t = m.group(1)
    if len(t) == 1: return CN.index(t) + 1
    if t[0] == "十": return 10 + (CN.index(t[1]) + 1 if len(t) > 1 else 0)
    return None

def check(draft, retrieval=None):
    R = {"checks": [], "score": {}}
    add = lambda group, name, ok, note="": R["checks"].append({"group": group, "item": name, "pass": bool(ok), "note": note})

    facts   = NORM(draft.get("facts"))
    reasons = [NORM(x) for x in draft.get("reasons") or []]
    body    = facts + "".join(reasons)
    holding = NORM(draft.get("holding"))
    instr   = NORM(draft.get("instruction"))

    # ---- 1 段落齊全 ----
    for k, v in [("主文", holding), ("事實", facts), ("理由", "".join(reasons)), ("教示", instr)]:
        add("段落", f"{k}存在", bool(v))
    hdr = draft.get("header") or {}
    add("段落", "表頭含訴願人／機關／處分文號", all(hdr.get(k) for k in ("appellant", "agency", "disposition_ref")))

    # ---- 2 格式固定句 ----
    add("格式", "事實以「緣」起首", facts.startswith("緣"))
    add("格式", "事實含「茲摘敘訴辯意旨於次」", "茲摘敘訴辯意旨於次" in facts)
    add("格式", "事實含「一、訴願意旨略謂」", "訴願意旨略謂" in facts)
    add("格式", "事實含「二、答辯意旨略謂」", "答辯意旨略謂" in facts)
    add("格式", "理由第一項以「一、按」起首", bool(reasons) and reasons[0].startswith("一、按"))
    ords = [cn_ordinal(r) for r in reasons]
    add("格式", "理由項次連續編號", ords and ords == list(range(1, len(ords) + 1)), f"實際 {ords}")
    add("格式", "理由末項含「綜上論結」", bool(reasons) and "綜上論結" in reasons[-1])
    add("格式", "理由末項引用訴願法第79條第1項", bool(reasons) and "訴願法第79條第1項" in reasons[-1])
    add("格式", "理由 4–10 項", 4 <= len(reasons) <= 10, f"{len(reasons)} 項")

    # ---- 3 主文 / 教示 ----
    add("結論", "主文＝訴願駁回。", holding == NORM(GOLD["holding"]), holding)
    add("結論", f"教示指向{GOLD['instruction_court']}", GOLD["instruction_court"] in instr)
    add("結論", "教示含 2 個月", "2個月" in instr)

    # ---- 4 事實要素 ----
    miss = [k for k in GOLD["facts_must_contain"] if NORM(k) not in facts]
    add("事實", f"關鍵事實要素 {len(GOLD['facts_must_contain'])-len(miss)}/{len(GOLD['facts_must_contain'])}", not miss, "缺：" + "、".join(miss) if miss else "")

    # ---- 5 引用召回 ----
    def recall(items, label):
        hit = [i["id"] for i in items if NORM(i["id"]) in body]
        add("引用", f"{label} {len(hit)}/{len(items)}", len(hit) == len(items), "缺：" + "、".join(i["id"] for i in items if i["id"] not in hit) if len(hit) < len(items) else "")
        return len(hit), len(items)
    s = recall(GOLD["statutes"], "法條")
    lr_hit = [i["id"] for i in GOLD["legislative_reasons"]
              if all(NORM(k) in body for k in re.findall(r"第\d+條之\d+|立法理由第\d+點", i["id"]))]
    add("引用", f"立法理由 {len(lr_hit)}/{len(GOLD['legislative_reasons'])}", len(lr_hit) == len(GOLD["legislative_reasons"]),
        "缺：" + "、".join(i["id"] for i in GOLD["legislative_reasons"] if i["id"] not in lr_hit) if len(lr_hit) < len(GOLD["legislative_reasons"]) else "")
    j_hit = [i["id"] for i in GOLD["judgments"] if NORM(i["id"]) in body]
    alt_hit = [i["id"] for i in GOLD["acceptable_alternatives"] if NORM(i["id"]) in body]
    add("引用", f"正本判決 {len(j_hit)}/{len(GOLD['judgments'])}（皆不在資料集，缺為預期）", True, "、".join(j_hit))
    add("引用", f"可接受替代引用 {len(alt_hit)}/{len(GOLD['acceptable_alternatives'])}", len(alt_hit) > 0 or len(j_hit) > 0, "、".join(alt_hit))

    # ---- 6 論理要點 ----
    pts = []
    for p in GOLD["reasoning_points"]:
        ok = all(NORM(k) in body for k in p["keywords"])
        pts.append(ok); add("論理", f"{p['id']} {p['point']}", ok)
    ev = [e for e in GOLD["evidence"] if NORM(e) in body]
    add("論理", f"卷內證據提及 {len(ev)}/{len(GOLD['evidence'])}", len(ev) >= 2, "、".join(ev))

    # ---- 7 引用是否有據（防幻覺）----
    cited_articles = set(re.findall(r"(?:%s)第\d+條(?:之\d+)?(?:第\d+項)?" % "|".join(map(re.escape, LAWS)), body))
    allowed = {NORM(i["id"]) for i in GOLD["statutes"] + GOLD["acceptable_alternatives"] + GOLD["legislative_reasons"]}
    if retrieval:
        for st in retrieval.get("statutes", []):
            allowed.add(NORM(f"{st['law']}第{st['article']}條"))
    def grounded(a):
        base = re.sub(r"第\d+項$", "", a)
        return any(x.startswith(base) or base.startswith(x) for x in allowed)
    ungrounded = sorted(a for a in cited_articles if not grounded(a))
    add("防幻覺", f"引用法條皆有據（{len(cited_articles)-len(ungrounded)}/{len(cited_articles)}）", not ungrounded, "未經檢索／非標準答案：" + "、".join(ungrounded) if ungrounded else "")
    cites = draft.get("citations") or []
    add("防幻覺", f"citations 皆帶 source（{sum(1 for c in cites if c.get('source'))}/{len(cites)}）", cites and all(c.get("source") for c in cites), "" if cites else "草稿未回傳 citations")
    if retrieval:
        ids = {NORM(x["id"]) for k in ("precedents", "interpretations", "similar_cases") for x in retrieval.get(k, [])}
        judg = set(re.findall(r"(?:最高行政法院|臺北高等行政法院|臺中高等行政法院|高雄高等行政法院)?\d+年度[判裁上訴簡]+字第\d+號", body))
        bad = sorted(x for x in judg if not any(NORM(x) in i or i in NORM(x) for i in ids))
        add("防幻覺", f"引用判決皆在檢索結果內（{len(judg)-len(bad)}/{len(judg)}）", not bad, "未檢索到：" + "、".join(bad) if bad else "")

    # ---- 分數 ----
    groups = {}
    for c in R["checks"]:
        g = groups.setdefault(c["group"], [0, 0]); g[1] += 1; g[0] += c["pass"]
    R["score"] = {g: f"{p}/{n}" for g, (p, n) in groups.items()}
    total = sum(c["pass"] for c in R["checks"]); R["score"]["總分"] = f"{total}/{len(R['checks'])}"
    R["score"]["論理要點"] = f"{sum(pts)}/{len(pts)}"
    return R

def show(R):
    w = max(len(c["item"]) for c in R["checks"])
    for c in R["checks"]:
        print(f"  {'✔' if c['pass'] else '✘'} [{c['group']}] {c['item']}" + (f"　← {c['note']}" if c["note"] and not c["pass"] else ""))
    print("  " + "  ".join(f"{k} {v}" for k, v in R["score"].items()))

def draft_from_gold():
    """把正本 00_ 檔轉成 S4 草稿格式，應得滿分（正本判決三篇不在資料集，屬預期）。"""
    md = (HERE / "00_標準答案_113-16_原決定書.md").read_text(encoding="utf8")
    sec = lambda name: re.search(r"## %s\n(.*?)(?=\n## |\Z)" % name, md, re.S).group(1).strip()
    reasons = re.split(r"(?=(?:^|(?<=。))[%s]+、)" % CN, sec("理由"))
    reasons = [r for r in reasons if r.strip() and cn_ordinal(r)]
    return {"header": {"appellant": "王小明", "agency": "新北市政府警察局新店分局", "disposition_ref": "113年9月1日新北警店刑字第1134082840號"},
            "holding": sec("主文"), "facts": sec("事實"), "reasons": reasons,
            "instruction": "如不服本決定，得於決定書送達之次日起2個月內向臺北高等行政法院提起行政訴訟。",
            "citations": [{"text": "洗錢防制法第22條第1項", "source": "statutes[0]"}]}

WEAK = {"header": {"appellant": "王小明", "agency": "新北市政府警察局新店分局"},
        "holding": "訴願駁回。",
        "facts": "訴願人被詐騙集團騙走提款卡，帳戶被列為警示帳戶，警察局裁處告誡。訴願人主張沒有故意。",
        "reasons": ["一、按洗錢防制法第22條規定不得將帳戶交付他人使用。", "二、訴願人交付提款卡，違反規定。",
                    "三、依行政罰法第14條及個人資料保護法第20條，訴願人應負責。", "四、綜上，訴願駁回。"],
        "instruction": "如不服本決定，得向臺灣新北地方法院行政訴訟庭提起行政訴訟。", "citations": []}

if __name__ == "__main__":
    if "--selftest" in sys.argv:
        print("=== 正本轉草稿（預期：除三篇外部判決外全過）==="); show(check(draft_from_gold()))
        print("\n=== 弱草稿（預期：大量 ✘，含幻覺法條）==="); show(check(WEAK))
        sys.exit(0)
    draft = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf8"))
    retrieval = json.loads(pathlib.Path(sys.argv[2]).read_text(encoding="utf8")) if len(sys.argv) > 2 else None
    R = check(draft, retrieval); show(R)
    out = pathlib.Path(sys.argv[1]).with_suffix(".check.json"); out.write_text(json.dumps(R, ensure_ascii=False, indent=1), encoding="utf8")
    print("→", out)
