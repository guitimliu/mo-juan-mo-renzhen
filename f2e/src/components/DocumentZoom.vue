<script setup lang="ts">
import { nextTick, ref } from 'vue'
import Icon from './AppIcon.vue'

defineProps<{ src: string; title: string }>()
const dialog = ref<HTMLDialogElement | null>(null)
const trigger = ref<HTMLButtonElement | null>(null)
const closeButton = ref<HTMLButtonElement | null>(null)
const viewport = ref<HTMLElement | null>(null)
const zoom = ref(100)

async function open() {
  zoom.value = 100
  dialog.value?.showModal()
  await nextTick()
  viewport.value?.scrollTo(0, 0)
  closeButton.value?.focus()
}
function fit() {
  zoom.value = 100
  viewport.value?.scrollTo(0, 0)
}
</script>

<template>
  <button ref="trigger" class="button secondary zoom-trigger" :disabled="!src" :aria-label="`放大檢視${title}`" @click="open">
    <Icon name="search" :size="18" />放大檢視
  </button>
  <Teleport to="body">
    <dialog ref="dialog" class="document-zoom" aria-labelledby="document-zoom-title" @close="trigger?.focus()" @click="event => { if (event.target === dialog) dialog?.close() }">
      <div class="zoom-shell">
        <header class="zoom-header">
          <h2 id="document-zoom-title">{{ title }} · 原始文件</h2>
          <button ref="closeButton" class="button secondary" @click="dialog?.close()">關閉</button>
        </header>
        <div class="zoom-toolbar" role="group" aria-label="文件縮放">
          <button class="button secondary" :disabled="zoom <= 100" aria-label="縮小文件" @click="zoom = Math.max(100, zoom - 50)">−</button>
          <output aria-live="polite">{{ zoom }}%</output>
          <button class="button secondary" :disabled="zoom >= 300" aria-label="放大文件" @click="zoom = Math.min(300, zoom + 50)">＋</button>
          <button class="button secondary" @click="fit">符合寬度</button>
          <p id="zoom-help">放大後可捲動查看細節，按 Esc 關閉。</p>
        </div>
        <div ref="viewport" class="zoom-viewport" tabindex="0" role="region" aria-label="原始文件大圖" aria-describedby="zoom-help">
          <img v-if="src" :src="src" :alt="title + '原始文件'" :style="{ width: zoom + '%' }" />
        </div>
      </div>
    </dialog>
  </Teleport>
</template>

<style scoped>
.zoom-trigger{margin-left:auto;min-height:44px;flex-shrink:0}
.document-zoom{width:min(1120px,calc(100vw - 32px));height:min(900px,calc(100dvh - 32px));max-width:none;max-height:none;padding:0;border:1px solid #cbd5df;border-radius:12px;color:var(--navy);background:#fff;overflow:hidden}
.document-zoom::backdrop{background:#182c48b3}
.zoom-shell{height:100%;display:flex;flex-direction:column;min-height:0}
.zoom-header{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:16px 24px;border-bottom:1px solid var(--border)}
.zoom-header h2{font-size:1.285714rem;line-height:1.5;margin:0}
.zoom-toolbar{display:flex;align-items:center;gap:12px;flex-wrap:wrap;padding:12px 24px}
.zoom-toolbar output{min-width:48px;text-align:center;font-size:1rem;font-variant-numeric:tabular-nums}
.zoom-toolbar p{font-size:1rem;color:#526474;line-height:1.7;margin:0}
.zoom-header .button,.zoom-toolbar .button{min-width:44px;min-height:44px;font-size:1rem}
.zoom-viewport{flex:1;min-height:0;overflow:auto;background:#e8edf2;overscroll-behavior:contain}
.zoom-viewport img{display:block;max-width:none;height:auto;margin:0}
@media(max-width:680px){.document-zoom{width:calc(100vw - 16px);height:calc(100dvh - 16px)}.zoom-header,.zoom-toolbar{padding:12px;gap:8px}.zoom-toolbar p{width:100%}.zoom-trigger{padding:8px 10px}}
</style>
