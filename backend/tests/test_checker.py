# -*- coding: utf-8 -*-
"""checker.py：07 包裝、附錄 C summary、弱草稿能被抓出來。"""
from app import checker


def test_covered_exact_article_not_prefix():
    assert checker._covered("訴願法第79條第1項", {"訴願法第79條"}) is True
    assert checker._covered("訴願法第79條第1項", {"訴願法第7條"}) is False      # 不能用前綴誤涵蓋
    assert checker._covered("洗錢防制法第15條之2立法理由第3點", {"洗錢防制法第15條之2立法理由第3點"}) is True
    assert checker._covered("臺北高等行政法院113年度簡字第243號", {"最高行政法院109年度上字第780號"}) is False


def test_gold_draft_scores_30_of_30_without_retrieval():
    r = checker.run(checker.draft_from_gold())
    assert r["score"]["總分"] == "30/30" and r["summary"]["holding_match"] is True
    assert r["summary"]["gold_citations_missed"] == []          # 沒檢索結果時退回「本文是否出現」；正本三篇判決都在本文


def test_weak_draft_flags_hallucinated_statutes():
    weak = checker.load_checker().WEAK
    r = checker.run(weak)
    total, n = r["score"]["總分"].split("/")
    assert int(total) < 12 and int(n) == 30
    hallu = next(c for c in r["checks"] if c["item"].startswith("引用法條皆有據"))
    assert hallu["pass"] is False and "行政罰法第14條" in hallu["note"] and "個人資料保護法第20條" in hallu["note"]
    assert r["summary"]["citation_total"] == 0 and r["summary"]["sections_present"]["教示"] is True


def test_summary_citation_grounded_requires_resolvable_source():
    draft = checker.draft_from_gold()
    draft["citations"] = [{"text": "洗錢防制法第22條第1項", "source": "statutes[0]"}, {"text": "洗錢防制法第22條第1項", "source": "statutes[9]"}, {"text": "洗錢防制法第22條第1項", "source": ""}]
    retrieval = {"statutes": [{"law": "洗錢防制法", "article": "22"}], "precedents": [], "interpretations": [], "similar_cases": []}
    s = checker.summarize(checker.check(draft, retrieval), draft, retrieval)
    assert s["citation_total"] == 3 and s["citation_grounded"] == 1


def test_summary_citation_grounded_requires_text_to_match_source():
    """幻覺引用即使 source 寫 statutes[0]，text 對不上該法條也不算 grounded。"""
    draft = checker.draft_from_gold()
    draft["citations"] = [
        {"text": "洗錢防制法第22條第1項", "source": "statutes[0]"},           # 對
        {"text": "個人資料保護法第20條", "source": "statutes[0]"},            # text 與 statutes[0] 不符
        {"text": "最高行政法院999年度判字第1號", "source": "precedents[0]"},  # id 不符
        {"text": "最高行政法院109年度上字第780號", "source": "precedents[0]"},  # 對
    ]
    retrieval = {"statutes": [{"law": "洗錢防制法", "article": "22"}], "precedents": [{"id": "最高行政法院109年度上字第780號"}],
                 "interpretations": [], "similar_cases": []}
    s = checker.summarize(checker.check(draft, retrieval), draft, retrieval)
    assert s["citation_total"] == 4 and s["citation_grounded"] == 2


def test_run_tolerates_malformed_s4_and_s3():
    """Bedrock 生成格式稍有出入（header 是字串、citations 是字串陣列、reasons 含數字）不應讓 S5 炸掉。"""
    bad = {"header": "x", "holding": None, "facts": 123, "reasons": ["一、按", 2, None], "instruction": ["a"], "citations": ["statutes[0]"], "gaps": "g"}
    r = checker.run(bad, {"statutes": None, "precedents": "x", "interpretations": [{"no_id": 1}], "similar_cases": [{"id": "113-15"}]})
    assert r["score"]["總分"].endswith("/31") and r["summary"]["citation_total"] == 0
    r = checker.run("not a dict", None)
    assert r["summary"]["sections_present"] == {"主文": False, "事實": False, "理由": False, "教示": False}
