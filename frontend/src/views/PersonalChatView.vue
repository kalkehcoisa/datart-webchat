<template>
  <div class="chat-view">
    <div class="chat-topbar">
      <span class="presence-dot" :class="otherUser?.presence || 'offline'"></span>
      <span class="chat-title">{{ otherUser?.username }}</span>
      <div style="margin-left:auto" class="flex gap-2">
        <button v-if="!frozen" class="btn-ghost btn-sm" @click="showBan = true">🚫 Block</button>
        <span v-else class="frozen-label">🔒 Conversation blocked</span>
      </div>
    </div>

    <MessageList
      :context-id="chatId"
      :messages="chatStore.messages[chatId] || []"
      :is-admin="false"
      @load-more="loadMore"
    />

    <MessageInput
      v-if="!frozen"
      :context-id="chatId"
      context-type="chat"
      @sent="onSent"
    />
    <div v-else class="frozen-bar">
      You can no longer send messages in this conversation.
    </div>

    <div v-if="showBan" class="modal-overlay" @click.self="showBan = false">
      <div class="modal">
        <h2>Block {{ otherUser?.username }}?</h2>
        <p class="text-sm text-muted mt-2">
          This will remove the friendship and prevent further contact.
          The conversation history will remain visible but become read-only.
        </p>
        <div class="flex gap-2 mt-3">
          <button class="btn-danger" @click="doBan">Block</button>
          <button class="btn-secondary" @click="showBan = false">Cancel</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useChatStore } from '@/stores/chat'
import { useSocketStore } from '@/stores/socket'
import { useFriendsStore } from '@/stores/friends'
import api from '@/api/client'
import MessageList from '@/components/chat/MessageList.vue'
import MessageInput from '@/components/chat/MessageInput.vue'

const route = useRoute()
const router = useRouter()
const chatStore = useChatStore()
const socket = useSocketStore()
const friendsStore = useFriendsStore()

const chatId = computed(() => route.params.id)
const otherUser = ref(null)
const frozen = ref(false)
const showBan = ref(false)

async function load() {
  const chat = chatStore.personalChats.find(c => c.id === chatId.value)
  otherUser.value = chat?.other_user || null
  frozen.value = chat?.frozen || false
  await chatStore.loadChatMessages(chatId.value)
  chatStore.clearUnread(chatId.value)
  socket.emit('join_chat', { chat_id: chatId.value })
  chatStore.activeChatId = chatId.value
  chatStore.activeRoomId = null
}

async function loadMore(beforeId, resolve) {
  await chatStore.loadChatMessages(chatId.value, beforeId)
  resolve?.()
}

function onSent(msg) {
  chatStore.appendMessage(chatId.value, msg)
}

async function doBan() {
  await friendsStore.banUser(otherUser.value.username)
  showBan.value = false
  await chatStore.fetchPersonalChats()
  frozen.value = true
}

watch(chatId, load)
onMounted(load)
onUnmounted(() => { chatStore.activeChatId = null })
</script>

<style scoped>
.chat-view { display: flex; flex-direction: column; height: 100%; overflow: hidden; }
.chat-topbar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
  background: var(--bg2);
}
.chat-title { font-weight: 700; font-size: 16px; }
.frozen-label { font-size: 12px; color: var(--text2); }
.frozen-bar {
  padding: 12px 16px;
  background: var(--bg2);
  border-top: 1px solid var(--border);
  color: var(--text2);
  font-size: 13px;
  text-align: center;
  flex-shrink: 0;
}
</style>
