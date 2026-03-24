<template>
  <div class="rooms-view">
    <div class="rooms-header">
      <h2>Public Rooms</h2>
      <div class="flex gap-2">
        <input v-model="search" placeholder="Search rooms…" style="width:220px" @input="doSearch" />
        <button class="btn-primary" @click="showCreate = true">+ New Room</button>
      </div>
    </div>

    <div class="room-list">
      <div v-if="loading" class="empty">Loading…</div>
      <div v-else-if="!rooms.length" class="empty">No public rooms found.</div>
      <div
        v-for="room in rooms"
        :key="room.id"
        class="room-card card"
      >
        <div class="room-info">
          <span class="room-name"># {{ room.name }}</span>
          <span class="text-muted text-sm">{{ room.member_count }} members</span>
        </div>
        <p v-if="room.description" class="room-desc text-sm text-muted">{{ room.description }}</p>
        <div class="flex gap-2 mt-2">
          <button
            v-if="isMember(room.id)"
            class="btn-secondary btn-sm"
            @click="goToRoom(room.id)"
          >Open</button>
          <button
            v-else
            class="btn-primary btn-sm"
            @click="joinRoom(room)"
          >Join</button>
        </div>
      </div>
    </div>

    <CreateRoomModal v-if="showCreate" @close="showCreate = false" @created="onCreated" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useChatStore } from '@/stores/chat'
import { useSocketStore } from '@/stores/socket'
import api from '@/api/client'
import CreateRoomModal from '@/components/rooms/CreateRoomModal.vue'

const chatStore = useChatStore()
const socket = useSocketStore()
const router = useRouter()
const search = ref('')
const rooms = ref([])
const loading = ref(false)
const showCreate = ref(false)

const isMember = (id) => chatStore.myRooms.some(r => r.id === id)

async function doSearch() {
  loading.value = true
  await chatStore.fetchPublicRooms(search.value)
  rooms.value = chatStore.rooms
  loading.value = false
}

async function joinRoom(room) {
  await api.post(`/rooms/${room.id}/join`)
  await chatStore.fetchMyRooms()
  socket.emit('join_room', { room_id: room.id })
  router.push(`/rooms/${room.id}`)
}

function goToRoom(id) {
  router.push(`/rooms/${id}`)
}

async function onCreated(room) {
  showCreate.value = false
  await chatStore.fetchMyRooms()
  socket.emit('join_room', { room_id: room.id })
  router.push(`/rooms/${room.id}`)
}

onMounted(doSearch)
</script>

<style scoped>
.rooms-view { padding: 24px; overflow-y: auto; height: 100%; }
.rooms-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; }
h2 { font-size: 20px; }
.room-list { display: flex; flex-direction: column; gap: 10px; max-width: 600px; }
.room-card { display: flex; flex-direction: column; gap: 4px; }
.room-info { display: flex; align-items: center; justify-content: space-between; }
.room-name { font-weight: 600; }
.room-desc { color: var(--text2); }
.empty { color: var(--text2); padding: 24px 0; }
</style>
