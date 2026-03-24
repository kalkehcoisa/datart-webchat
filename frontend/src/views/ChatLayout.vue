<template>
  <div class="layout">
    <header class="topbar">
      <span class="logo">💬 WebChat</span>
      <nav class="flex gap-2 items-center">
        <router-link to="/rooms" class="nav-link">Rooms</router-link>
        <span class="text-muted">|</span>
        <router-link to="/settings" class="nav-link">Settings</router-link>
        <span class="text-muted">{{ auth.user?.username }}</span>
        <span class="presence-dot" :class="auth.user?.presence || 'offline'"></span>
        <button class="btn-ghost btn-sm" @click="doLogout">Logout</button>
      </nav>
    </header>

    <div class="main">
      <aside class="sidebar">
        <SidebarPanel />
      </aside>
      <div class="content">
        <router-view />
      </div>
    </div>

    <NotificationToast />
  </div>
</template>

<script setup>
import { onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useSocketStore } from '@/stores/socket'
import { useChatStore } from '@/stores/chat'
import { useFriendsStore } from '@/stores/friends'
import SidebarPanel from '@/components/chat/SidebarPanel.vue'
import NotificationToast from '@/components/common/NotificationToast.vue'

const auth = useAuthStore()
const socket = useSocketStore()
const chatStore = useChatStore()
const friendsStore = useFriendsStore()
const router = useRouter()

onMounted(async () => {
  const token = localStorage.getItem('access_token')
  if (token) socket.connect(token)

  await Promise.all([
    chatStore.fetchMyRooms(),
    chatStore.fetchPersonalChats(),
    friendsStore.fetchFriends(),
    friendsStore.fetchPending(),
  ])

  socket.on('presence', msg => {
    friendsStore.setPresence(msg.user_id, msg.status)
  })

  socket.on('message', msg => {
    const ctxId = msg.room_id || msg.personal_chat_id
    if (ctxId !== chatStore.activeRoomId && ctxId !== chatStore.activeChatId) {
      chatStore.incrementUnread(ctxId)
    }
    chatStore.appendMessage(ctxId, msg)
  })

  socket.on('message_edited', msg => {
    const ctxId = msg.room_id || msg.personal_chat_id
    chatStore.updateMessage(ctxId, msg)
  })

  socket.on('message_deleted', msg => {
    for (const key of Object.keys(chatStore.messages)) {
      chatStore.markDeleted(key, msg.message_id)
    }
  })

  socket.on('member_joined', async () => { await chatStore.fetchMyRooms() })
  socket.on('member_left', async () => { await chatStore.fetchMyRooms() })
  socket.on('room_deleted', async () => { await chatStore.fetchMyRooms() })

  socket.on('room_invitation', async (msg) => {
    notifications.value.push({ id: Date.now(), text: `${msg.inviter} invited you to #${msg.room_name}`, roomId: msg.room_id })
    await chatStore.fetchMyRooms()
  })

  socket.on('friend_request', async (msg) => {
    notifications.value.push({ id: Date.now(), text: `Friend request from ${msg.from}` })
    await friendsStore.fetchPending()
  })

  socket.on('friend_accepted', async (msg) => {
    notifications.value.push({ id: Date.now(), text: `${msg.by} accepted your friend request` })
    await friendsStore.fetchFriends()
  })
})

onUnmounted(() => socket.disconnect())

async function doLogout() {
  socket.disconnect()
  await auth.logout()
  router.push('/login')
}

import { ref, provide } from 'vue'
const notifications = ref([])
provide('notifications', notifications)
</script>

<style scoped>
.layout { display: flex; flex-direction: column; height: 100vh; }
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  height: 48px;
  background: var(--bg2);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}
.logo { font-weight: 700; font-size: 18px; color: var(--accent); }
.nav-link { color: var(--text2); font-size: 14px; }
.nav-link:hover { color: var(--text); }
.main { display: flex; flex: 1; overflow: hidden; }
.sidebar { width: 280px; background: var(--bg2); border-right: 1px solid var(--border); overflow-y: auto; flex-shrink: 0; }
.content { flex: 1; overflow: hidden; display: flex; flex-direction: column; }
</style>
