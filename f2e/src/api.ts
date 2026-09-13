// 後端 API 客戶端。契約：data/poc/03_介面規格.md（S0–S5 ＋ 附錄 A/B/C）。
// base URL 讀 VITE_API_BASE_URL（.env.example），預設 http://localhost:8000；路徑前綴 /api。

// 空字串＝同源（Docker 內由 nginx 把 /api 反向代理到後端）；未設定才退回本機 8000
export const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000').replace(/\/+$/, '')
export const POLL_INTERVAL_MS = 1500   // 附錄 A：輪詢 1500 ms（WebSocket 連上後降為 POLL_FALLBACK_MS 備援）
export const POLL_FALLBACK_MS = 10_000
export const POLL_TIMEOUT_MS = 300_000 // 附錄 A 建議 120 s，但 bedrock 模式全鏈約 2–2.5 分鐘（OCR 36 s＋Generate 60–80 s），放寬到 300 s（同 nginx proxy_read_timeout）
export const REQUEST_TIMEOUT_MS = 30_000 // 單次 fetch 逾時（後端掛住時不會永遠等）

export type StageStatus = 'pending' | 'running' | 'done' | 'error' | 'skipped'
export type CaseStatus = 'queued' | 'running' | 'done' | 'error'
export type StageKey = 'S1' | 'S2' | 'S2_5' | 'S3' | 'S4' | 'S5'

export interface S1 { case_id: string; petition_text: string; disposition_text: string; ocr_confidence_note: string }
export interface S2 {
  appellant: { name: string; dob?: string; address?: string }
  agency: string
  disposition: { date?: string; doc_no?: string; type?: string; legal_basis?: string[]; addressee?: string }
  served_date?: string
  petition_filed_date?: string
  case_type?: string
  facts_by_agency?: string
  appellant_claims: string[]
  issues: string[]
}
export interface ProcedureCheck { rule: string; pass: boolean; note?: string; served?: string | null; filed?: string | null; days?: number | null; needs_review?: boolean; category?: string; inputs?: Record<string, unknown> }
export interface S25 { admissible: boolean; checks: ProcedureCheck[]; defect_flags?: { flag: string; law: string; note: string }[]; needs_review?: string[] }
export interface S3 {
  // basis／note：歷史決定書法條索引補上的條文（同案型 N 篇中 M% 引用）
  statutes: { law: string; article: string; text: string; version_date?: string | null; basis?: string; note?: string }[]
  precedents: { id: string; topic?: string; excerpt: string; score?: number }[]
  interpretations: { id: string; excerpt: string }[]
  similar_cases: { id: string; result: string; why_similar: string; score?: number; holding?: string; case_type?: string; source?: string; decided?: string }[]
  // 同案型歷史決定書分布（26,607 篇統計；案由對不到索引時為 null）
  history?: { case_type: string; cases: number; outcome: Record<string, number> } | null
  note?: string
}
export interface Citation { text: string; source: string; section: 'facts' | 'reasons' | 'instruction'; index: number }
export interface S4 {
  header: { case_type?: string; appellant?: string; agency?: string; disposition_ref?: string }
  holding: string
  facts: string
  reasons: string[]
  instruction: string
  citations: Citation[]
  gaps: string[]
  provenance?: string
}
export interface CheckItem { group: string; item: string; pass: boolean; note?: string }
export interface S5Summary {
  sections_present: Record<string, boolean>
  citation_grounded: number
  citation_total: number
  gold_citations_recalled: string[]
  gold_citations_missed: string[]
  holding_match: boolean
}
export interface S5 { checks: CheckItem[]; score: Record<string, string>; summary: S5Summary }

export interface StageState<T> { status: StageStatus; data: T | null; error: string | null; elapsed_ms: number | null }
export interface CaseEnvelope {
  case_id: string
  status: CaseStatus
  current_stage: StageKey | null
  adapter_mode: string
  created_at: string
  updated_at: string
  stages: { S1: StageState<S1>; S2: StageState<S2>; S2_5: StageState<S25>; S3: StageState<S3>; S4: StageState<S4>; S5: StageState<S5> }
  // 個資前處理摘要（bedrock 模式；stub 為 null）：S1 後姓名→甲○○ 等代號，S4 還原；對照表只在後端記憶體
  pii?: { mode: string; replaced: Record<string, number>; codes: string[] } | null
  error: string | null
  // 持久層（DATABASE_URL 有設）：目前生效的承辦人草稿版本；null＝AI 原稿
  draft?: DraftMeta | null
}
export interface DraftMeta { version: number; edited_at: string | null; edited_by: string | null; note: string | null; is_current?: boolean }
export interface DraftDoc extends DraftMeta { case_id: string; content: S4 }
export type CaseSummary = Omit<CaseEnvelope, 'stages'> & { stages: Record<StageKey, Omit<StageState<unknown>, 'data'>> }
export interface ModelStage { configured: string; active: string }
export interface ModelConfig { default: string; fallback: string | null; kb_id: string; region: string; stages: Record<'ocr' | 'extract' | 'retrieval' | 'generate', ModelStage>; fallbacks_in_effect: Record<string, string> }
export interface Health { status: string; adapter_mode: string; auth_required?: boolean; db?: boolean; models?: ModelConfig }
export interface LoginResult { auth_required: boolean; token: string | null; expires_at?: number; username?: string }

// ---- 登入 token（後端 AUTH_USERNAME／AUTH_PASSWORD 有設才需要）----
const TOKEN_KEY = 'mjmr_token'
export const getToken = () => { try { return localStorage.getItem(TOKEN_KEY) } catch { return null } }
export const setToken = (t: string | null) => { try { t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY) } catch { /* 無 localStorage */ } }
export const onUnauthorized: { handler: (() => void) | null } = { handler: null }   // App 在 401 時切回登入頁

export class ApiError extends Error {
  status?: number
  constructor(message: string, status?: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  const headers = new Headers(init?.headers)
  const token = getToken()
  if (token && !headers.has('Authorization')) headers.set('Authorization', `Bearer ${token}`)
  try {
    res = await fetch(API_BASE + path, { ...init, headers, signal: init?.signal ?? AbortSignal.timeout(REQUEST_TIMEOUT_MS) })
  } catch (e) {
    if (e instanceof DOMException && e.name === 'TimeoutError') throw new ApiError('等候回應逾時，請稍後重試。')
    throw new ApiError('暫時無法連線，請確認網路連線或稍後重試。')
  }
  if (res.status === 401 && !path.startsWith('/api/login')) { setToken(null); onUnauthorized.handler?.() }
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch { /* 非 JSON 回應 */ }
    console.error('Request failed', res.status, detail)
    const message = res.status === 401 ? '登入已失效，請重新登入。'
      : res.status === 413 ? '文件過大，請縮小至 10 MB 以下再上傳。'
      : res.status === 422 ? '文件或日期格式不正確，請檢查後重試。'
      : res.status === 404 ? '找不到這份案件，請重新開始。'
      : '服務暫時無法完成要求，請稍後重試。'
    throw new ApiError(message, res.status)
  }
  return res.json() as Promise<T>
}

export const getHealth = () => request<Health>('/api/health')
export const login = (username: string, password: string) =>
  request<LoginResult>('/api/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username, password }) })

// Demo 文件：public/demo/ 的兩張模擬影像（01 訴願書／02 書面告誡渲染成 JPG，人名帳號皆虛構），一鍵載入方便測試
export const DEMO_FILES = [
  { url: `${import.meta.env.BASE_URL}demo/petition.jpg`, name: 'demo_訴願書.jpg' },
  { url: `${import.meta.env.BASE_URL}demo/disposition.jpg`, name: 'demo_書面告誡.jpg' },
] as const
export async function fetchDemoFiles(): Promise<File[]> {
  return Promise.all(DEMO_FILES.map(async d => {
    const r = await fetch(d.url)
    if (!r.ok) throw new ApiError('載入 Demo 文件失敗，請稍後重試。')
    return new File([await r.blob()], d.name, { type: 'image/jpeg' })
  }))
}

export function createCase(petition: File, disposition: File, serviceDate?: string) {
  const body = new FormData()
  body.append('petition_image', petition)
  body.append('disposition_image', disposition)
  if (serviceDate) body.append('service_date', serviceDate)   // 選填：承辦人填的送達日（西元 YYYY-MM-DD），後端覆蓋 S2.served_date
  return request<{ case_id: string }>('/api/cases', { method: 'POST', body })
}

export const getCase = (caseId: string) => request<CaseEnvelope>(`/api/cases/${encodeURIComponent(caseId)}`)
export const listCases = () => request<{ cases: CaseSummary[] }>('/api/cases')

// ---- 持久層（後端 DATABASE_URL 有設才可用；沒設回 501）：承辦人草稿版本、上傳影像回看 ----
const casePath = (caseId: string) => `/api/cases/${encodeURIComponent(caseId)}`
export const getCurrentDraft = (caseId: string) => request<DraftDoc>(`${casePath(caseId)}/drafts/current`)
export const listDrafts = (caseId: string) => request<{ case_id: string; drafts: DraftMeta[] }>(`${casePath(caseId)}/drafts`)
export const saveDraft = (caseId: string, content: S4, note?: string) =>
  request<{ case_id: string; version: number; edited_at: string }>(`${casePath(caseId)}/draft`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ content, note: note || null }) })
export const restoreDraft = (caseId: string, version: number) =>
  request<{ case_id: string; current_version: number }>(`${casePath(caseId)}/drafts/${version}/restore`, { method: 'POST' })
/** 回看已存的上傳影像 → object URL（需 Authorization header，所以不能直接 <img src>）；失敗回空字串 */
export async function fetchCaseFile(caseId: string, field: 'petition_image' | 'disposition_image'): Promise<string> {
  const token = getToken()
  try {
    const r = await fetch(`${API_BASE}${casePath(caseId)}/files/${field}`, { headers: token ? { Authorization: `Bearer ${token}` } : {}, signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS) })
    if (!r.ok) return ''
    return URL.createObjectURL(await r.blob())
  } catch { return '' }
}

export const sleep = (ms: number) => new Promise<void>(resolve => setTimeout(resolve, ms))

// ---- WebSocket 即時進度（後端 /api/cases/{id}/ws）----
// 訊息：{type:'envelope', envelope, final?} 階段變化｜{type:'progress', stage, message} 子步驟｜{type:'delta', stage, text} 生成串流｜{type:'ping'}
export type CaseEvent =
  | { type: 'envelope'; envelope: CaseEnvelope; final?: boolean }
  | { type: 'progress'; stage: StageKey; message: string }
  | { type: 'delta'; stage: StageKey; text: string }
  | { type: 'ping' }

export interface CaseSocket { close(): void; readonly connected: boolean }

export function openCaseSocket(caseId: string, onEvent: (e: CaseEvent) => void, onClose?: (clean: boolean) => void): CaseSocket {
  const base = (API_BASE || window.location.origin).replace(/^http/, 'ws')
  const token = getToken()
  const url = `${base}/api/cases/${encodeURIComponent(caseId)}/ws${token ? `?token=${encodeURIComponent(token)}` : ''}`
  let connected = false
  let ws: WebSocket | null = null
  try { ws = new WebSocket(url) } catch { onClose?.(false); return { close() {}, get connected() { return false } } }
  ws.onopen = () => { connected = true }
  ws.onmessage = ev => { try { onEvent(JSON.parse(ev.data) as CaseEvent) } catch (e) { console.warn('ws message parse failed', e) } }
  ws.onerror = () => { /* onclose 會接著觸發 */ }
  ws.onclose = ev => { const was = connected; connected = false; onClose?.(was && ev.code === 1000) }
  return { close() { try { ws?.close(1000) } catch { /* ignore */ } }, get connected() { return connected } }
}
