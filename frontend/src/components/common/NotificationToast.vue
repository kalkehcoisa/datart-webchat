<template>
  <div class="toast-container">
    <transition-group name="toast">
      <div
        v-for="n in notifications"
        :key="n.id"
        class="toast"
        :class="{ 'toast-action': n.roomId }"
      >
        <span class="toast-text">{{ n.text }}</span>
        <div v-if="n.roomId" class="toast-actions">
          <button class="btn-primary btn-sm" @click="acceptInvite(n)">Accept</button>
          <button class="btn-ghost btn-sm" @click="dismiss(n.id)">✕</button>
        </div>
        <button v-else class="toast-close" @click="dismiss(n.id)">✕</button>
      </div>
    </transition-group>
  </div>
</template>

<script setup>
import { inject } from 'vue'
import { useRouter } from 'vue-router'
import { useChatStore } from '@/stores/chat'
import api from '@/api/client'

const notifications = inject('notifications')
const router = useRouter()
const chatStore = useChatStore()

function dismiss(id) {
  const idx = notifications.value.findIndex(n => n.id === id)
  if (idx !== -1) notifications.value.splice(idx, 1)
}

async function acceptInvite(n) {
  try {
    await api.post(`/rooms/${n.roomId}/accept-invite`)
    await chatStore.fetchMyRooms()
    router.push(`/rooms/${n.roomId}`)
  } catch (e) {
    console.error('Failed to accept invite', e)
  } finally {
    dismiss(n.id)
  }
}

function scheduleAutoDismiss(n) {
  if (!n.roomId) {
    setTimeout(() => dismiss(n.id), 5000)
  }
}

import { watch } from 'vue'
watch(notifications, (list) => {
  if (!list.length) return
  const last = list[list.length - 1]
  scheduleAutoDismiss(last)
}, { deep: true })
</script>

<style scoped>
.toast-container {
  position: fixed;
  bottom: 20px;
  right: 20px;
  z-index: 2000;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.toast {
  background: var(--bg3);
  border: 1px solid var(--border);
  border-left: 3px solid var(--accent);
  padding: 10px 16px;
  border-radius: var(--radius);
  font-size: 14px;
  max-width: 320px;
  box-shadow: var(--shadow);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.toast-text { flex: 1; }
.toast-actions { display: flex; gap: 6px; flex-shrink: 0; }
.toast-close {
  background: none;
  border: none;
  color: var(--text2);
  cursor: pointer;
  padding: 0 2px;
  font-size: 14px;
  flex-shrink: 0;
}
.toast-enter-active, .toast-leave-active { transition: all 0.3s; }
.toast-enter-from { opacity: 0; transform: translateX(20px); }
.toast-leave-to { opacity: 0; transform: translateX(20px); }
</style>
