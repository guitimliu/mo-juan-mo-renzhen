import pipeline from './pipeline.json'

export const showDeveloperChecks = false
export const steps = [
  { title: '文件上傳', short: '上傳', icon: 'upload', description: '匯入案件文件，開始審查流程' },
  { title: 'OCR 辨識', short: 'OCR 對照', icon: 'scan', description: '對照原始文件與辨識文字' },
  { title: '程序檢核', short: '程序檢核', icon: 'shield', description: '確認案件程序與需人工複核的項目' },
  { title: '法源檢索', short: '法源檢索', icon: 'search', description: '檢視法條、判解、立法理由與相似訴願案件' },
  { title: '決定書草稿', short: '草稿生成', icon: 'edit', description: '逐段核對草稿內容，讓每一份引用都有依據' },
  { title: '正本比對檢核', short: '正本比對', icon: 'list', description: '對照團隊標準答案，檢查段落、引用與五個論理要點' },
].filter((_, index) => showDeveloperChecks || index < 5)
export const summary = pipeline.s2
export const procedure = pipeline.procedure
export const report = pipeline.detailed_report
export const validation = pipeline.s5
export const gaps = pipeline.s4.gaps.map(gap => gap.startsWith('教示法院待團隊確認：')
  ? '救濟教示待核對：決定書與引用資料記載的法院不一致，請承辦人確認。'
  : gap.replace('本次模擬檢索', '本次檢索'))
export const ocrText = pipeline.s1.petition_text
export const dispositionText = pipeline.s1.disposition_text
export const ocrNote = pipeline.s1.ocr_confidence_note
export const totals = {
  passed: report.checks.filter(c => c.pass).length,
  total: report.checks.length,
  failed: report.checks.filter(c => !c.pass).length,
}
export const sources = [
  ...pipeline.s3.statutes.map((s, i) => ({ id: `statutes[${i}]`, type: '法條', title: s.law, subtitle: `第 ${s.article} 條 · 版本 ${s.version_date}`, content: s.text, tag: '法條' })),
  ...pipeline.s3.precedents.map((s, i) => ({ id: `precedents[${i}]`, type: '判解', title: s.id, subtitle: `${s.topic} · 相關度 ${s.score}`, content: s.excerpt, tag: '判解' })),
  ...pipeline.s3.interpretations.map((s, i) => ({ id: `interpretations[${i}]`, type: '立法理由', title: s.id, subtitle: '取自提供的原決定書引文', content: s.excerpt, tag: '原決定書引文' })),
  ...pipeline.s3.similar_cases.map((s, i) => ({ id: `similar_cases[${i}]`, type: '相似案', title: `${s.id} 違反洗錢防制法事件`, subtitle: `${s.result} · 相關度 ${s.score}`, content: s.why_similar, tag: s.result })),
]
// S4 has global citations, not per-paragraph associations. This is demo-only mapping.
const reasonSources = [['statutes[0]'], ['statutes[0]'], ['statutes[0]', 'interpretations[0]', 'interpretations[1]'], ['statutes[1]']]
export const draft = [
  { title: '主文', text: pipeline.s4.holding, citations: ['statutes[1]'] },
  { title: '事實', text: pipeline.s4.facts, citations: [] as string[] },
  ...pipeline.s4.reasons.map((text, i) => ({ title: `理由（${['一', '二', '三', '四'][i]}）`, text, citations: reasonSources[i] || [] })),
  { title: '教示', text: pipeline.s4.instruction, citations: [] as string[] },
]
export const checks = [
  { title: '必要段落齊全', detail: '主文、事實、理由、教示', status: Object.values(validation.sections_present).every(Boolean) },
  { title: '引用判決可追溯', detail: '正本的 3 篇判決未在模擬檢索結果內', status: false },
  { title: '主文與正本一致', detail: pipeline.s4.holding, status: validation.holding_match },
  { title: '教示法院一致', detail: '正本與模板不一致，待團隊確認', status: false },
]
