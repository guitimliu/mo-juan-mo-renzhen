<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import Icon from './components/AppIcon.vue'
import ProcessingStatus from './components/ProcessingStatus.vue'
import { showDeveloperChecks, steps, fixture, empty, buildView, stagesFrom } from './data/demo'
import { ApiError, createCase, getCase, getHealth, sleep, POLL_INTERVAL_MS, POLL_TIMEOUT_MS, type CaseEnvelope } from './api'

// 資料流：view 由 envelope（後端 API）或 fixture（保底）建出；template 透過下列 computed 讀取。
const view = ref(fixture)
const dataSource = ref<'fixture' | 'api'>('fixture')
const caseId = ref('')
const adapterMode = ref<string | null>(null)
const processingError = ref('')
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
const ocrNote = computed(() => view.value.ocrNote)
const caseLabel = computed(() => dataSource.value === 'api' ? caseId.value : useSample.value ? '113-16' : '新建案件')
const caseTitle = computed(() => summary.value.case_type || (useSample.value ? '違反洗錢防制法事件' : '待匯入案件文件'))
const modeLabel = computed(() => adapterMode.value === 'stub' ? '示範資料（stub）' : adapterMode.value ? `後端 ${adapterMode.value}` : '後端未連線')
const sourceLabel = computed(() => dataSource.value === 'api' ? `後端 API · ${modeLabel.value}` : '本機 fixture（保底）')
const provenanceNote = computed(() => view.value.provenance || (dataSource.value === 'api' ? '草稿由後端生成，仍須人工核對。' : '本機 fixture：正本轉製，非 AI 生成。'))
const reportNote = computed(() => `此報告由 07_檢核.py 對${dataSource.value === 'api' ? '後端回傳' : 'fixture'}的草稿與檢索結果實際計算；stub 模式草稿為正本改寫，不代表 AI 生成品質。` + (view.value.failedItems.length ? `未通過：${view.value.failedItems.join('；')}。` : ''))

const active = ref(4)
const selectedSource = ref('statutes[0]')
const filter = ref('全部')
const NO_SOURCE = { id: '', type: '', title: '尚無檢索來源', subtitle: '', content: '', tag: '' }
const source = computed(() => sources.value.find(s => s.id === selectedSource.value) || sources.value[0] || NO_SOURCE)
const filteredSources = computed(() => sources.value.filter(s => filter.value === '全部' || s.type === filter.value))
const ready = ref(true)
const running = ref(false)
const progress = ref(0)
const processingVisible = ref(false)
const processingComplete = ref(false)
const elapsed = ref(0)
const toast = ref('')
const reviewed = ref(false)
const files = ref<(File | null)[]>([null, null])
const previews = ref<string[]>(['', ''])
const useSample = ref(true)
const serviceDate = ref('')
const documentIndex = ref(0)
const expanded = ref('理由（三）')
const sourceDetail = ref<HTMLElement | null>(null)
watch(active, () => window.scrollTo({ top: 0, behavior: 'instant' }))
async function showSource(id: string) {
  selectedSource.value = id
  await nextTick()
  sourceDetail.value?.focus({ preventScroll: true })
  sourceDetail.value?.scrollIntoView({ block: 'nearest', behavior: 'instant' })
}
let timer: ReturnType<typeof setInterval> | undefined
let toastTimer: ReturnType<typeof setTimeout> | undefined
let run = 0   // 每次開始分析 +1，讓被停止的輪詢迴圈不再寫回狀態
const fileNames = computed(() => files.value.map((f, i) => f?.name || (useSample.value ? ['01_模擬訴願書.jpg', '02_模擬書面告誡.jpg'][i] : '尚未選擇文件')))
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
  useSample.value = false
  reviewed.value = false
  active.value = 0
  serviceDate.value = ''
  files.value = [null, null]
  previews.value.forEach(url => url && URL.revokeObjectURL(url))
  previews.value = ['', '']
  view.value = empty()
  dataSource.value = 'fixture'
  caseId.value = ''
}
function loadSample() {
  reset()
  view.value = fixture
  useSample.value = true
  ready.value = true
  active.value = 4
  notify('已載入 113-16 示範案件（本機 fixture，非後端結果）')
}
function selectFile(event: Event, index: number) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size > 10 * 1024 * 1024) {
    notify('請選擇 10 MB 以下的 JPG、PNG 或 WebP 圖片')
    input.value = ''
    return
  }
  if (previews.value[index]) URL.revokeObjectURL(previews.value[index]!)
  files.value[index] = file
  previews.value[index] = URL.createObjectURL(file)
  if (ready.value || useSample.value) { view.value = empty(); dataSource.value = 'fixture'; caseId.value = ''; useSample.value = false }
  ready.value = false
  reviewed.value = false
  processingVisible.value = false
  processingComplete.value = false
  processingError.value = ''
}
function stopDemo() {
  clearInterval(timer)
  run++
  running.value = false
  notify('已停止輪詢；後端沒有取消端點，案件仍會在伺服器端跑完')
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
  return active.value === index ? '目前檢視' : index === 5 ? '待人工確認' : '已完成'
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
  const [petition, disposition] = files.value
  if (!petition || !disposition) return notify(useSample.value ? '示範案件是本機 fixture；請選擇兩份圖片後交給後端分析' : '請先選擇訴願書與原處分書兩份圖片')
  const myRun = ++run
  running.value = true
  ready.value = false
  useSample.value = false
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
  const startedAt = Date.now()
  timer = setInterval(() => { elapsed.value = Math.floor((Date.now() - startedAt) / 1000) }, 250)
  try {
    await refreshHealth()
    const { case_id } = await createCase(petition, disposition, serviceDate.value || undefined)
    if (myRun !== run) return
    caseId.value = case_id
    progress.value = 1
    while (myRun === run) {
      await sleep(POLL_INTERVAL_MS)
      if (myRun !== run) return
      const env = await getCase(case_id)
      if (myRun !== run) return
      view.value = buildView(stagesFrom(env))
      adapterMode.value = env.adapter_mode || adapterMode.value
      progress.value = progressFrom(env)
      if (env.status === 'done') {
        clearInterval(timer)
        running.value = false
        ready.value = true
        processingComplete.value = true
        notify(`案件 ${case_id} 已完成，結果來自後端 API`)
        return
      }
      if (env.status === 'error') return failRun(`後端處理失敗：${env.error ?? '未知錯誤'}`)
      if (Date.now() - startedAt > POLL_TIMEOUT_MS) return failRun('等待後端逾時（120 秒），請重試')
    }
  } catch (error) {
    if (myRun !== run) return
    failRun(error instanceof ApiError ? error.message : `發生錯誤：${String(error)}`)
  }
}
async function refreshHealth() {
  try {
    adapterMode.value = (await getHealth()).adapter_mode
  } catch {
    adapterMode.value = null
  }
}
const exporting = ref(false)
async function downloadDraft(format: 'pdf' | 'docx' = 'pdf') {
  if (exporting.value) return
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
onUnmounted(() => { clearInterval(timer); clearTimeout(toastTimer); previews.value.forEach(url => url && URL.revokeObjectURL(url)) })
</script>

<template>
  <div class="workspace">
    <aside class="sidebar">
      <a class="brand" href="#" @click.prevent="loadSample"><span class="brand-symbol"><Icon name="scales" :size="25" /></span><span>訴願審查助手<small>智慧案件審查工作台</small></span></a>
      <div class="workspace-label">法制局工作空間</div>
      <button class="nav-main" @click="active = ready ? 4 : 0"><Icon name="grid" />案件工作台<span class="nav-dot"></span></button>
      <div class="side-divider"></div>
      <div class="side-heading">目前案件 <span>01</span></div>
      <button class="case-nav" @click="active = ready ? 4 : 0"><Icon name="file" /><span><b>{{ caseLabel }}</b><small>{{ caseTitle }}</small></span></button>
      <div class="side-heading flow-heading">審查流程</div>
      <nav aria-label="審查流程"><button v-for="(step, i) in steps" :key="step.title" class="side-step" :class="{ selected: active === i }" :disabled="!stepAvailable(i)" @click="active = i"><Icon :name="step.icon" :size="18" /><span>{{ step.title }}</span><Icon v-if="ready && i < 4" name="check" :size="14" /><span v-else-if="i === 4 && ready" class="little-dot"></span></button></nav>
      <div class="side-bottom"><div class="user"><span class="avatar">E</span><span>案件工作空間<small>{{ adapterMode ? modeLabel : '後端未連線 · 僅本機 fixture' }}</small></span><span class="online" :title="modeLabel"></span></div></div>
    </aside>

    <div class="main-shell">
      <header class="topbar"><div class="breadcrumb">案件工作台 <Icon name="chevron" :size="13" /><span>{{ caseLabel }}</span><Icon name="chevron" :size="13" /><span :title="sourceLabel">{{ dataSource === 'api' ? modeLabel : '本機 fixture' }}</span></div><div class="topbar-right"><Icon name="scales" :size="18" /><span>新北市政府法制局</span></div></header>
      <main>
        <div class="page-title"><div><div class="case-eyebrow">{{ ready || running ? `案件 ${caseLabel}` : '建立新案件' }} <span>行政訴願</span></div><h1>{{ ready || running ? caseTitle : '開始一份新的案件審查' }}</h1><p><span>訴願人 {{ summary.appellant.name || '待辨識' }}</span><i></i><span>原處分機關 {{ summary.agency || '待辨識' }}</span><i></i><span class="status-text"><span></span>{{ running ? '後端分析中' : ready ? '草稿待審閱' : '等待文件' }}</span></p></div><button class="button secondary" :disabled="running" @click="reset"><Icon name="plus" :size="17" />新建案件</button></div>

        <div class="case-banner"><div class="banner-icon"><Icon name="spark" /></div><div><b>讓繁複的卷證，成為有據可循的決定。</b><p>從文件辨識到草稿生成，完整保留每一步審查依據。</p></div><button @click="loadSample" :disabled="running">載入示範案件 <Icon name="arrow" :size="17" /></button></div>

        <nav class="pipeline" aria-label="案件處理階段" :aria-busy="running"><button v-for="(step, i) in steps" :key="step.title" :class="{ current: running ? progress === i : active === i, done: running ? i < progress : ready && i < 4 }" :aria-current="(running ? progress === i : active === i) ? 'step' : undefined" :disabled="!stepAvailable(i)" @click="active = i"><span class="step-number"><Icon v-if="running ? i < progress : ready && i < 4" name="check" :size="15" /><template v-else>{{ String(i + 1).padStart(2, '0') }}</template></span><span>{{ step.short }}<small>{{ stepStatus(i) }}</small></span><Icon v-if="i < steps.length - 1" class="step-chevron" name="chevron" :size="14" /></button></nav>

        <div class="section-heading"><div><h2>{{ steps[active]!.title }} <span v-if="active === 4" class="tag">初稿 v1</span></h2><p>{{ steps[active]!.description }}</p></div><div v-if="ready && active === 4" class="export-actions"><button class="button primary" :disabled="exporting" @click="downloadDraft()"><Icon name="download" :size="17" />{{ exporting ? '匯出中…' : '匯出 PDF' }}</button><button class="button secondary" :disabled="exporting" @click="downloadDraft('docx')">匯出 Word</button></div></div>

        <template v-if="active === 0">
          <ProcessingStatus v-if="processingVisible" :phase="progress" :running="running" :complete="processingComplete" :elapsed="elapsed" :files="fileNames" :error="processingError" :note="adapterMode === 'stub' ? 'stub 模式：後端回傳的草稿為正本改寫，非 AI 生成；重新整理會重置。' : '進度來自後端 /api/cases 輪詢；重新整理會重置。'" @cancel="stopDemo" @retry="runDemo" @view="active = 1" />
<div v-if="!processingVisible" class="service-date-field">
  <div class="service-date-heading"><label for="service-date">送達日期 <span>（選填）</span></label></div>
  <p id="service-date-help">請依原處分的送達證明填寫；不確定可先留空，後續由承辦人核對。</p>
  <div class="service-date-control"><input id="service-date" v-model="serviceDate" type="date" :disabled="running" aria-describedby="service-date-help service-date-note" /><button v-if="serviceDate" class="button secondary" :disabled="running" @click="serviceDate = ''">清除日期</button></div>
  <small id="service-date-note">請選擇西元日期（例如民國 113 年為西元 2024 年）。</small>
</div>
          <section v-if="!processingVisible" class="panel upload-panel"><div class="panel-title"><Icon name="upload" /><h3>匯入案件文件</h3><span class="tag">2 份必要文件</span></div><p class="muted">請上傳清晰的訴願書與原處分書影像，送交後端分析。</p><div class="upload-grid"><label v-for="(label, i) in ['訴願書', '原處分書']" :key="label" class="upload-zone"><input type="file" accept="image/jpeg,image/png,image/webp" :disabled="running" @change="selectFile($event, i)" /><img v-if="previews[i]" :src="previews[i]" :alt="label + '預覽'" /><Icon v-else name="upload" :size="30" /><b>{{ label }}</b><span>{{ fileNames[i] }}</span><small>點選選擇圖片 · JPG / PNG / WebP · 上限 10 MB</small></label></div>
<div class="info-bar"><Icon name="info" :size="18" />{{ adapterMode === 'stub' ? '後端為 stub 模式：影像會上傳但不辨識，各階段回傳工作包內容（草稿＝正本改寫，非 AI 生成）。' : adapterMode ? `後端模式：${adapterMode}` : '後端未連線：按下分析會顯示錯誤，不會退回假資料。' }}</div><div class="panel-actions"><button class="button primary" :disabled="running" @click="runDemo"><Icon name="spark" :size="17" />{{ running ? '後端分析中…' : '開始分析' }}</button></div></section>
        </template>

        <template v-else-if="active === 1">
          <div class="document-tabs"><button v-for="(name, i) in ['訴願書', '原處分書']" :key="name" :class="{ active: documentIndex === i }" @click="documentIndex = i">{{ name }}</button></div><div class="ocr-layout"><section class="panel"><div class="panel-title"><Icon name="file" /><h3>原始文件</h3></div><div class="scan-preview"><img v-if="previews[documentIndex]" :src="previews[documentIndex]" alt="所選文件預覽" /><div v-else class="sample-document"><span class="sample-stamp">模擬文件</span><h3>{{ documentIndex === 0 ? '訴 願 書' : '書 面 告 誡' }}</h3><p>{{ documentIndex === 0 ? ocrText : dispositionText }}</p></div></div></section><section class="panel"><div class="panel-title"><Icon name="scan" /><h3>辨識結果</h3><span class="tag">{{ sourceLabel }}</span></div><div class="ocr-content"><div v-if="ocrNote" class="info-bar">{{ ocrNote }}</div><p>{{ documentIndex === 0 ? ocrText : dispositionText }}</p><h4>擷取欄位</h4><dl class="fields"><div><dt>訴願人</dt><dd>{{ summary.appellant.name || '—' }}</dd></div><div><dt>案件類型</dt><dd>{{ summary.case_type || '—' }}</dd></div><div><dt>核心主張</dt><dd>{{ summary.appellant_claims.join('、') }}</dd></div></dl></div></section></div>
        </template>

        <template v-else-if="active === 2">
          <section class="panel procedure-panel"><div class="panel-title"><Icon name="shield" /><h3>程序審查結果</h3><span class="tag green">{{ procedure.checks.filter(c => c.pass).length }} / {{ procedure.checks.length }} 項通過</span></div><div class="check-row" v-for="item in procedure.checks" :key="item.rule"><span class="check-symbol" :class="{ warning: !item.pass }"><Icon :name="item.pass ? 'check' : 'info'" /></span><div><h3>{{ item.rule }}</h3><p>{{ item.note || `送達日 ${item.served} → 提起日 ${item.filed}，相隔 ${item.days} 天。` }}</p></div><span :class="['tag', item.pass && !item.needs_review ? 'green' : 'amber']">{{ item.pass ? (item.needs_review ? '通過・請人工確認' : '通過') : item.needs_review ? '待人工確認' : '未通過' }}</span></div><div class="info-bar">{{ dataSource === 'api' ? '由後端規則引擎（backend/app/rules.py）計算，不經 LLM；' : '本機 fixture（後端 stub pipeline 預先算出）；' }}{{ procedure.admissible ? '程序合法，進入實體審查。' : '程序有疑義，請人工確認。' }}</div></section>
        </template>

        <template v-else-if="active === 3">
          <div class="filter-row"><button v-for="type in ['全部', '法條', '判解', '立法理由', '相似案']" :key="type" :class="{ active: filter === type }" @click="filter = type">{{ type }} <span>{{ type === '全部' ? sources.length : sources.filter(s => s.type === type).length }}</span></button></div><div class="retrieval-grid"><article class="panel source-result" v-for="item in filteredSources" :key="item.id"><span class="tag">{{ item.type }}</span><h3>{{ item.title }}</h3><p class="muted">{{ item.subtitle }}</p><p>{{ item.content }}</p><div class="result-footer"><span><Icon name="link" :size="14" />{{ item.id }}</span><span class="tag green">{{ item.tag }}</span></div></article></div>
        </template>

        <template v-else-if="active === 4">
          <div class="draft-layout"><section class="document-panel"><div class="document-toolbar"><span><Icon name="file" :size="16" />{{ caseLabel }}_訴願決定書</span><span><span class="small-dot"></span>已生成 <span class="toolbar-divider">|</span> {{ sourceLabel }}</span></div><article class="decision-paper"><div class="paper-topline"><span>新北市政府</span><span class="draft-stamp">草 稿</span></div><h2>訴願決定書</h2><div class="paper-case-number">案號：{{ caseLabel }}</div><dl class="paper-meta"><div><dt>訴願人</dt><dd>{{ header.appellant || summary.appellant.name || '—' }}</dd></div><div><dt>原處分機關</dt><dd>{{ header.agency || summary.agency || '—' }}</dd></div><div><dt>案由</dt><dd>{{ header.case_type || summary.case_type || '—' }}</dd></div></dl><p class="paper-intro">訴願人因{{ header.case_type || summary.case_type || '本件' }}，不服原處分機關{{ header.disposition_ref || '' }}所為之{{ summary.disposition.type || '處分' }}，提起訴願，本府決定如下：</p><section v-for="part in draft" :key="part.title" class="draft-section"><div class="draft-section-title"><h3>{{ part.title }}</h3><button v-if="part.citations.length" :aria-expanded="expanded === part.title" @click="expanded = expanded === part.title ? '' : part.title"><Icon name="link" :size="13" />{{ part.citations.length }} 筆引用 <span>{{ expanded === part.title ? '−' : '+' }}</span></button><span v-else class="paper-note">{{ part.title === '教示' ? '待人工補正' : '依案件摘要' }}</span></div><p>{{ part.text }}</p><div v-if="expanded === part.title" class="citation-chips"><button v-for="c in part.citations" :key="c.id + c.label" :class="{ selected: selectedSource === c.id }" :title="sources.find(s => s.id === c.id)?.title" @click="showSource(c.id)"><Icon name="book" :size="13" />{{ c.label }}<Icon name="chevron" :size="12" /></button></div></section><footer class="paper-footer">{{ provenanceNote }} 草稿內容須由承辦人核對事實、引用依據及救濟教示。</footer></article><div class="document-foot"><span>{{ draft.length }} 個段落</span><span>{{ sourceLabel }} · 待人工審閱</span></div></section>
          <aside class="evidence-column"><section class="panel evidence-panel"><div class="panel-title"><Icon name="book" :size="18" /><h3>引用依據</h3><span class="count">{{ sources.length }}</span></div><p class="evidence-hint">點選草稿中的引用，查看對應來源。</p><div class="source-list"><button v-for="item in sources" :key="item.id" :class="{ active: selectedSource === item.id }" @click="showSource(item.id)"><span class="source-type">{{ item.type }}</span><span><b>{{ item.title }}</b><small>{{ item.subtitle }}</small></span><Icon name="chevron" :size="14" /></button></div><div ref="sourceDetail" class="source-detail" tabindex="-1" aria-label="引用來源內容"><div><span class="tag">{{ source.tag }}</span><span class="source-id">{{ source.id }}</span></div><h4>{{ source.title }}</h4><p>{{ source.content }}</p></div></section><section class="panel gap-panel"><div class="panel-title"><Icon name="info" :size="18" /><h3>待補查與資料差異</h3><span class="tag amber">{{ gaps.length }}</span></div><ul><li v-for="gap in gaps" :key="gap">{{ gap }}</li></ul></section><section v-if="showDeveloperChecks" class="panel quick-check"><div class="panel-title"><Icon name="shield" :size="18" /><h3>草稿檢核</h3><span class="tag amber">{{ report.checks.length ? `${totals.passed} / ${totals.total}` : '未檢核' }}</span></div><div v-for="item in checks" :key="item.title" class="mini-check"><Icon :name="item.status ? 'check' : 'info'" :size="16" :class="item.status ? 'text-green' : 'text-amber'" /><span>{{ item.title }}</span></div><button class="review-link" @click="active = 5">檢視完整檢核表 <Icon name="arrow" :size="16" /></button></section><div class="human-note"><Icon name="info" :size="18" /><p>AI 提供輔助，判斷仍由人作成。<br>請確認事實、法源及救濟教示。</p></div></aside></div>
        </template>

        <template v-else-if="showDeveloperChecks && active === 5">
          <section class="panel quality-panel"><div class="quality-summary"><span class="quality-icon"><Icon name="shield" :size="32" /></span><div><h3>{{ reviewed ? '已完成審閱' : report.checks.length ? '與標準答案比對，讓差異清楚可見' : '尚未取得檢核結果' }}</h3><p>{{ totals.passed }} 項通過，{{ totals.failed }} 項未通過 · 論理要點 {{ report.score['論理要點'] }}</p></div><span class="quality-score">{{ totals.passed }}<span>/ {{ totals.total }}</span></span></div><div class="comparison-note info-bar">{{ reportNote }}</div><div class="comparison-grid"><div><h4>{{ dataSource === 'api' ? '本次檢索已涵蓋' : '本次 fixture 檢索已涵蓋' }}</h4><p v-for="name in validation.gold_citations_recalled" :key="name"><Icon name="check" :size="14" />{{ name }}</p></div><div><h4>正本引用但未檢索到</h4><p v-for="name in validation.gold_citations_missed" :key="name"><Icon name="info" :size="14" />{{ name }}</p></div></div><details v-for="group in ['段落', '格式', '結論', '事實', '引用', '論理', '防幻覺']" :key="group" class="report-group" :open="group === '結論' || group === '防幻覺'"><summary>{{ group }}<span class="tag">{{ report.score[group as keyof typeof report.score] }}</span></summary><div class="check-row" v-for="item in report.checks.filter(c => c.group === group)" :key="item.item"><span class="check-symbol" :class="{ warning: !item.pass }"><Icon :name="item.pass ? 'check' : 'info'" /></span><div><h3>{{ item.item }}</h3><p v-if="item.note">{{ item.note }}</p></div><span :class="['tag', item.pass ? 'green' : 'amber']">{{ item.pass ? '通過' : '未通過' }}</span></div></details><div class="quality-confirm"><label><input type="checkbox" v-model="reviewed" />我已檢視此示範草稿，了解法律內容與救濟教示仍需人工核對。</label><button class="button primary" :disabled="!reviewed" @click="downloadDraft()"><Icon name="download" :size="17" />下載示範草稿</button></div></section>
        </template>
        <footer class="page-footer"><span><Icon name="scales" :size="14" />訴願審查助手 · 讓審查更有依據</span><span>新北市政府法制局</span></footer>
      </main>
    </div>
    <div v-if="toast" class="toast" role="status"><Icon name="info" :size="18" />{{ toast }}</div>
  </div>
</template>
