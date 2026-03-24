<template>
  <div class="sidebar-panel">
    <section class="section">
      <div class="section-header" @click="roomsOpen = !roomsOpen">
        <span>Rooms</span>
        <span class="chevron">{{ roomsOpen ? '▾' : '▸' }}</span>
      </div>
      <div v-if="roomsOpen" class="section-body">
        <router-link
          v-for="room in chatStore.myRooms"
          :key="room.id"
          :to="`/rooms/${room.id}`"
          class="item"
          :class="{ active: route.params.id === room.id }"
          @click="chatStore.clearUnread(room.id)"
        >
          <span class="item-name truncate"># {{ room.name }}</span>
          <span v-if="chatStore.unread[room.id]" class="badge">{{ chatStore.unread[room.id] }}</span>
        </router-link>
        <router-link to="/rooms" class="item browse">+ Browse rooms</router-link>
      </div>
    </section>

    <section class="section">
      <div class="section-header" @click="dmsOpen = !dmsOpen">
        <span>Direct Messages</span>
        <span class="chevron">{{ dmsOpen ? '▾' : '▸' }}</span>
      </div>
      <div v-if="dmsOpen" class="section-body">
        <router-link
          v-for="chat in chatStore.personalChats"
          :key="chat.id"
          :to="`/chats/${chat.id}`"
          class="item"
          :class="{ active: route.params.id === chat.id }"
          @click="chatStore.clearUnread(chat.id)"
        >
          <span class="presence-dot" :class="chat.other_user.presence"></span>
          <span class="item-name truncate">{{ chat.other_user.username }}</span>
          <span v-if="chatStore.unread[chat.id]" class="badge">{{ chatStore.unread[chat.id] }}</span>
        </router-link>
      </div>
    </section>

    <section class="section">
      <div class="section-header" @click="friendsOpen = !friendsOpen">
        <span>Friends</span>
        <span v-if="pendingCount" class="badge">{{ pendingCount }}</span>
        <span class="chevron">{{ friendsOpen ? '▾' : '▸' }}</span>
      </div>
      <div v-if="friendsOpen" class="section-body">
        <div
          v-for="friend in friendsStore.friends"
          :key="friend.id"
          class="item friend-item"
          @click="openDm(friend.username)"
        >
          <span class="presence-dot" :class="friend.presence"></span>
          <span class="item-name truncate">{{ friend.username }}</span>
        </div>
        <button class="item browse" @click="showAddFriend = true">+ Add friend</button>
        <div v-if="pendingCount" class="item browse" @click="showPending = true">
          📩 {{ pendingCount }} pending request{{ pendingCount > 1 ? 's' : '' }}
        </div>
      </div>
    </section>

    <AddFriendModal v-if="showAddFriend" @close="showAddFriend = false" />
    <PendingRequestsModal v-if="showPending" @close="showPending = false" />
  </div>
</template>

<script setup>
import { ref, computed, inject } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useChatStore } from '@/stores/chat'
import { useFriendsStore } from '@/stores/friends'
import api from '@/api/client'
import AddFriendModal from '@/components/contacts/AddFriendModal.vue'
import PendingRequestsModal from '@/components/contacts/PendingRequestsModal.vue'

const notifications = inject('notifications', ref([]))

const chatStore = useChatStore()
const friendsStore = useFriendsStore()
const route = useRoute()
const router = useRouter()

const roomsOpen = ref(true)
const dmsOpen = ref(true)
const friendsOpen = ref(true)
const showAddFriend = ref(false)
const showPending = ref(false)

const pendingCount = computed(() => friendsStore.pendingRequests.length)

async function openDm(username) {
  try {
    const { data } = await api.post(`/chats/${username}`)
    await chatStore.fetchPersonalChats()
    router.push(`/chats/${data.id}`)
  } catch (e) {
    const msg = e.response?.data?.detail || 'Cannot open conversation'
    notifications.value.push({ id: Date.now(), text: msg })
  }
}
</script>

<style scoped>
.sidebar-panel { padding: 8px 0; }
.section { margin-bottom: 4px; }
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 12px;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text2);
  cursor: pointer;
  user-select: none;
}
.section-header:hover { color: var(--text); }
.chevron { font-size: 10px; }
.section-body { padding: 2px 0; }
.item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  font-size: 14px;
  color: var(--text2);
  cursor: pointer;
  text-decoration: none;
  border-radius: 4px;
  margin: 0 4px;
  transition: background 0.1s;
}
.item:hover { background: var(--bg3); color: var(--text); }
.item.active { background: var(--bg3); color: var(--text); }
.item-name { flex: 1; }
.browse { color: var(--accent); font-size: 13px; }
.friend-item { cursor: pointer; }
</style>
