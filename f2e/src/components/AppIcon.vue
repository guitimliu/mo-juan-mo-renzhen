<script setup lang="ts">
withDefaults(defineProps<{ name: string; size?: number }>(), { size: 20 })
const paths: Record<string, string> = {
  scales: 'M12 3v17M5 21h14M4 7h16M6 7l-4 8h8L6 7Zm12 0-4 8h8l-4-8Z',
  grid: 'M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z',
  file: 'M14 2H5v20h14V7l-5-5Zm0 0v6h5M8 12h8M8 16h6',
  upload: 'M12 16V3m-5 5 5-5 5 5M4 16v5h16v-5',
  scan: 'M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5M7 8h10M7 12h10M7 16h6',
  shield: 'M12 2 3 6v6c0 5 9 10 9 10s9-5 9-10V6l-9-4Zm-4 10 3 3 5-6',
  search: 'M21 21l-5-5M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0Z',
  edit: 'm15 4 5 5M4 20l5-1L21 7l-5-5L4 14v6ZM12 20h9',
  check: 'm5 12 4 4L19 6',
  list: 'm3 6 1 1 2-3M9 5h12M3 12l1 1 2-3M9 11h12M3 18l1 1 2-3M9 17h12',
  logout: 'M9 4H4v16h5M10 12h11m-4-4 4 4-4 4',
  arrow: 'M5 12h14m-6-6 6 6-6 6',
  chevron: 'm9 5 7 7-7 7',
  download: 'M12 3v13m-5-5 5 5 5-5M4 17v4h16v-4',
  plus: 'M12 5v14M5 12h14',
  clock: 'M12 8v5l3 2M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0Z',
  book: 'M12 5v16M12 5C8 2 4 3 2 4v16c4-2 7-1 10 1 3-2 6-3 10-1V4c-2-1-6-2-10 1Z',
  info: 'M12 11v6M12 7h.01M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0Z',
  spark: 'm12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3Z',
  link: 'm10 13 4-4M8 15l-1 1a4 4 0 0 1-6-6l5-5a4 4 0 0 1 6 0m4 4 1-1a4 4 0 0 1 6 6l-5 5a4 4 0 0 1-6 0',
}
</script>
<template><svg :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path :d="paths[name] || paths.file" /></svg></template>
