<template>
  <div class="room-view">
    <div class="room-main">
      <div class="room-topbar">
        <span class="room-title"># {{ room?.name }}</span>
        <span class="text-muted text-sm">{{ room?.description }}</span>
        <div class="flex gap-2 items-center" style="margin-left:auto">
          <button v-if="isOwner" class="btn-ghost btn-sm" @click="showAdmin = true">⚙ Admin</button>
          <button v-if="!isOwner" class="btn-ghost btn-sm" @click="confirmLeave">Leave</button>
          <button class="btn-ghost btn-sm" @click="membersOpen = !membersOpen">
            👥 {{ members.length }}
          </button>
        </div>
      </div>

      <MessageList
        :context-id="roomId"
        :messages="chatStore.messages[roomId] || []"
        :is-admin="isAdmin"
        @load-more="loadMore"
        @delete-msg="deleteMsg"
      />

      <MessageInput
        :context-id="roomId"
        context-type="room"
        @sent="onSent"
      />
    </div>

    <transition name="slide">
      <aside v-if="membersOpen" class="members-panel">
        <MemberList
          :room-id="roomId"
          :members="members"
          :is-admin="isAdmin"
          :is-owner="isOwner"
          :owner-id="room?.owner_id"
          @refresh="loadMembers"
        />
      </aside>
    </transition>

    <RoomAdminModal
      v-if="showAdmin"
      :room="room"
      @close="showAdmin = false"
      @deleted="onDeleted"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useChatStore } from '@/stores/chat'
import { useSocketStore } from '@/stores/socket'
import api from '@/api/client'
import MessageList from '@/components/chat/MessageList.vue'
import MessageInput from '@/components/chat/MessageInput.vue'
import MemberList from '@/components/rooms/MemberList.vue'
import RoomAdminModal from '@/components/rooms/RoomAdminModal.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const chatStore = useChatStore()
const socket = useSocketStore()

const roomId = computed(() => route.params.id)
const room = ref(null)
const members = ref([])
const membersOpen = ref(true)
const showAdmin = ref(false)

const isAdmin = computed(() => members.value.find(m => m.user_id === auth.user?.id)?.is_admin || false)
const isOwner = computed(() => room.value?.owner_id === auth.user?.id)

async function load() {
  try {
    const [roomRes] = await Promise.all([
      api.get(`/rooms/${roomId.value}`),
      chatStore.loadRoomMessages(roomId.value),
    ])
    room.value = roomRes.data
    await loadMembers()
    chatStore.clearUnread(roomId.value)
    socket.emit('join_room', { room_id: roomId.value })
    chatStore.activeRoomId = roomId.value
    chatStore.activeChatId = null
  } catch {
    router.push('/rooms')
  }
}

async function loadMembers() {
  const { data } = await api.get(`/rooms/${roomId.value}/members`)
  members.value = data
}

async function loadMore(beforeId, resolve) {
  await chatStore.loadRoomMessages(roomId.value, beforeId)
  resolve?.()
}

async function deleteMsg(msgId) {
  await api.delete(`/messages/${msgId}`)
}

async function confirmLeave() {
  if (confirm(`Leave #${room.value?.name}?`)) {
    await api.post(`/rooms/${roomId.value}/leave`)
    socket.emit('leave_room', { room_id: roomId.value })
    await chatStore.fetchMyRooms()
    router.push('/rooms')
  }
}

function onSent(msg) {
  chatStore.appendMessage(roomId.value, msg)
}

function onDeleted() {
  chatStore.fetchMyRooms()
  router.push('/rooms')
}

watch(roomId, load)
onMounted(load)
onUnmounted(() => { chatStore.activeRoomId = null })
</script>

<style scoped>
.room-view { display: flex; height: 100%; overflow: hidden; }
.room-main { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.room-topbar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
  background: var(--bg2);
}
.room-title { font-weight: 700; font-size: 16px; }
.members-panel {
  width: 220px;
  border-left: 1px solid var(--border);
  overflow-y: auto;
  background: var(--bg2);
  flex-shrink: 0;
}
.slide-enter-active, .slide-leave-active { transition: width 0.2s; }
.slide-enter-from, .slide-leave-to { width: 0; }
</style>
