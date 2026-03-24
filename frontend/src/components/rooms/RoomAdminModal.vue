<template>
  <div class="modal-overlay" @click.self="$emit('close')">
    <div class="modal" style="max-width:520px">
      <div class="flex justify-between items-center">
        <h2>Admin — #{{ room.name }}</h2>
        <button class="btn-ghost btn-sm" @click="$emit('close')">✕</button>
      </div>

      <div class="tabs flex gap-2 mt-3">
        <button
          v-for="t in tabs"
          :key="t.id"
          :class="['tab-btn', { active: tab === t.id }]"
          @click="tab = t.id"
        >{{ t.label }}</button>
      </div>

      <div v-if="tab === 'bans'" class="tab-content">
        <p v-if="!bans.length" class="text-muted text-sm mt-2">No banned users.</p>
        <div v-for="b in bans" :key="b.id" class="ban-row">
          <span class="text-sm">{{ b.banned_user?.username || '(deleted)' }}</span>
          <span class="text-xs text-muted">banned by {{ b.banned_by?.username || '—' }}</span>
          <button class="btn-secondary btn-sm" @click="unban(b.user_id)">Unban</button>
        </div>
      </div>

      <div v-if="tab === 'invite'" class="tab-content">
        <div class="flex gap-2 mt-2">
          <input v-model="inviteUsername" placeholder="Username" />
          <button class="btn-primary" @click="invite">Invite</button>
        </div>
        <p v-if="inviteMsg" :class="inviteMsg.ok ? 'success' : 'error'">{{ inviteMsg.text }}</p>
      </div>

      <div v-if="tab === 'settings'" class="tab-content">
        <div class="field mt-2">
          <label>Name</label>
          <input v-model="editName" />
        </div>
        <div class="field mt-2">
          <label>Description</label>
          <input v-model="editDesc" />
        </div>
        <button class="btn-primary mt-2" @click="saveSettings">Save</button>
        <hr class="mt-3" style="border-color:var(--border)" />
        <button class="btn-danger mt-3" @click="deleteRoom">Delete room</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '@/api/client'

const props = defineProps({ room: Object })
const emit = defineEmits(['close', 'deleted'])

const tab = ref('bans')
const tabs = [
  { id: 'bans', label: 'Banned users' },
  { id: 'invite', label: 'Invite' },
  { id: 'settings', label: 'Settings' },
]

const bans = ref([])
const inviteUsername = ref('')
const inviteMsg = ref(null)
const editName = ref(props.room.name)
const editDesc = ref(props.room.description || '')

async function loadBans() {
  const { data } = await api.get(`/rooms/${props.room.id}/bans`)
  bans.value = data
}

async function unban(userId) {
  await api.delete(`/rooms/${props.room.id}/members/${userId}/ban`)
  await loadBans()
}

async function invite() {
  inviteMsg.value = null
  try {
    await api.post(`/rooms/${props.room.id}/invite`, { username: inviteUsername.value })
    inviteMsg.value = { ok: true, text: 'Invited!' }
    inviteUsername.value = ''
  } catch (e) {
    inviteMsg.value = { ok: false, text: e.response?.data?.detail || 'Failed' }
  }
}

async function saveSettings() {
  await api.patch(`/rooms/${props.room.id}`, { name: editName.value, description: editDesc.value })
  emit('close')
}

async function deleteRoom() {
  if (confirm(`Delete #${props.room.name}? This is permanent.`)) {
    await api.delete(`/rooms/${props.room.id}`)
    emit('deleted')
    emit('close')
  }
}

onMounted(loadBans)
</script>

<style scoped>
.tab-btn {
  padding: 6px 12px;
  background: var(--bg3);
  color: var(--text2);
  font-size: 13px;
}
.tab-btn.active { background: var(--accent); color: #fff; }
.tab-content { margin-top: 12px; }
.ban-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 0;
  border-bottom: 1px solid var(--border);
}
.ban-row span:first-child { flex: 1; }
.field { display: flex; flex-direction: column; gap: 4px; }
.field label { font-size: 13px; color: var(--text2); }
</style>
