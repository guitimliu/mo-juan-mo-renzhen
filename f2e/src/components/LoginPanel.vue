<script setup lang="ts">
// 帳密登入頁：後端 AUTH_USERNAME／AUTH_PASSWORD 有設（/api/health.auth_required=true）才會出現。
import { ref } from 'vue'
import Icon from './AppIcon.vue'
import { ApiError, login, setToken } from '../api'

const emit = defineEmits<{ (e: 'done', username: string): void }>()
const username = ref('')
const password = ref('')
const error = ref('')
const busy = ref(false)

async function submit() {
  if (busy.value) return
  error.value = ''
  if (!username.value.trim() || !password.value) { error.value = '請輸入帳號與密碼'; return }
  busy.value = true
  try {
    const r = await login(username.value, password.value)
    if (!r.auth_required) { emit('done', ''); return }       // 後端沒開驗證
    setToken(r.token)
    emit('done', r.username || username.value.trim())
  } catch (e) {
    error.value = e instanceof ApiError && e.status === 401 ? '帳號或密碼錯誤' : e instanceof ApiError ? e.message : '登入失敗，請稍後重試。'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="login-shell">
    <form class="login-card" @submit.prevent="submit" aria-labelledby="login-title">
      <div class="login-brand"><span class="brand-symbol"><Icon name="scales" :size="26" /></span><div><b>訴願審查助手</b><small>新北市政府法制局 · 智慧案件審查工作台</small></div></div>
      <h1 id="login-title">登入工作台</h1>
      <p class="muted">請輸入承辦人帳號與密碼。若無法登入，請聯絡管理者。</p>
      <label>帳號<input v-model="username" type="text" autocomplete="username" :disabled="busy" autofocus /></label>
      <label>密碼<input v-model="password" type="password" autocomplete="current-password" :disabled="busy" /></label>
      <div v-if="error" class="login-error" role="alert"><Icon name="info" :size="16" />{{ error }}</div>
      <button class="button primary" type="submit" :disabled="busy"><Icon name="arrow" :size="17" />{{ busy ? '登入中…' : '登入' }}</button>

    </form>
  </div>
</template>

<style scoped>
/* 寬度一律以視窗為上限：shell 不得撐出水平捲軸，card 用 max-width，內部 grid／flex 子元素 min-width:0 才能縮 */
.login-shell{box-sizing:border-box;width:100%;max-width:100%;min-height:100vh;min-height:100dvh;display:grid;place-items:center;padding:24px 16px;overflow-x:hidden;background:linear-gradient(160deg,#eef2f7,#f8fafc)}
.login-card{box-sizing:border-box;width:100%;max-width:420px;min-width:0;background:#fff;border:1px solid var(--border);border-radius:16px;padding:32px 30px;display:grid;gap:14px;box-shadow:0 12px 40px rgba(24,44,72,.08)}
.login-card>*{min-width:0;max-width:100%}
.login-brand{display:flex;align-items:center;gap:12px;margin-bottom:4px}
.login-brand>div{min-width:0}
.login-brand .brand-symbol{flex:none;width:44px;height:44px;border-radius:12px;background:var(--navy);color:#fff;display:grid;place-items:center}
.login-brand b{display:block;font-size:16px;color:var(--navy)}
.login-brand small{display:block;color:var(--muted);overflow-wrap:anywhere}
h1{margin:6px 0 0;font-size:22px;color:var(--navy)}
.muted{color:var(--muted);margin:0;line-height:1.6;overflow-wrap:anywhere}
label{display:grid;gap:6px;font-weight:500;color:#3a4a62;min-width:0}
input{box-sizing:border-box;width:100%;min-width:0;border:1px solid var(--border);border-radius:10px;padding:11px 12px;font-size:15px;font-family:inherit;background:#fbfcfe}
input:focus{outline:2px solid var(--teal);outline-offset:1px;border-color:var(--teal)}
.login-error{display:flex;align-items:center;gap:8px;color:#a13c2e;background:#fdf1ee;border:1px solid #f3cfc7;border-radius:10px;padding:9px 12px;font-size:14px;overflow-wrap:anywhere}
.button{justify-content:center;width:100%}
.login-foot{text-align:center;color:var(--muted);overflow-wrap:anywhere}
@media (max-width:480px){.login-card{padding:24px 18px;border-radius:12px}}
</style>
