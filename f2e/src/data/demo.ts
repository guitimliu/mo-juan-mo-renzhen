import pipeline from './pipeline.json'
import type { CaseEnvelope, CheckItem, S1, S2, S25, S3, S4, S5 } from '../api'

// E：正本比對檢核是開發用檢核頁，demo 時隱藏（第 6 步）；後端仍會算 S5，設 true 就看得到
export const showDeveloperChecks = false
export const steps = [
  { title: '文件上傳', short: '上傳', icon: 'upload', description: '匯入案件文件，開始審查流程' },
  { title: 'OCR 辨識', short: 'OCR 對照', icon: 'scan', description: '對照原始文件與辨識文字' },
  { title: '程序檢核', short: '程序檢核', icon: 'shield', description: '確認案件程序與需人工複核的項目' },
  { title: '法源檢索', short: '法源檢索', icon: 'search', description: '檢視法條、判解、立法理由與相似訴願案件' },
  { title: '決定書草稿', short: '草稿生成', icon: 'edit', description: '逐段核對草稿內容，讓每一份引用都有依據' },
  { title: '正本比對檢核', short: '正本比對', icon: 'list', description: '對照團隊標準答案，檢查段落、引用與五個論理要點' },
].filter((_, index) => showDeveloperChecks || index < 5)

// 六階段資料；任一階段尚未完成時為 null／undefined，畫面顯示空白而不是假資料。
export interface StageData { s1?: S1 | null; s2?: S2 | null; procedure?: S25 | null; s3?: S3 | null; s4?: S4 | null; s5?: S5 | null }

// 接受附錄 A envelope（後端回傳／backend `python -m app.fixture` 產的 pipeline.json）。
// E 舊 fixture 形狀（s1/s2/procedure/s3/s4/s5/detailed_report）只保證不拋錯：舊 citations 沒有 section/index，段落引用 chip 會是空的。
export function stagesFrom(input: unknown): StageData {
  const any = input as Record<string, any> | null
  if (any?.stages) {
    const st = (any as CaseEnvelope).stages
    return { s1: st.S1?.data, s2: st.S2?.data, procedure: st.S2_5?.data, s3: st.S3?.data, s4: st.S4?.data, s5: st.S5?.data }
  }
  return { s1: any?.s1, s2: any?.s2, procedure: any?.procedure, s3: any?.s3, s4: any?.s4, s5: any?.s5 && any?.detailed_report ? { ...any.detailed_report, summary: any.s5 } : null }
}

const EMPTY_S2: S2 = { appellant: { name: '' }, agency: '', disposition: {}, appellant_claims: [], issues: [] }
const EMPTY_S3: S3 = { statutes: [], precedents: [], interpretations: [], similar_cases: [] }
const CN = '一二三四五六七八九十'

export function buildView(d: StageData) {
  const s1 = d.s1 ?? null
  const summary = d.s2 ?? EMPTY_S2
  const procedure: S25 = d.procedure ?? { admissible: false, checks: [] }
  const s3: S3 = { ...EMPTY_S3, ...(d.s3 ?? {}) }
  for (const k of ['statutes', 'precedents', 'interpretations', 'similar_cases'] as const) if (!Array.isArray(s3[k])) (s3 as any)[k] = []
  const s4 = d.s4 ?? null
  const report = { checks: (Array.isArray(d.s5?.checks) ? d.s5!.checks : []) as CheckItem[], score: (d.s5?.score ?? {}) as Record<string, string> }
  const validation = d.s5?.summary ?? { sections_present: {}, citation_grounded: 0, citation_total: 0, gold_citations_recalled: [], gold_citations_missed: [], holding_match: false }
  const totals = { passed: report.checks.filter(c => c.pass).length, total: report.checks.length, failed: report.checks.filter(c => !c.pass).length }
  const sources = [
    ...s3.statutes.map((s, i) => ({ id: `statutes[${i}]`, type: '法條', title: s.law, subtitle: `第 ${s.article} 條 · 版本 ${s.version_date ?? '—'}`, content: s.text, tag: '法條' })),
    ...s3.precedents.map((s, i) => ({ id: `precedents[${i}]`, type: '判解', title: s.id, subtitle: `${s.topic ?? ''} · 相關度 ${s.score ?? '—'}`, content: s.excerpt, tag: '判解' })),
    ...s3.interpretations.map((s, i) => ({ id: `interpretations[${i}]`, type: '立法理由', title: s.id, subtitle: '立法理由', content: s.excerpt, tag: '立法理由' })),
    ...s3.similar_cases.map((s, i) => ({ id: `similar_cases[${i}]`, type: '相似案', title: `${s.id}${s.case_type ? ' ' + s.case_type : ''}`, subtitle: `${s.result} · 相關度 ${s.score ?? '—'}`, content: s.why_similar + (s.holding ? `　主文：${s.holding}` : ''), tag: s.result })),
  ]
  // 附錄 B：citations 帶 (section, index)，依此掛到段落；每筆 citation 一顆 chip（同 text+source 才合併），數字與 S5 的 citation_total 對得上
  const cites = (section: string, index: number) => {
    const seen = new Set<string>()
    return (Array.isArray(s4?.citations) ? s4!.citations : []).filter(c => c && c.section === section && c.index === index && c.source)
      .filter(c => { const k = `${c.text}|${c.source}`; if (seen.has(k)) return false; seen.add(k); return true })
      .map(c => ({ id: c.source, label: c.text || c.source }))
  }
  const reasons = Array.isArray(s4?.reasons) ? s4!.reasons : []
  const draft = s4 ? [
    { title: '主文', text: s4.holding, citations: [] as { id: string; label: string }[] },
    { title: '事實', text: s4.facts, citations: cites('facts', 0) },
    ...reasons.map((text, i) => ({ title: `理由（${CN[i] ?? i + 1}）`, text, citations: cites('reasons', i) })),
    { title: '教示', text: s4.instruction, citations: cites('instruction', 0) },
  ] : []
  const find = (prefix: string) => report.checks.find(c => c.item.startsWith(prefix))
  const sections = Object.values(validation.sections_present)
  const checks = !report.checks.length ? [] : [
    { title: '必要段落齊全', detail: '主文、事實、理由、教示', status: sections.length > 0 && sections.every(Boolean) },
    { title: '引用判決可追溯', detail: find('引用判決皆在檢索結果內')?.note || find('引用判決皆在檢索結果內')?.item || '', status: find('引用判決皆在檢索結果內')?.pass ?? false },
    { title: '主文與正本一致', detail: s4?.holding ?? '', status: validation.holding_match },
    { title: '教示法院一致', detail: find('教示指向')?.item ?? '', status: find('教示指向')?.pass ?? false },
  ]
  return {
    summary, procedure, report, validation, sources, draft, checks, totals,
    header: s4?.header ?? {},
    gaps: Array.isArray(s4?.gaps) ? s4!.gaps : [],
    provenance: s4?.provenance ?? '',
    ocrText: s1?.petition_text ?? '',
    dispositionText: s1?.disposition_text ?? '',
    ocrNote: s1?.ocr_confidence_note ?? '',
    failedItems: report.checks.filter(c => !c.pass).map(c => c.item),
  }
}

export type View = ReturnType<typeof buildView>
export const empty = (): View => buildView({})
// 保底 fixture：後端 stub pipeline 產的 envelope（backend: python -m app.fixture）
export const fixtureEnvelope = pipeline as unknown as CaseEnvelope
export const fixture: View = buildView(stagesFrom(fixtureEnvelope))
