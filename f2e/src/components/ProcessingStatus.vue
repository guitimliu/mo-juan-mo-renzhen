<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import Icon from './AppIcon.vue'
const props = withDefaults(defineProps<{ phase: number; running: boolean; complete: boolean; elapsed: number; files: (string | undefined)[]; error?: string; note?: string }>(), { error: '', note: '進度來自後端 /api/cases 輪詢；重新整理會重置。' })
defineEmits<{ cancel: []; retry: []; view: [] }>()
const stages = [
  { title: '接收案件文件', description: '上傳訴願書與原處分書，後端建立案件（POST /api/cases）。', result: '2 份文件已送達後端，案件已建立', icon: 'upload' },
  { title: 'OCR 文字辨識', description: '讀取兩份文件內容，整理案件資訊與訴願主張（S1、S2）。', result: 'OCR 對照與案件摘要已回傳', icon: 'scan' },
  { title: '程序檢核', description: '檢查訴願期間、當事人與處分資訊，標示待確認項目。', result: '程序燈號與檢核說明已備妥', icon: 'shield' },
  { title: '檢索法條與相似案', description: '比對案件爭點，整理法條、判解及相似案例來源。', result: '法條、判解、立法理由與相似案已整理', icon: 'search' },
  { title: '生成決定書草稿', description: '依主文、事實、理由及教示編排草稿，連結引用依據。', result: '4 個草稿段落已備妥', icon: 'edit' },
  { title: '正本比對與檢核', description: '以 07_檢核.py 對草稿與檢索結果打分，呈現引用缺口與待確認差異。', result: '檢核表已備妥，等待人工審閱', icon: 'list' },
]
const current = computed(() => stages[Math.min(props.phase, stages.length - 1)]!)
const heading = computed(() => props.complete ? '分析完成，開始審閱案件' : props.running ? current.value.title : props.error ? '分析失敗' : '已停止本次分析')
const headingElement = ref<HTMLElement | null>(null)
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
        <span class="processing-kicker">{{ complete ? '所有階段已完成' : running ? `正在處理 · 第 ${phase + 1} / 6 步` : error ? '後端回報錯誤' : '流程已暫停' }}</span>
        <h3 ref="headingElement" tabindex="-1">{{ heading }}</h3>
        <p>{{ complete ? 'OCR、程序檢核、法源、草稿與檢核表皆已就緒，請從原始文件開始核對。' : running ? current.description : error ? error : '選擇的文件仍保留，可以重新開始，不需要再次選檔。' }}</p>
      </div>
      <span class="elapsed"><Icon name="clock" :size="14" />{{ complete || !running ? '本次耗時' : '已等待' }} {{ elapsed }} 秒</span>
    </header>
    <div class="stage-meter" aria-hidden="true"><span v-for="(_, i) in stages" :key="i" :class="{ finished: complete || i < phase, processing: running && i === phase }"></span></div>
    <div class="processing-meta"><span>{{ complete ? 6 : phase }} / 6 個步驟已完成</span><span>{{ running ? '請保持此頁開啟，完成後會顯示結果入口' : complete ? '仍需人工審閱' : '尚未產生本次結果' }}</span></div>
    <ol class="processing-stages">
      <li v-for="(stage, i) in stages" :key="stage.title" :class="{ finished: complete || i < phase, processing: running && i === phase }" :aria-current="running && i === phase ? 'step' : undefined">
        <span class="stage-marker"><Icon v-if="complete || i < phase" name="check" :size="16" /><span v-else-if="running && i === phase" class="spinner"></span><span v-else>{{ i + 1 }}</span></span>
        <div><h4>{{ stage.title }}</h4><p>{{ complete || i < phase ? stage.result : i === phase && running ? stage.description : '等待前一步完成' }}</p></div>
        <span class="stage-state">{{ complete || i < phase ? '已完成' : running && i === phase ? '處理中' : !running && i === phase ? (error ? '失敗' : '已停止') : '等待中' }}</span>
      </li>
    </ol>
    <div class="processing-files"><Icon name="file" :size="15" /><span v-for="name in files" :key="name">{{ name }}</span></div>
    <footer class="processing-footer"><p><Icon name="info" :size="15" />{{ note }}</p><button v-if="running" class="button secondary" @click="$emit('cancel')">停止輪詢</button><button v-else-if="complete" class="button primary" @click="$emit('view')">查看 OCR 對照 <Icon name="arrow" :size="16" /></button><button v-else class="button primary" @click="$emit('retry')">重新開始分析 <Icon name="arrow" :size="16" /></button></footer>
  </section>
</template>
