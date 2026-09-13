<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, shallowRef, watch } from 'vue'
import Icon from './components/AppIcon.vue'
import DocumentZoom from './components/DocumentZoom.vue'
import ProcessingStatus from './components/ProcessingStatus.vue'
import LoginPanel from './components/LoginPanel.vue'
import { parseRocDate } from './rocDate'
import { showDeveloperChecks, steps, empty, buildView, stagesFrom } from './data/demo'
import { ApiError, createCase, getCase, getHealth, sleep, fetchDemoFiles, getToken, setToken, onUnauthorized, openCaseSocket, listCases, getCurrentDraft, listDrafts, saveDraft, restoreDraft, fetchCaseFile, POLL_INTERVAL_MS, POLL_FALLBACK_MS, POLL_TIMEOUT_MS, type CaseEnvelope, type CaseEvent, type CaseSocket, type CaseSummary, type DraftMeta, type S4 } from './api'

// 資料流：view 由 envelope（後端 API）或 fixture（保底）建出；template 透過下列 computed 讀取。
const view = ref(empty())
const dataSource = ref<'fixture' | 'api'>('fixture')
const caseId = ref('')
const adapterMode = ref<string | null>(null)
const authRequired = ref(false)
const loggedIn = ref(!!getToken())
const currentUser = ref('')
const showLogin = computed(() => authRequired.value && !loggedIn.value)
const slidesUrl = `${import.meta.env.BASE_URL}slides/`   // Slidev 簡報：Docker 內由 nginx 代理到 slides 容器；本機 dev 需另起 slides（npm run dev）
const processingError = ref('')
const pii = ref<CaseEnvelope['pii']>(null)
const liveNote = ref('')            // WebSocket progress：目前子步驟說明
const liveText = ref('')            // WebSocket delta：S4 生成中的草稿串流
let socket: CaseSocket | null = null

// ---- 持久層：我的案件列表、承辦人草稿版本（後端 DATABASE_URL 有設才會有儲存鍵；列表不需 DB）----
const dbEnabled = ref(false)
const caseList = ref<CaseSummary[]>([])
const caseListLoading = ref(false)
const lastEnvelope = shallowRef<CaseEnvelope | null>(null)   // 最近一次 envelope：切換草稿版本／歷史統計列用
const draftVersion = ref(0)                    // 0＝AI 原稿
const draftVersions = ref<DraftMeta[]>([])
const editing = ref(false)
const saving = ref(false)
const editNote = ref('')
const edited = ref<{ holding: string; facts: string; reasons: string[]; instruction: string }>({ holding: '', facts: '', reasons: [], instruction: '' })
const draftLabel = computed(() => draftVersion.value ? `承辦人版 v${draftVersion.value}` : 'AI 原稿')
const history = computed(() => lastEnvelope.value?.stages.S3?.data?.history ?? null)
const historyLabel = computed(() => {
  const h = history.value
  if (!h || !h.cases) return ''
  const pct = (k: string) => `${k} ${Math.round(100 * (h.outcome[k] ?? 0) / h.cases)}%`
  return `歷史同案型「${h.case_type}」${h.cases.toLocaleString()} 篇：${['駁回', '撤銷', '不受理'].map(pct).join('、')}（新北市法制局 2004–2026 訴願決定書統計）`
})
async function refreshCaseList() {
  if (!loggedIn.value) return
  caseListLoading.value = true
  try { caseList.value = (await listCases()).cases } catch { /* 列表失敗不影響工作台 */ } finally { caseListLoading.value = false }
}
function caseListTitle(c: CaseSummary) {
  return { queued: '排隊中', running: '分析中', done: '草稿待審閱', error: '分析失敗' }[c.status] || c.status
}
// 把目前生效的草稿版本套進 view（content 為 S4 形狀；null＝AI 原稿）
function applyDraft(content: S4 | null, version: number) {
  if (!lastEnvelope.value) return
  const stages = stagesFrom(lastEnvelope.value)
  view.value = buildView(content ? { ...stages, s4: content } : stages)
  draftVersion.value = version
}
async function loadDraftState(id: string) {
  draftVersion.value = 0; draftVersions.value = []
  if (!dbEnabled.value) return
  try {
    const cur = await getCurrentDraft(id)
    if (cur.version > 0) applyDraft(cur.content, cur.version)
    draftVersions.value = (await listDrafts(id)).drafts
  } catch { /* 501／404：沒有草稿功能或案件 */ }
}
// 從「我的案件」列表開啟一個已存在的案件（重啟後也能回來）
async function openCase(id: string) {
  if (running.value || exporting.value || demoLoading.value || id === caseId.value) return
  try {
    const env = await getCase(id)
    reset()
    lastEnvelope.value = env
    caseId.value = id
    dataSource.value = 'api'
    adapterMode.value = env.adapter_mode || adapterMode.value
    pii.value = env.pii ?? null
    view.value = buildView(stagesFrom(env))
    ready.value = env.status === 'done'
    processingVisible.value = env.status !== 'done'
    processingComplete.value = env.status === 'done'
    processingError.value = env.status === 'error' ? (env.error || '分析未完成') : ''
    progress.value = env.status === 'done' ? 6 : progressFrom(env)
    await loadDraftState(id)
    if (dbEnabled.value) {   // 上傳影像回看（需 token，走 fetch → object URL）
      const [p, d] = await Promise.all([fetchCaseFile(id, 'petition_image'), fetchCaseFile(id, 'disposition_image')])
      previews.value = [p, d]
    }
    active.value = ready.value ? 4 : 0
    notify(`已載入案件 ${id}（${draftLabel.value}）`)
  } catch (error) {
    notify(error instanceof ApiError ? error.message : '載入案件失敗')
  }
}
function startEdit() {
  const s4 = currentS4()
  if (!s4) return
  edited.value = { holding: s4.holding, facts: s4.facts, reasons: [...s4.reasons], instruction: s4.instruction }
  editNote.value = ''
  editing.value = true
}
function currentS4(): S4 | null {
  const parts = draft.value
  if (!parts.length || !lastEnvelope.value) return null
  const base = lastEnvelope.value.stages.S4.data
  if (!base) return null
  const reasons = parts.filter(p => p.title.startsWith('理由')).map(p => p.text)
  return { ...base, holding: parts.find(p => p.title === '主文')?.text ?? base.holding, facts: parts.find(p => p.title === '事實')?.text ?? base.facts, reasons: reasons.length ? reasons : base.reasons, instruction: parts.find(p => p.title === '教示')?.text ?? base.instruction }
}
async function saveEdit() {
  const base = lastEnvelope.value?.stages.S4.data
  if (!base || saving.value) return
  saving.value = true
  try {
    const content: S4 = { ...base, ...edited.value, reasons: edited.value.reasons.map(r => r.trim()).filter(Boolean) }
    const r = await saveDraft(caseId.value, content, editNote.value.trim() || undefined)
    applyDraft(content, r.version)
    draftVersions.value = (await listDrafts(caseId.value)).drafts
    editing.value = false
    notify(`已儲存承辦人版 v${r.version}`)
  } catch (error) {
    notify(error instanceof ApiError ? error.message : '儲存失敗，請稍後重試')
  } finally { saving.value = false }
}
async function switchDraft(version: number) {
  if (saving.value || version === draftVersion.value) return
  try {
    await restoreDraft(caseId.value, version)
    if (version === 0) applyDraft(null, 0)
    else { const d = await getCurrentDraft(caseId.value); applyDraft(d.content, d.version) }
    draftVersions.value = (await listDrafts(caseId.value)).drafts
    editing.value = false
    notify(version === 0 ? '已還原 AI 原稿' : `已切換為承辦人版 v${version}`)
  } catch (error) {
    notify(error instanceof ApiError ? error.message : '切換版本失敗')
  }
}
const piiLabel = computed(() => pii.value ? `已去識別化（${pii.value.mode === 'pseudonym' ? '取代法' : pii.value.mode}）：${Object.entries(pii.value.replaced || {}).filter(([, n]) => n).map(([k, n]) => `${({ name: '姓名', id: '身分證', phone: '電話', address: '地址', dob: '生日' } as Record<string, string>)[k] || k}×${n}`).join('、')}` : '')
const sources = computed(() => view.value.sources)
const draft = computed(() => view.value.draft)
const checks = computed(() => view.value.checks)
const summary = computed(() => view.value.summary)
const procedure = computed(() => view.value.procedure)
const report = computed(() => view.value.report)
const validation = computed(() => view.value.validation)
const gaps = computed(() => view.value.gaps)
const totals = computed(() => view.value.totals)
const header = computed(() => view.value.header)
const ocrText = computed(() => view.value.ocrText)
const dispositionText = computed(() => view.value.dispositionText)
const caseLabel = computed(() => dataSource.value === 'api' ? caseId.value : '新建案件')
const caseTitle = computed(() => summary.value.case_type || '待匯入案件文件')
const reportNote = computed(() => view.value.failedItems.length ? `請確認以下未通過項目：${view.value.failedItems.join('；')}。` : '請逐項核對草稿內容與引用依據。')

const active = ref(0)
const topbar = ref<HTMLElement | null>(null)
const topbarHeight = ref(66)
const fontSizes = [{ label: '標準', value: 14 }, { label: '大', value: 16 }, { label: '特大', value: 18 }]
const fontSize = ref(14)
try {
  const saved = Number(localStorage.getItem('workspace-font-size'))
  if (fontSizes.some(size => size.value === saved)) fontSize.value = saved
} catch { /* Storage is optional. */ }
watch(fontSize, value => {
  document.documentElement.style.fontSize = value + 'px'
  try { localStorage.setItem('workspace-font-size', String(value)) } catch { /* Keep the session preference. */ }
}, { immediate: true })
let topbarObserver: ResizeObserver | undefined
watch(topbar, element => {
  topbarObserver?.disconnect()
  if (!element) return
  const measure = () => { topbarHeight.value = element.getBoundingClientRect().height }
  measure()
  topbarObserver = new ResizeObserver(measure)
  topbarObserver.observe(element)
}, { flush: 'post' })
onUnmounted(() => topbarObserver?.disconnect())
function goToWorkspace() {
  active.value = 0
  window.scrollTo({ top: 0, behavior: 'instant' })
}
const pipelineNav = ref<HTMLElement | null>(null)
const selectedSource = ref('statutes[0]')
const filter = ref('全部')
const NO_SOURCE = { id: '', type: '', title: '尚無檢索來源', subtitle: '', content: '', tag: '' }
const source = computed(() => sources.value.find(s => s.id === selectedSource.value) || sources.value[0] || NO_SOURCE)
const filteredSources = computed(() => sources.value.filter(s => filter.value === '全部' || s.type === filter.value))
const ready = ref(false)

const running = ref(false)
const progress = ref(0)
watch([active, progress, running], async () => {
  await nextTick()
  const nav = pipelineNav.value
  const current = nav?.querySelector<HTMLElement>('[aria-current="step"]')
  if (!nav || !current || nav.scrollWidth <= nav.clientWidth) return
  const left = current.getBoundingClientRect().left - nav.getBoundingClientRect().left + nav.scrollLeft
  nav.scrollTo({ left: left - (nav.clientWidth - current.offsetWidth) / 2, behavior: 'instant' })
})
const processingVisible = ref(false)
const processingComplete = ref(false)
const elapsed = ref(0)
const toast = ref('')
const reviewed = ref(false)
const files = ref<(File | null)[]>([null, null])
const previews = ref<string[]>(['', ''])

const serviceDate = ref('')
const serviceDateIso = computed(() => parseRocDate(serviceDate.value))
const serviceDateError = computed(() => serviceDateIso.value === null ? '請輸入有效的民國年月日，例如 113/01/31。' : '')
const documentIndex = ref(0)
const expanded = ref('理由（三）')
const sourceDetail = ref<HTMLElement | null>(null)
const sectionTitle = ref<HTMLElement | null>(null)
const fileErrors = ref(['', ''])
const canAnalyze = computed(() => files.value.every(Boolean))
const uploadHint = computed(() => canAnalyze.value ? '文件已備妥，可以開始分析。' : `還需要選擇${files.value.map((file, i) => file ? '' : ['訴願書', '原處分書'][i]).filter(Boolean).join('與')}。`)
const confirmDialog = ref<HTMLDialogElement | null>(null)
const cancelButton = ref<HTMLButtonElement | null>(null)
const pendingAction = ref<'new' | 'demo' | 'demo-run'>('new')
const demoLoading = ref(false)
function warnBeforeLeaving(event: BeforeUnloadEvent) {
  if (!files.value.some(Boolean) && !serviceDate.value && !reviewed.value && !running.value && !exporting.value) return
  event.preventDefault()
  event.returnValue = ''
}
onMounted(() => window.addEventListener('beforeunload', warnBeforeLeaving))
let actionTrigger: HTMLElement | null = null
const guidance = [
  '準備訴願書與原處分書各一份圖片，再開始分析。',
  '切換兩份文件，核對姓名、日期與主張；確認辨識結果是否正確。',
  '優先查看需人工確認的項目，核對程序與送達資訊。',
  '依類型查看來源，確認條文與案例是否適用。',
  '逐段核對事實與理由，點選引用查看依據，完成後可匯出草稿。',
  '檢視差異與缺漏，確認後再下載示範草稿。',
]
watch(active, async () => {
  await nextTick()
  sectionTitle.value?.focus({ preventScroll: true })
  window.scrollTo({ top: 0, behavior: 'instant' })
})
function requestCase(action: 'new' | 'demo' | 'demo-run' = 'new') {
  if (running.value || exporting.value || demoLoading.value) return
  pendingAction.value = action
  if (files.value.some(Boolean) || serviceDate.value || reviewed.value) {
    actionTrigger = document.activeElement instanceof HTMLElement ? document.activeElement : null
    confirmDialog.value?.showModal()
    cancelButton.value?.focus()
  } else {
    executeCaseAction()
  }
}
function confirmCase() {
  confirmDialog.value?.close()
  executeCaseAction()
}
function executeCaseAction() {
  if (pendingAction.value === 'new') reset()
  else void loadDemoFiles(pendingAction.value === 'demo-run')
}
async function loadDemoFiles(andRun: boolean) {
  if (running.value || exporting.value || demoLoading.value) return
  demoLoading.value = true
  try {
    const [petition, disposition] = await fetchDemoFiles()
    if (!petition || !disposition) throw new Error('缺少 Demo 文件')
    reset()
    files.value = [petition, disposition]
    previews.value = [URL.createObjectURL(petition), URL.createObjectURL(disposition)]
    notify('已載入 Demo 文件，可以開始分析')
    if (andRun) await runDemo()
  } catch (error) {
    notify(error instanceof Error ? error.message : '載入 Demo 文件失敗，請重試')
  } finally {
    demoLoading.value = false
  }
}
function restoreActionFocus() {
  actionTrigger?.focus()
}
async function showSource(id: string) {
  selectedSource.value = id
  await nextTick()
  sourceDetail.value?.focus({ preventScroll: true })
  sourceDetail.value?.scrollIntoView({ block: 'nearest', behavior: 'instant' })
}
let timer: ReturnType<typeof setInterval> | undefined
let toastTimer: ReturnType<typeof setTimeout> | undefined
let run = 0   // 每次開始分析 +1，讓被停止的輪詢迴圈不再寫回狀態
const fileNames = computed(() => files.value.map(f => f?.name || '尚未選擇文件'))

function notify(message: string) {
  toast.value = message
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => toast.value = '', 4000)
}
function reset() {
  clearInterval(timer)
  run++
  running.value = false
  processingVisible.value = false
  processingComplete.value = false
  processingError.value = ''
  progress.value = 0
  elapsed.value = 0
  ready.value = false

  reviewed.value = false
  active.value = 0
  serviceDate.value = ''
  files.value = [null, null]
  previews.value.forEach(url => url && URL.revokeObjectURL(url))
  previews.value = ['', '']
  view.value = empty()
  dataSource.value = 'fixture'
  caseId.value = ''
  pii.value = null
  fileErrors.value = ['', '']
  documentIndex.value = 0
  filter.value = '全部'
  expanded.value = '理由（三）'
  selectedSource.value = 'statutes[0]'
  toast.value = ''
  clearTimeout(toastTimer)
  lastEnvelope.value = null
  draftVersion.value = 0
  draftVersions.value = []
  editing.value = false
}
function selectFile(event: Event, index: number) {
  if (running.value || exporting.value || demoLoading.value) return
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  input.value = ''
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
    fileErrors.value[index] = '不支援此格式，請改選 JPG、PNG 或 WebP 圖片。'
    return
  }
  if (!file.size || file.size > 10 * 1024 * 1024) {
    fileErrors.value[index] = !file.size ? '檔案是空的，請重新選擇圖片。' : '圖片超過 10 MB，請縮小圖片後重新選擇。'
    return
  }
  removeFile(index)
  files.value[index] = file
  previews.value[index] = URL.createObjectURL(file)
}
function removeFile(index: number) {
  if (running.value || exporting.value) return
  if (previews.value[index]) URL.revokeObjectURL(previews.value[index]!)
  files.value[index] = null
  previews.value[index] = ''
  fileErrors.value[index] = ''
  view.value = empty()
  caseId.value = ''

  ready.value = false
  reviewed.value = false
  processingVisible.value = false
  processingComplete.value = false
  processingError.value = ''
}
function stopDemo() {
  clearInterval(timer)
  socket?.close(); socket = null
  run++
  running.value = false
  notify('已停止更新進度，案件仍會繼續處理')
}
// 各區塊只要該階段資料已到就可點進去（區塊隨階段逐一出現）
function stepAvailable(index: number) {
  if (index === 0 || ready.value) return true
  const v = view.value
  return [false, !!v.ocrText, v.procedure.checks.length > 0, v.sources.length > 0, v.draft.length > 0, v.report.checks.length > 0][index] ?? false
}
function stepStatus(index: number) {
  if (running.value) return index < progress.value ? '已完成' : index === progress.value ? '處理中' : '等待中'
  if (processingVisible.value && !processingComplete.value && !ready.value) return index < progress.value ? '已完成' : index === progress.value ? (processingError.value ? '失敗' : '已停止') : '等待中'
  if (!ready.value) return index === 0 ? '等待文件' : '等待中'
  return active.value === index ? '目前檢視' : index === 0 ? '文件已備妥' : '可檢視・待核對'
}
// envelope → 前端進度：0 上傳（POST 成功即完成）、1 OCR＝S1+S2、2 程序＝S2_5、3 檢索＝S3、4 草稿＝S4、5 檢核＝S5（showDeveloperChecks=false 時第 6 步不顯示，但仍等它完成）
function progressFrom(env: CaseEnvelope) {
  const done = (k: keyof CaseEnvelope['stages']) => env.stages[k]?.status === 'done'
  if (!(done('S1') && done('S2'))) return 1
  if (!done('S2_5')) return 2
  if (!done('S3')) return 3
  if (!done('S4')) return 4
  if (!done('S5')) return 5
  return 6
}
function failRun(message: string) {
  clearInterval(timer)
  running.value = false
  processingComplete.value = false
  processingError.value = message
  notify(message)
}
async function runDemo() {
  if (running.value) return
  if (serviceDateError.value) {
    notify(serviceDateError.value)
    document.getElementById('service-date')?.focus()
    return
  }
  const [petition, disposition] = files.value
  if (!petition || !disposition) return notify('請先選擇訴願書與原處分書兩份圖片')
  const myRun = ++run

  running.value = true
  ready.value = false

  reviewed.value = false
  progress.value = 0
  elapsed.value = 0
  active.value = 0
  processingVisible.value = true
  processingComplete.value = false
  processingError.value = ''
  toast.value = ''
  view.value = empty()
  dataSource.value = 'api'
  liveNote.value = ''
  liveText.value = ''
  const startedAt = Date.now()
  timer = setInterval(() => { elapsed.value = Math.floor((Date.now() - startedAt) / 1000) }, 250)
  // 套用一次 envelope（WebSocket 與輪詢共用）；回傳 true 表示已結束
  const applyEnvelope = (env: CaseEnvelope, case_id: string): boolean => {
    lastEnvelope.value = env
    view.value = buildView(stagesFrom(env))
    adapterMode.value = env.adapter_mode || adapterMode.value
    pii.value = env.pii ?? null
    const next = progressFrom(env)
    if (next !== progress.value) { progress.value = next; liveNote.value = ''; if (next > 4) liveText.value = '' }
    if (env.status === 'done') {
      clearInterval(timer)
      running.value = false
      ready.value = true
      processingComplete.value = true
      liveNote.value = ''
      notify(`案件 ${case_id} 已完成，可以開始核對`)
      void refreshCaseList(); void loadDraftState(case_id)
      return true
    }
    if (env.status === 'error') { console.error('Case processing failed', env.error); failRun('分析未完成，文件已保留，請重新嘗試。'); return true }
    return false
  }
  try {
    await refreshHealth()
    if (myRun !== run) return
    const { case_id } = await createCase(petition, disposition, serviceDateIso.value || undefined)
    if (myRun !== run) return
    caseId.value = case_id
    progress.value = 1
    void refreshCaseList()
    // WebSocket 即時進度：階段變化立即到、子步驟說明、生成草稿逐字串流；連不上就退回 1.5 s 輪詢
    let finished = false
    socket?.close()
    socket = openCaseSocket(case_id, (e: CaseEvent) => {
      if (myRun !== run || finished) return
      if (e.type === 'envelope') finished = applyEnvelope(e.envelope, case_id)
      else if (e.type === 'progress') liveNote.value = e.message
      else if (e.type === 'delta' && e.stage === 'S4') liveText.value += e.text
    }, () => { if (myRun === run && !finished) liveNote.value = liveNote.value || '即時連線中斷，改用輪詢更新' })
    while (myRun === run && !finished) {
      await sleep(socket?.connected ? POLL_FALLBACK_MS : POLL_INTERVAL_MS)
      if (myRun !== run || finished) return
      const env = await getCase(case_id)
      if (myRun !== run || finished) return
      finished = applyEnvelope(env, case_id)
      if (!finished && Date.now() - startedAt > POLL_TIMEOUT_MS) return failRun(`處理時間超過預期（${POLL_TIMEOUT_MS / 1000} 秒），請重試`)
    }
  } catch (error) {
    if (myRun !== run) return
    failRun(error instanceof ApiError ? error.message : '分析未完成，請稍後重試。')
  } finally {
    if (myRun === run) { socket?.close(); socket = null }
  }
}
async function refreshHealth() {
  try {
    const h = await getHealth()
    adapterMode.value = h.adapter_mode
    authRequired.value = !!h.auth_required
    dbEnabled.value = !!h.db
    if (!authRequired.value) loggedIn.value = true       // 後端沒開驗證：直接進工作台
    void refreshCaseList()
  } catch {
    adapterMode.value = null
  }
}
function onLoggedIn(username: string) {
  loggedIn.value = true
  currentUser.value = username
  refreshHealth()
}
function logout() {
  setToken(null)
  loggedIn.value = false
  currentUser.value = ''
  if (running.value) stopDemo()
}
onUnauthorized.handler = () => { loggedIn.value = false; notify('登入已失效，請重新登入') }
const exporting = ref(false)
async function downloadDraft(format: 'pdf' | 'docx' = 'pdf') {
  if (exporting.value || running.value || !ready.value) return
  exporting.value = true
  try {
    const { exportDraft } = await import('./exportDraft')
    await exportDraft(format, draft.value, { caseLabel: caseLabel.value, appellant: header.value.appellant || summary.value.appellant.name || '', agency: header.value.agency || summary.value.agency || '', caseType: header.value.case_type || summary.value.case_type || '' })
    notify(`已匯出 ${format === 'pdf' ? 'PDF' : 'Word'} 草稿`)
  } catch (error) {
    console.error('Draft export failed', error)
    notify('匯出失敗，請稍後重試')
  } finally {
    exporting.value = false
  }
}
onMounted(refreshHealth)
onUnmounted(() => { window.removeEventListener('beforeunload', warnBeforeLeaving); clearInterval(timer); clearTimeout(toastTimer); socket?.close(); previews.value.forEach(url => url && URL.revokeObjectURL(url)) })

</script>

<template>
  <LoginPanel v-if="showLogin" @done="onLoggedIn" />
  <div v-else class="workspace" :style="{ '--topbar-height': topbarHeight + 'px' }">
    <aside class="sidebar">
      <a class="brand" href="#" @click.prevent="active = 0"><span class="brand-symbol"><Icon name="scales" :size="25" /></span><span>訴願審查助手<small>智慧案件審查工作台</small></span></a>
      <div class="workspace-label">法制局工作空間</div>
      <button class="nav-main" @click="active = ready ? 1 : 0"><Icon name="grid" />案件工作台<span class="nav-dot"></span></button>
      <a class="nav-main nav-link" :href="slidesUrl" target="_blank" rel="noopener" title="開新分頁檢視專案簡報"><Icon name="book" />專案簡報<Icon name="arrow" :size="14" /></a>
      <div class="side-divider"></div>
      <div class="side-heading case-list-heading">案件列表 <button class="new-case" title="新建案件" aria-label="新建案件" :disabled="running || exporting || demoLoading" @click="requestCase('new')"><Icon name="plus" :size="18" /></button></div>
      <button v-if="!caseList.some(c => c.case_id === caseId)" class="case-nav selected" @click="active = ready ? 1 : 0"><Icon name="file" /><span><b>{{ caseLabel }}</b><small>{{ caseTitle }}</small></span></button>
      <div class="case-list" aria-label="我的案件"><button v-for="c in caseList" :key="c.case_id" class="case-nav case-item" :class="{ selected: c.case_id === caseId }" :disabled="running || exporting || demoLoading" :title="`${c.case_id}｜${c.updated_at}`" @click="openCase(c.case_id)"><Icon name="file" :size="16" /><span><b>{{ c.case_id }}<em v-if="c.draft"> v{{ c.draft.version }}</em></b><small>{{ caseListTitle(c) }} · {{ c.updated_at.slice(5, 16).replace('T', ' ') }}</small></span></button><small v-if="!caseList.length && !caseListLoading" class="case-list-empty">{{ dbEnabled ? '尚無案件' : '案件僅保存到後端重啟' }}</small></div>
      <div class="side-bottom"><div class="user"><span class="avatar">{{ (currentUser || 'E').slice(0, 1).toUpperCase() }}</span><span>{{ currentUser || '案件工作空間' }}</span><button v-if="authRequired" class="logout" title="登出" aria-label="登出" @click="logout"><Icon name="logout" :size="16" /><span>登出</span></button><span v-else class="online"></span></div></div>
    </aside>

    <div class="main-shell">
      <header ref="topbar" class="topbar">
        <nav class="breadcrumb" aria-label="麵包屑"><a href="#workspace" @click.prevent="goToWorkspace">案件工作台</a><Icon name="chevron" :size="13" /><a href="#current-case" @click.prevent="goToWorkspace">{{ caseLabel }}</a></nav>
        <div class="topbar-right"><div class="font-controls" role="group" aria-label="調整字級"><span>字級</span><button v-for="size in fontSizes" :key="size.value" :aria-pressed="fontSize === size.value" @click="fontSize = size.value">{{ size.label }}</button></div><span class="organization"><Icon name="scales" :size="18" />新北市政府法制局</span></div>
      </header>
      <main>
        <div class="page-title"><div><div class="case-eyebrow">{{ ready || running ? `案件 ${caseLabel}` : '建立新案件' }} <span>行政訴願</span></div><h1>{{ ready || running ? caseTitle : '開始一份新的案件審查' }}</h1><p><span>訴願人 {{ summary.appellant.name || '待辨識' }}</span><i></i><span>原處分機關 {{ summary.agency || '待辨識' }}</span><i></i><span class="status-text"><span></span>{{ running ? '分析中' : ready ? '草稿待審閱' : '等待文件' }}</span></p></div></div>





        <nav ref="pipelineNav" class="pipeline" aria-label="案件處理階段" :aria-busy="running"><button v-for="(step, i) in steps" :key="step.title" :class="{ current: running ? progress === i : active === i, done: running && i < progress }" :aria-current="(running ? progress === i : active === i) ? 'step' : undefined" :disabled="!stepAvailable(i)" :aria-label="step.short + '：' + stepStatus(i)" @click="active = i"><span class="step-number"><Icon v-if="running && i < progress" name="check" :size="15" /><template v-else>{{ String(i + 1).padStart(2, '0') }}</template></span><span>{{ step.short }}</span><Icon v-if="i < steps.length - 1" class="step-chevron" name="chevron" :size="14" /></button></nav>

        <div class="section-heading"><div><h2 ref="sectionTitle" tabindex="-1">{{ steps[active]!.title }} <span v-if="active === 4" class="tag" :class="{ green: draftVersion }">{{ draftLabel }}</span></h2><p>{{ steps[active]!.description }}</p></div><div v-if="ready && active === 4" class="export-actions"><template v-if="dbEnabled && lastEnvelope"><label v-if="draftVersions.length" class="version-select"><span>版本</span><select :value="draftVersion" :disabled="exporting || saving || editing" @change="switchDraft(Number(($event.target as HTMLSelectElement).value))"><option :value="0">AI 原稿</option><option v-for="v in draftVersions" :key="v.version" :value="v.version">v{{ v.version }}{{ v.note ? ' · ' + v.note : '' }}（{{ v.edited_by || '承辦人' }}）</option></select></label><button v-if="!editing" class="button secondary" :disabled="exporting || saving" @click="startEdit"><Icon name="edit" :size="17" />編輯草稿</button></template><button class="button primary" :disabled="exporting || editing" @click="downloadDraft()"><Icon name="download" :size="17" />{{ exporting ? '匯出中…' : '匯出 PDF' }}</button><button class="button secondary" :disabled="exporting || editing" @click="downloadDraft('docx')">匯出 Word</button></div></div>

        <div class="step-guidance"><span>第 {{ active + 1 }} / {{ steps.length }} 步</span><p>{{ guidance[active] }}</p></div>
        <div v-if="ready && active === 4 && editing" class="edit-bar" role="region" aria-label="編輯草稿"><Icon name="edit" :size="16" /><span>逐段修改後儲存為新版本；AI 原稿不會被覆蓋，可隨時還原。</span><input v-model="editNote" type="text" placeholder="版本備註（選填）" maxlength="80" aria-label="版本備註" /><button class="button primary" :disabled="saving" @click="saveEdit">{{ saving ? '儲存中…' : '儲存版本' }}</button><button class="button secondary" :disabled="saving" @click="editing = false">取消</button></div>
        <template v-if="active === 0">
          <ProcessingStatus v-if="processingVisible" :phase="progress" :running="running" :complete="processingComplete" :elapsed="elapsed" :files="fileNames" :error="processingError" :live-note="liveNote" :live-text="liveText" note="文件仍需人工核對；重新整理會清除本頁內容。" @cancel="stopDemo" @retry="runDemo" @view="active = 1" /><button v-if="processingVisible && !running" class="button secondary edit-files" @click="processingVisible = false">返回修改文件</button>

<div v-if="!processingVisible" class="service-date-field">
  <div class="service-date-heading"><label for="service-date">送達日期 <span>（選填）</span></label></div>
  <p id="service-date-help">請依原處分的送達證明填寫；不確定可先留空，後續由承辦人核對。</p>
  <div class="service-date-control"><input id="service-date" v-model="serviceDate" type="text" placeholder="113/01/31" maxlength="9" :disabled="running" :aria-invalid="!!serviceDateError" aria-describedby="service-date-help service-date-note service-date-error" /><button v-if="serviceDate" class="button secondary" :disabled="running" @click="serviceDate = ''">清除日期</button></div>
  <small id="service-date-note">請輸入民國年/月/日，例如 113/01/31（民國 113 年 1 月 31 日）；不確定可留空。</small>
  <p v-if="serviceDateError" id="service-date-error" class="service-date-error" role="status">{{ serviceDateError }}</p>
</div>
          <section v-if="!processingVisible" class="panel upload-panel"><div class="panel-title"><Icon name="upload" /><h3>匯入案件文件</h3><span class="tag">2 份必要文件</span></div><p class="muted">請上傳清晰的訴願書與原處分書影像。</p><div class="upload-grid"><div v-for="(label, i) in ['訴願書', '原處分書']" :key="label" class="upload-item"><label class="upload-zone" :class="{ 'has-error': fileErrors[i], 'has-file': files[i] }"><input type="file" :aria-label="'選擇' + label + '圖片'" :aria-invalid="!!fileErrors[i]" :aria-describedby="'upload-feedback-' + i" accept="image/jpeg,image/png,image/webp" :disabled="running" @change="selectFile($event, i)" /><img v-if="previews[i]" :src="previews[i]" :alt="label + '預覽'" /><Icon v-else name="upload" :size="30" /><b>{{ label }}</b><span>{{ fileNames[i] }}</span><small>{{ files[i] ? '已選擇 · 點選可更換圖片' : '點選選擇圖片' }} · JPG / PNG / WebP · 上限 10 MB</small><span :id="'upload-feedback-' + i" class="upload-feedback" :class="{ 'field-error': fileErrors[i] }" aria-live="polite">{{ fileErrors[i] || (files[i] ? '圖片已備妥' : '尚未選擇圖片') }}</span></label><button v-if="files[i]" class="button secondary remove-file" :disabled="running || exporting || demoLoading" @click="removeFile(i)">移除{{ label }}</button></div></div>
<div class="demo-file-actions"><button class="button secondary" :disabled="running || exporting || demoLoading" @click="requestCase('demo')"><Icon name="file" :size="17" />{{ demoLoading ? '載入中…' : '載入 Demo 文件' }}</button><button class="button secondary" :disabled="running || exporting || demoLoading" @click="requestCase('demo-run')"><Icon name="spark" :size="17" />一鍵 Demo（載入並分析）</button></div><div class="panel-actions upload-actions"><p id="upload-hint" role="status">{{ uploadHint }}</p><button class="button primary" :disabled="running || demoLoading || !canAnalyze" aria-describedby="upload-hint" @click="runDemo"><Icon name="spark" :size="17" />{{ running ? '分析中…' : '開始分析' }}</button></div></section>

        </template>

        <template v-else-if="active === 1">
          <div class="document-tabs"><button v-for="(name, i) in ['訴願書', '原處分書']" :key="name" :class="{ active: documentIndex === i }" @click="documentIndex = i">{{ name }}</button></div><div class="ocr-layout"><section class="panel"><div class="panel-title"><Icon name="file" /><h3>原始文件</h3><DocumentZoom :src="previews[documentIndex] || ''" :title="documentIndex === 0 ? '訴願書' : '原處分書'" /></div><div class="scan-preview"><img v-if="previews[documentIndex]" :src="previews[documentIndex]" alt="所選文件預覽" /><div v-else class="sample-document"><span class="sample-stamp">模擬文件</span><h3>{{ documentIndex === 0 ? '訴 願 書' : '書 面 告 誡' }}</h3><p>{{ documentIndex === 0 ? ocrText : dispositionText }}</p></div></div></section><section class="panel"><div class="panel-title"><Icon name="scan" /><h3>辨識結果</h3><span v-if="pii" class="tag green" :title="piiLabel">{{ piiLabel }}</span></div><div class="ocr-content"><p>{{ documentIndex === 0 ? ocrText : dispositionText }}</p><h4>擷取欄位</h4><dl class="fields"><div><dt>訴願人</dt><dd>{{ summary.appellant.name || '—' }}</dd></div><div><dt>案件類型</dt><dd>{{ summary.case_type || '—' }}</dd></div><div><dt>核心主張</dt><dd>{{ summary.appellant_claims.join('、') }}</dd></div></dl></div></section></div>
        </template>

        <template v-else-if="active === 2">
          <section class="panel procedure-panel"><div class="panel-title"><Icon name="shield" /><h3>程序審查結果</h3><span class="tag green">{{ procedure.checks.filter(c => c.pass).length }} / {{ procedure.checks.length }} 項通過</span></div><div class="check-row" v-for="item in procedure.checks" :key="item.rule"><span class="check-symbol" :class="{ warning: !item.pass }"><Icon :name="item.pass ? 'check' : 'info'" /></span><div><h3>{{ item.rule }}</h3><p>{{ item.note || `送達日 ${item.served} → 提起日 ${item.filed}，相隔 ${item.days} 天。` }}</p></div><span :class="['tag', item.pass && !item.needs_review ? 'green' : 'amber']">{{ item.pass ? (item.needs_review ? '通過・請人工確認' : '通過') : item.needs_review ? '待人工確認' : '未通過' }}</span></div><div class="info-bar">{{ procedure.admissible ? '程序合法，進入實體審查。' : '程序有疑義，請人工確認。' }}</div></section>
        </template>

        <template v-else-if="active === 3">
          <div v-if="historyLabel" class="info-bar history-bar"><Icon name="book" :size="16" />{{ historyLabel }}</div><div class="filter-row"><button v-for="type in ['全部', '法條', '判解', '立法理由', '相似案']" :key="type" :class="{ active: filter === type }" @click="filter = type">{{ type }} <span>{{ type === '全部' ? sources.length : sources.filter(s => s.type === type).length }}</span></button></div><div class="retrieval-grid"><article class="panel source-result" v-for="item in filteredSources" :key="item.id"><span class="tag">{{ item.type }}</span><h3>{{ item.title }}</h3><p class="muted">{{ item.subtitle }}</p><p>{{ item.content }}</p><div class="result-footer"><span class="tag green">{{ item.tag }}</span></div></article></div>
        </template>

        <template v-else-if="active === 4">
          <div class="draft-layout"><section class="document-panel"><div class="document-toolbar"><span><Icon name="file" :size="16" />{{ caseLabel }}_訴願決定書</span><span><span class="small-dot"></span>已生成 <span class="toolbar-divider">|</span> 草稿</span></div><article class="decision-paper"><div class="paper-topline"><span>新北市政府</span><span class="draft-stamp">草 稿</span></div><h2>訴願決定書</h2><div class="paper-case-number">案號：{{ caseLabel }}</div><dl class="paper-meta"><div><dt>訴願人</dt><dd>{{ header.appellant || summary.appellant.name || '—' }}</dd></div><div><dt>原處分機關</dt><dd>{{ header.agency || summary.agency || '—' }}</dd></div><div><dt>案由</dt><dd>{{ header.case_type || summary.case_type || '—' }}</dd></div></dl><p class="paper-intro">訴願人因{{ header.case_type || summary.case_type || '本件' }}，不服原處分機關{{ header.disposition_ref || '' }}所為之{{ summary.disposition.type || '處分' }}，提起訴願，本府決定如下：</p><section v-for="(part, pi) in draft" :key="part.title" class="draft-section"><div class="draft-section-title"><h3>{{ part.title }}</h3><button v-if="part.citations.length" :aria-expanded="expanded === part.title" @click="expanded = expanded === part.title ? '' : part.title"><Icon name="link" :size="13" />{{ part.citations.length }} 筆引用 <span>{{ expanded === part.title ? '−' : '+' }}</span></button><span v-else class="paper-note">{{ part.title === '教示' ? '待人工補正' : '依案件摘要' }}</span></div><textarea v-if="editing" class="draft-edit" :aria-label="'編輯' + part.title" rows="4" :value="part.title === '主文' ? edited.holding : part.title === '事實' ? edited.facts : part.title === '教示' ? edited.instruction : (edited.reasons[pi - 2] ?? '')" @input="e => { const v = (e.target as HTMLTextAreaElement).value; if (part.title === '主文') edited.holding = v; else if (part.title === '事實') edited.facts = v; else if (part.title === '教示') edited.instruction = v; else edited.reasons[pi - 2] = v }"></textarea><p v-else>{{ part.text }}</p><div v-if="expanded === part.title && !editing" class="citation-chips"><button v-for="c in part.citations" :key="c.id + c.label" :class="{ selected: selectedSource === c.id }" :title="sources.find(s => s.id === c.id)?.title" @click="showSource(c.id)"><Icon name="book" :size="13" />{{ c.label }}<Icon name="chevron" :size="12" /></button></div></section><footer class="paper-footer">草稿內容須由承辦人核對事實、引用依據及救濟教示。</footer></article><div class="document-foot"><span>{{ draft.length }} 個段落</span><span>{{ draftLabel }} · 待人工審閱</span></div></section>
          <aside class="evidence-column"><section class="panel evidence-panel"><div class="panel-title"><Icon name="book" :size="18" /><h3>引用依據</h3><span class="count">{{ sources.length }}</span></div><p class="evidence-hint">點選草稿中的引用，查看對應來源。</p><div class="source-list"><button v-for="item in sources" :key="item.id" :class="{ active: selectedSource === item.id }" @click="showSource(item.id)"><span class="source-type">{{ item.type }}</span><span><b>{{ item.title }}</b><small>{{ item.subtitle }}</small></span><Icon name="chevron" :size="14" /></button></div><div ref="sourceDetail" class="source-detail" tabindex="-1" aria-label="引用來源內容"><div><span class="tag">{{ source.tag }}</span></div><h4>{{ source.title }}</h4><p>{{ source.content }}</p></div></section><section class="panel gap-panel"><div class="panel-title"><Icon name="info" :size="18" /><h3>待補查與資料差異</h3><span class="tag amber">{{ gaps.length }}</span></div><ul><li v-for="gap in gaps" :key="gap">{{ gap }}</li></ul></section><section v-if="showDeveloperChecks" class="panel quick-check"><div class="panel-title"><Icon name="shield" :size="18" /><h3>草稿檢核</h3><span class="tag amber">{{ report.checks.length ? `${totals.passed} / ${totals.total}` : '未檢核' }}</span></div><div v-for="item in checks" :key="item.title" class="mini-check"><Icon :name="item.status ? 'check' : 'info'" :size="16" :class="item.status ? 'text-green' : 'text-amber'" /><span>{{ item.title }}</span></div><button class="review-link" @click="active = 5">檢視完整檢核表 <Icon name="arrow" :size="16" /></button></section><div class="human-note"><Icon name="info" :size="18" /><p>AI 提供輔助，判斷仍由人作成。<br>請確認事實、法源及救濟教示。</p></div></aside></div>
        </template>

        <template v-else-if="showDeveloperChecks && active === 5">
          <section class="panel quality-panel"><div class="quality-summary"><span class="quality-icon"><Icon name="shield" :size="32" /></span><div><h3>{{ reviewed ? '已完成審閱' : report.checks.length ? '與標準答案比對，讓差異清楚可見' : '尚未取得檢核結果' }}</h3><p>{{ totals.passed }} 項通過，{{ totals.failed }} 項未通過 · 論理要點 {{ report.score['論理要點'] }}</p></div><span class="quality-score">{{ totals.passed }}<span>/ {{ totals.total }}</span></span></div><div class="comparison-note info-bar">{{ reportNote }}</div><div class="comparison-grid"><div><h4>本次檢索已涵蓋</h4><p v-for="name in validation.gold_citations_recalled" :key="name"><Icon name="check" :size="14" />{{ name }}</p></div><div><h4>正本引用但未檢索到</h4><p v-for="name in validation.gold_citations_missed" :key="name"><Icon name="info" :size="14" />{{ name }}</p></div></div><details v-for="group in ['段落', '格式', '結論', '事實', '引用', '論理', '防幻覺']" :key="group" class="report-group" :open="group === '結論' || group === '防幻覺'"><summary>{{ group }}<span class="tag">{{ report.score[group as keyof typeof report.score] }}</span></summary><div class="check-row" v-for="item in report.checks.filter(c => c.group === group)" :key="item.item"><span class="check-symbol" :class="{ warning: !item.pass }"><Icon :name="item.pass ? 'check' : 'info'" /></span><div><h3>{{ item.item }}</h3><p v-if="item.note">{{ item.note }}</p></div><span :class="['tag', item.pass ? 'green' : 'amber']">{{ item.pass ? '通過' : '未通過' }}</span></div></details><div class="quality-confirm"><label><input type="checkbox" v-model="reviewed" />我已檢視此示範草稿，了解法律內容與救濟教示仍需人工核對。</label><button class="button primary" :disabled="!reviewed || exporting" @click="downloadDraft()"><Icon name="download" :size="17" />下載示範草稿</button></div></section>

        </template>
        <nav v-if="ready && active > 0" class="step-actions" aria-label="步驟導覽"><button class="button secondary" @click="active--">上一步：{{ steps[active - 1]!.title }}</button><span>第 {{ active + 1 }} / {{ steps.length }} 步</span><button v-if="active < steps.length - 1" class="button primary" @click="active++">下一步：{{ steps[active + 1]!.title }} <Icon name="arrow" :size="16" /></button><button v-else class="button primary" :disabled="exporting || editing" @click="downloadDraft()"><Icon name="download" :size="17" />{{ exporting ? '匯出中…' : '匯出 PDF' }}</button></nav>
        <footer class="page-footer"><span><Icon name="scales" :size="14" />訴願審查助手 · 讓審查更有依據</span></footer>
      </main>
    </div>
    <dialog ref="confirmDialog" class="case-confirm" aria-labelledby="confirm-title" aria-describedby="confirm-description" @close="restoreActionFocus"><h2 id="confirm-title">{{ pendingAction === 'new' ? '建立新案件？' : '以 Demo 文件取代目前內容？' }}</h2><p id="confirm-description">目前選擇的圖片、送達日期與審閱狀態將會清除。若要保留目前操作，請選擇繼續編輯。</p><div class="confirm-actions"><button ref="cancelButton" class="button secondary" @click="confirmDialog?.close()">繼續編輯</button><button class="button primary" @click="confirmCase">{{ pendingAction === 'new' ? '清除並新建案件' : pendingAction === 'demo-run' ? '取代並開始分析' : '取代並載入文件' }}</button></div></dialog>
    <div v-if="toast" class="toast" role="status"><Icon name="info" :size="18" />{{ toast }}</div>
  </div>
</template>
