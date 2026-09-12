// 後端 API 客戶端。契約：data/poc/03_介面規格.md（S0–S5 ＋ 附錄 A/B/C）。
// base URL 讀 VITE_API_BASE_URL（.env.example），預設 http://localhost:8000；路徑前綴 /api。

// 空字串＝同源（Docker 內由 nginx 把 /api 反向代理到後端）；未設定才退回本機 8000
export const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000').replace(/\/+$/, '')
export const POLL_INTERVAL_MS = 1500   // 附錄 A：輪詢 1500 ms
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
  statutes: { law: string; article: string; text: string; version_date?: string | null }[]
  precedents: { id: string; topic?: string; excerpt: string; score?: number }[]
  interpretations: { id: string; excerpt: string }[]
  similar_cases: { id: string; result: string; why_similar: string; score?: number; holding?: string; case_type?: string }[]
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
  error: string | null
}
export interface ModelStage { configured: string; active: string }
export interface ModelConfig { default: string; fallback: string | null; kb_id: string; region: string; stages: Record<'ocr' | 'extract' | 'retrieval' | 'generate', ModelStage>; fallbacks_in_effect: Record<string, string> }
export interface Health { status: string; adapter_mode: string; auth_required?: boolean; models?: ModelConfig }
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
    if (e instanceof DOMException && e.name === 'TimeoutError') throw new ApiError(`後端 ${API_BASE} 逾時未回應（${REQUEST_TIMEOUT_MS / 1000} 秒）`)
    throw new ApiError(`無法連線後端 ${API_BASE}，請確認 uvicorn 已啟動`)
  }
  if (res.status === 401 && !path.startsWith('/api/login')) { setToken(null); onUnauthorized.handler?.() }
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch { /* 非 JSON 回應 */ }
    throw new ApiError(`後端回應錯誤：${detail}`, res.status)
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
    if (!r.ok) throw new ApiError(`載入 demo 影像失敗：${d.url}`)
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

export const sleep = (ms: number) => new Promise<void>(resolve => setTimeout(resolve, ms))
