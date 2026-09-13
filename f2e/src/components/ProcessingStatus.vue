<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import Icon from './AppIcon.vue'
import { showDeveloperChecks } from '../data/demo'
const props = withDefaults(defineProps<{ phase: number; running: boolean; complete: boolean; elapsed: number; files: (string | undefined)[]; error?: string; note?: string; liveNote?: string; liveText?: string }>(), { error: '', note: '請保持此頁開啟，完成後即可核對結果。', liveNote: '', liveText: '' })
defineEmits<{ cancel: []; retry: []; view: [] }>()
const stages = [
  { title: '接收案件文件', description: '接收訴願書與原處分書，建立案件。', result: '已收到 2 份文件，案件已建立', icon: 'upload' },
  { title: '文字辨識（OCR）', description: '讀取兩份文件內容，整理案件資訊與訴願主張。', result: '文字對照與案件摘要已備妥', icon: 'scan' },
  { title: '程序檢核', description: '檢查訴願期間、當事人與處分資訊，標示待確認項目。', result: '程序燈號與檢核說明已備妥', icon: 'shield' },
  { title: '檢索法條與相似案', description: '比對案件爭點，整理法條、判解及相似案例來源。', result: '法條、判解、立法理由與相似案已整理', icon: 'search' },
  { title: '生成決定書草稿', description: '依主文、事實、理由及教示編排草稿，連結引用依據。', result: '4 個草稿段落已備妥', icon: 'edit' },
  { title: '正本比對與檢核', description: '比對草稿與檢索結果，呈現引用缺漏與待確認差異。', result: '檢核表已備妥，等待人工審閱', icon: 'list' },
].filter((_, index) => showDeveloperChecks || index < 5)
const current = computed(() => stages[Math.min(props.phase, stages.length - 1)]!)
const heading = computed(() => props.complete ? '分析完成，開始審閱案件' : props.running ? current.value.title : props.error ? '分析失敗' : '已停止本次分析')

const headingElement = ref<HTMLElement | null>(null)
const liveBox = ref<HTMLElement | null>(null)
// 串流內容是模型輸出的 S4 JSON；顯示時把欄位名轉成中文標籤、去掉引號與括號，讀起來像文件
const LIVE_LABELS: Record<string, string> = { header: '表頭', case_type: '案由', appellant: '訴願人', agency: '原處分機關', disposition_ref: '處分', holding: '主文', facts: '事實', reasons: '理由', instruction: '教示', citations: '引用', provenance: '產生方式', gaps: '待補查', text: '', source: '來源', section: '', index: '' }
function prettyLive(raw: string) {
  return raw
    .replace(/"([a-z_]+)"\s*:\s*/g, (_, k: string) => (LIVE_LABELS[k] ?? k) ? `\n${LIVE_LABELS[k] ?? k}：` : '')
    .replace(/\\"/g, '"').replace(/\\n/g, '\n')
    .replace(/[{}\[\]"]/g, '').replace(/,\s*\n/g, '\n').replace(/\n{2,}/g, '\n').trim()
}
const liveTail = computed(() => { const t = prettyLive(props.liveText); return t.length > 1200 ? '…' + t.slice(-1200) : t })
watch(() => props.liveText, () => { if (liveBox.value) liveBox.value.scrollTop = liveBox.value.scrollHeight }, { flush: 'post' })
onMounted(() => {
  headingElement.value?.focus({ preventScroll: true })
  headingElement.value?.scrollIntoView({ block: 'center', behavior: 'instant' })
})
</script>

<template>
  <section class="processing-panel" :class="{ complete }" aria-label="案件處理進度">
    <header class="processing-header">
      <span class="processing-emblem"><Icon :name="complete ? 'check' : running ? current.icon : 'clock'" :size="27" /></span>
      <div class="processing-heading" role="status" aria-live="polite" aria-atomic="true">
        <span class="processing-kicker">{{ complete ? '所有階段已完成' : running ? `正在處理 · 第 ${Math.min(phase + 1, stages.length)} / ${stages.length} 步` : error ? '處理未完成' : '流程已暫停' }}</span>
        <h3 ref="headingElement" tabindex="-1">{{ heading }}</h3>
        <p>{{ complete ? '文字辨識、程序檢核、法源與草稿皆已就緒，請從原始文件開始核對。' : running ? (liveNote || current.description) : error ? error : '選擇的文件仍保留，可以重新開始，不需要再次選檔。' }}</p>

      </div>
      <span class="elapsed"><Icon name="clock" :size="14" />{{ complete || !running ? '本次耗時' : '已等待' }} {{ elapsed }} 秒</span>
    </header>
    <div class="stage-meter" aria-hidden="true"><span v-for="(_, i) in stages" :key="i" :class="{ finished: complete || i < phase, processing: running && i === phase }"></span></div>
    <div class="processing-meta"><span>{{ complete ? stages.length : Math.min(phase, stages.length) }} / {{ stages.length }} 個步驟已完成</span><span>{{ running ? '請保持此頁開啟，完成後會顯示結果入口' : complete ? '仍需人工審閱' : '尚未產生本次結果' }}</span></div>
    <div v-if="running && liveText" class="live-wrap"><div class="live-title"><span class="spinner"></span>AI 正在撰寫草稿（逐字顯示）<span class="live-count">{{ liveText.length }} 字</span></div><pre ref="liveBox" class="live-draft" aria-live="off" aria-label="生成中的草稿">{{ liveTail }}</pre></div>
    <ol class="processing-stages">
      <li v-for="(stage, i) in stages" :key="stage.title" :class="{ finished: complete || i < phase, processing: running && i === phase }" :aria-current="running && i === phase ? 'step' : undefined">
        <span class="stage-marker"><Icon v-if="complete || i < phase" name="check" :size="16" /><span v-else-if="running && i === phase" class="spinner"></span><span v-else>{{ i + 1 }}</span></span>
        <div><h4>{{ stage.title }}</h4><p>{{ complete || i < phase ? stage.result : i === phase && running ? (liveNote || stage.description) : '等待前一步完成' }}</p>
</div>
        <span class="stage-state">{{ complete || i < phase ? '已完成' : running && i === phase ? '處理中' : !running && i === phase ? (error ? '失敗' : '已停止') : '等待中' }}</span>
      </li>
    </ol>
    <div class="processing-files"><Icon name="file" :size="15" /><span v-for="name in files" :key="name">{{ name }}</span></div>
    <footer class="processing-footer"><p><Icon name="info" :size="15" />{{ note }}</p><button v-if="running" class="button secondary" @click="$emit('cancel')">停止更新進度</button><button v-else-if="complete" class="button primary" @click="$emit('view')">查看文字對照 <Icon name="arrow" :size="16" /></button><button v-else class="button primary" @click="$emit('retry')">重新開始分析 <Icon name="arrow" :size="16" /></button></footer>

  </section>
</template>
