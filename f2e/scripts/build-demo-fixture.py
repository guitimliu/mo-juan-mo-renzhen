"""【已棄用 2026-09-12】舊工作包時期的 fixture 產生器（舊形狀、教示法院為地院）。

現在 src/data/pipeline.json 是附錄 A envelope，請改用後端：cd backend && python -m app.fixture
保留本檔僅供對照，執行會覆蓋 pipeline.json 成舊形狀（demo.ts 仍可讀，但內容是舊版）。
"""
import sys
if "--force" not in sys.argv:
    sys.exit("已棄用：請改用 `cd backend && python -m app.fixture`（加 --force 仍可執行舊流程）")
import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'data' / 'poc'
spec_text = (PACKAGE / '03_介面規格.md').read_text(encoding='utf-8')
decoder = json.JSONDecoder()

def stage(name):
    section = spec_text.split('## ' + name + ' ', 1)[1].split('\n## ', 1)[0]
    return decoder.raw_decode(section[section.index('{'):])[0]

def document(name):
    return '\n'.join(line for line in (PACKAGE / name).read_text(encoding='utf-8').splitlines()
                     if not line.startswith(('#', '>'))).strip()

module_spec = importlib.util.spec_from_file_location('poc_checker', PACKAGE / '07_檢核.py')
checker = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(checker)
gold = json.loads((PACKAGE / '06_標準答案_引用清單.json').read_text(encoding='utf-8'))
gold_md = (PACKAGE / '00_標準答案_113-16_原決定書.md').read_text(encoding='utf-8')
draft = checker.draft_from_gold()
# Preserve the supplied original's instruction; surface disagreement with the template.
draft['instruction'] = gold_md.split('## 教示（原件末尾）', 1)[1].strip()
draft['header']['case_type'] = '違反洗錢防制法事件'
draft['citations'] = [
    {'text': '洗錢防制法第22條第1項', 'source': 'statutes[0]'},
    {'text': '洗錢防制法第22條第2項', 'source': 'statutes[0]'},
    {'text': '訴願法第79條第1項', 'source': 'statutes[1]'},
    {'text': '洗錢防制法第15條之2立法理由第3點', 'source': 'interpretations[0]'},
    {'text': '洗錢防制法第15條之2立法理由第5點', 'source': 'interpretations[1]'},
]
draft['gaps'] = ['需承辦人補查：' + item['id'] + '（正本引用，但本次模擬檢索未收錄）' for item in gold['judgments']]
draft['gaps'].append('教示法院待團隊確認：00 原決定書與 03 介面範例為臺灣新北地方法院行政訴訟庭；04 模板與 06 引用清單為臺北高等行政法院。')
retrieval = stage('S3')
retrieval['statutes'][0]['text'] = re.search('「(.*?)」', draft['reasons'][0]).group(1)
retrieval['statutes'].append({'law': '訴願法', 'article': '79', 'text': '正本引用：' + draft['reasons'][-1], 'version_date': '待核對'})
retrieval['precedents'][0]['excerpt'] = '模擬檢索摘要：行政罰法第7條第1項的故意過失認定。這是工作包指定的示範檢索結果，尚未連接裁判原文。'
quotes = re.findall('「(.*?)」', draft['reasons'][2])
retrieval['interpretations'] = [
    {'id': gold['legislative_reasons'][0]['id'], 'excerpt': quotes[0]},
    {'id': gold['legislative_reasons'][1]['id'], 'excerpt': next(q for q in quotes if q.startswith('五、'))},
]
report = checker.check(draft, retrieval)
body = draft['facts'] + ''.join(draft['reasons'])
expected = [i['id'] for group in ['statutes', 'legislative_reasons', 'judgments'] for i in gold[group]]
retrieved_ids = {x['law'] + '第' + x['article'] + '條' for x in retrieval['statutes']}
retrieved_ids.update(x['id'] for x in retrieval['interpretations'] + retrieval['precedents'])
recalled = [x for x in expected if any(x.startswith(y) or y == x for y in retrieved_ids)]
fixture = {
    'provenance': '正本轉製的固定展示資料；非即時 OCR、检索或 AI 生成。S5 詳細報告由提供的 07_檢核.py 對此草稿與模擬檢索資料計算。',
    'case_id': 'poc-001',
    's1': {'case_id': 'poc-001', 'petition_text': document('01_模擬訴願書.md'), 'disposition_text': document('02_模擬書面告誡.md'), 'ocr_confidence_note': '固定展示文字，來自團隊模擬文件；尚未執行 OCR，不提供虛構信心分數。'},
    's2': stage('S2'),
    'procedure': stage('S2.5'),
    's3': retrieval,
    's4': draft,
    's5': {'sections_present': {name: bool(draft[key]) for name, key in [('主文', 'holding'), ('事實', 'facts'), ('理由', 'reasons'), ('教示', 'instruction')]},
           'citation_grounded': len(draft['citations']), 'citation_total': len(draft['citations']),
           'gold_citations_recalled': recalled, 'gold_citations_missed': [x for x in expected if x not in recalled],
           'holding_match': draft['holding'] == gold['holding']},
    'detailed_report': report,
    'gold': gold,
}
for citation in draft['citations']:
    match = re.fullmatch(r'(statutes|precedents|interpretations|similar_cases)\[(\d+)\]', citation['source'])
    assert match and int(match[2]) < len(retrieval[match[1]]), citation
assert len(report['checks']) == 31
assert not all(c['pass'] for c in report['checks']), 'Do not conceal known source gaps or court disagreement'
output = ROOT / 'src' / 'data' / 'pipeline.json'
output.write_text(json.dumps(fixture, ensure_ascii=False, indent=2), encoding='utf-8')
print('Fixture generated:', report['score'])
print('Needs review:', [c['item'] for c in report['checks'] if not c['pass']])
