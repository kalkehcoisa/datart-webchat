<template>
  <div class="settings-view">
    <h2>Settings</h2>

    <section class="card mt-3">
      <h3>Change Password</h3>
      <div class="field mt-2">
        <label>Current password</label>
        <input v-model="pw.current" type="password" />
      </div>
      <div class="field mt-2">
        <label>New password</label>
        <input v-model="pw.next" type="password" />
      </div>
      <p v-if="pwError" class="error">{{ pwError }}</p>
      <p v-if="pwOk" class="success">{{ pwOk }}</p>
      <button class="btn-primary mt-2" @click="changePw">Update password</button>
    </section>

    <section class="card mt-3">
      <h3>Active Sessions</h3>
      <div v-for="s in sessions" :key="s.id" class="session-row mt-2">
        <div class="flex-col gap-1">
          <span class="text-sm">{{ s.user_agent || 'Unknown browser' }}</span>
          <span class="text-xs text-muted">{{ s.ip_address }} · Last used {{ formatDate(s.last_used) }}</span>
        </div>
        <button class="btn-danger btn-sm" @click="revokeSession(s.id)">Revoke</button>
      </div>
    </section>

    <section class="card mt-3">
      <h3>Danger Zone</h3>
      <p class="text-sm text-muted mt-2">Deleting your account is permanent and cannot be undone.</p>
      <button class="btn-danger mt-2" @click="confirmDelete">Delete account</button>
    </section>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useSocketStore } from '@/stores/socket'
import api from '@/api/client'

const auth = useAuthStore()
const socket = useSocketStore()
const router = useRouter()

const sessions = ref([])
const pw = ref({ current: '', next: '' })
const pwError = ref('')
const pwOk = ref('')

async function loadSessions() {
  const { data } = await api.get('/auth/sessions')
  sessions.value = data
}

async function changePw() {
  pwError.value = ''
  pwOk.value = ''
  try {
    await api.post('/auth/password/change', {
      current_password: pw.value.current,
      new_password: pw.value.next,
    })
    pwOk.value = 'Password updated.'
    pw.value = { current: '', next: '' }
  } catch (e) {
    pwError.value = e.response?.data?.detail || 'Failed'
  }
}

async function revokeSession(id) {
  await api.delete(`/auth/sessions/${id}`)
  await loadSessions()
}

async function confirmDelete() {
  if (confirm('Delete your account permanently?')) {
    await api.delete('/auth/account')
    socket.disconnect()
    auth.user = null
    localStorage.clear()
    router.push('/login')
  }
}

function formatDate(d) {
  return new Date(d).toLocaleString()
}

onMounted(loadSessions)
</script>

<style scoped>
.settings-view { padding: 24px; overflow-y: auto; height: 100%; max-width: 560px; }
h2 { font-size: 20px; }
h3 { font-size: 16px; }
.field label { display: block; font-size: 13px; color: var(--text2); margin-bottom: 4px; }
.session-row { display: flex; align-items: center; justify-content: space-between; border-top: 1px solid var(--border); padding-top: 8px; }
</style>
