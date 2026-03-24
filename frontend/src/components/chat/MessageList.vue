<template>
  <div class="msg-list" ref="listEl" @scroll="onScroll">
    <div v-if="loadingMore" class="load-more-indicator">Loading…</div>
    <div
      v-for="msg in messages"
      :key="msg.id"
      class="msg"
      :class="{ 'msg-own': msg.author.id === auth.user?.id, deleted: msg.is_deleted }"
    >
      <div class="msg-avatar">{{ msg.author.username[0].toUpperCase() }}</div>
      <div class="msg-body">
        <div class="msg-meta">
          <span class="msg-author">{{ msg.author.username }}</span>
          <span class="msg-time">{{ formatTime(msg.created_at) }}</span>
          <span v-if="msg.edited_at" class="msg-edited text-xs text-muted">(edited)</span>
        </div>

        <div v-if="msg.reply_to && !msg.reply_to.is_deleted" class="reply-quote">
          <span class="reply-author">↩ {{ msg.reply_to.author.username }}</span>
          <span class="reply-text">{{ msg.reply_to.content }}</span>
        </div>

        <p v-if="!msg.is_deleted" class="msg-content">{{ msg.content }}</p>
        <p v-else class="msg-content deleted-text">[ message deleted ]</p>

        <div v-if="msg.attachments?.length" class="attachments">
          <div v-for="att in msg.attachments" :key="att.id" class="attachment">
            <img
              v-if="att.is_image"
              :src="`/api/v1/files/${att.id}`"
              class="attachment-img"
              @error="e => e.target.style.display='none'"
            />
            <a v-else :href="`/api/v1/files/${att.id}`" target="_blank" class="attachment-file">
              📎 {{ att.filename }} ({{ formatSize(att.file_size) }})
            </a>
            <p v-if="att.comment" class="text-xs text-muted">{{ att.comment }}</p>
          </div>
        </div>

        <div class="msg-actions">
          <button class="btn-ghost btn-sm" @click="$emit('reply', msg)" title="Reply">↩</button>
          <button
            v-if="msg.author.id === auth.user?.id && !msg.is_deleted"
            class="btn-ghost btn-sm"
            @click="startEdit(msg)"
          >✏</button>
          <button
            v-if="(msg.author.id === auth.user?.id || isAdmin) && !msg.is_deleted"
            class="btn-ghost btn-sm"
            @click="$emit('delete-msg', msg.id)"
          >🗑</button>
        </div>

        <div v-if="editingId === msg.id" class="edit-form">
          <textarea v-model="editContent" rows="2" class="w-full" />
          <div class="flex gap-2 mt-1">
            <button class="btn-primary btn-sm" @click="submitEdit(msg.id)">Save</button>
            <button class="btn-secondary btn-sm" @click="editingId = null">Cancel</button>
          </div>
        </div>
      </div>
    </div>
    <div ref="bottomEl"></div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import { useAuthStore } from '@/stores/auth'
import api from '@/api/client'

const props = defineProps({
  contextId: String,
  messages: Array,
  isAdmin: Boolean,
})
const emit = defineEmits(['load-more', 'delete-msg', 'reply'])

const auth = useAuthStore()
const listEl = ref(null)
const bottomEl = ref(null)
const loadingMore = ref(false)
const editingId = ref(null)
const editContent = ref('')
let atBottom = true

function onScroll() {
  const el = listEl.value
  atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 60
  if (el.scrollTop < 80 && !loadingMore.value && props.messages.length >= 50) {
    loadMore()
  }
}

async function loadMore() {
  if (!props.messages.length) return
  loadingMore.value = true
  const firstId = props.messages[0]?.id
  const prevHeight = listEl.value.scrollHeight
  await new Promise(resolve => emit('load-more', firstId, resolve))
  await nextTick()
  listEl.value.scrollTop = listEl.value.scrollHeight - prevHeight
  loadingMore.value = false
}

watch(() => props.messages.length, async (n, o) => {
  if (atBottom) {
    await nextTick()
    bottomEl.value?.scrollIntoView({ behavior: 'smooth' })
  }
}, { flush: 'post' })

watch(() => props.contextId, async () => {
  atBottom = true
  await nextTick()
  bottomEl.value?.scrollIntoView()
})

function formatTime(ts) {
  return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes}B`
  if (bytes < 1048576) return `${(bytes/1024).toFixed(1)}KB`
  return `${(bytes/1048576).toFixed(1)}MB`
}

function startEdit(msg) {
  editingId.value = msg.id
  editContent.value = msg.content
}

async function submitEdit(id) {
  await api.patch(`/messages/${id}`, { content: editContent.value })
  editingId.value = null
}
</script>

<style scoped>
.msg-list {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.load-more-indicator { text-align: center; color: var(--text2); font-size: 12px; padding: 8px; }
.msg { display: flex; gap: 10px; padding: 4px 6px; border-radius: 6px; }
.msg:hover { background: rgba(255,255,255,0.03); }
.msg-avatar {
  width: 34px; height: 34px;
  border-radius: 50%;
  background: var(--bg3);
  display: flex; align-items: center; justify-content: center;
  font-weight: 700; font-size: 14px;
  flex-shrink: 0;
}
.msg-body { flex: 1; min-width: 0; }
.msg-meta { display: flex; align-items: baseline; gap: 8px; margin-bottom: 2px; }
.msg-author { font-weight: 600; font-size: 14px; }
.msg-time { font-size: 11px; color: var(--text2); }
.msg-content { font-size: 14px; line-height: 1.5; white-space: pre-wrap; word-break: break-word; }
.deleted-text { color: var(--text2); font-style: italic; }
.reply-quote {
  border-left: 3px solid var(--accent2);
  padding: 2px 8px;
  margin-bottom: 4px;
  font-size: 12px;
  color: var(--text2);
  display: flex; gap: 6px;
}
.reply-author { font-weight: 600; color: var(--accent); }
.reply-text { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 300px; }
.msg-actions { display: none; gap: 2px; margin-top: 2px; }
.msg:hover .msg-actions { display: flex; }
.attachments { display: flex; flex-direction: column; gap: 6px; margin-top: 4px; }
.attachment-img { max-width: 300px; max-height: 200px; border-radius: 6px; cursor: pointer; }
.attachment-file { font-size: 13px; color: var(--accent); }
.edit-form { margin-top: 6px; }
</style>
