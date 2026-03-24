<template>
  <div class="input-area">
    <div v-if="replyTo" class="reply-bar">
      <span>↩ Replying to <strong>{{ replyTo.author.username }}</strong>: {{ replyTo.content?.slice(0, 60) }}</span>
      <button class="btn-ghost btn-sm" @click="replyTo = null">✕</button>
    </div>

    <div class="input-row">
      <label class="attach-btn" title="Attach file">
        📎
        <input type="file" style="display:none" @change="onFileSelected" />
      </label>

      <textarea
        ref="inputEl"
        v-model="text"
        class="msg-input"
        :placeholder="placeholder"
        rows="1"
        @keydown.enter.exact.prevent="send"
        @keydown.enter.shift.exact="text += '\n'"
        @input="autoResize"
        @keydown="emitTyping"
      />

      <button class="btn-primary send-btn" :disabled="!canSend" @click="send">Send</button>
    </div>

    <div v-if="pendingFile" class="file-preview">
      <span class="text-sm">📎 {{ pendingFile.name }}</span>
      <input v-model="fileComment" placeholder="Optional comment" style="flex:1" />
      <button class="btn-ghost btn-sm" @click="pendingFile = null">✕</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import api from '@/api/client'
import { useSocketStore } from '@/stores/socket'

const props = defineProps({
  contextId: String,
  contextType: String,
})
const emit = defineEmits(['sent'])

const socket = useSocketStore()
const text = ref('')
const replyTo = ref(null)
const pendingFile = ref(null)
const fileComment = ref('')
const inputEl = ref(null)
let typingTimeout = null

const placeholder = computed(() =>
  props.contextType === 'room' ? 'Message the room…' : 'Message…'
)

const canSend = computed(() => text.value.trim() || pendingFile.value)

function autoResize() {
  const el = inputEl.value
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 160) + 'px'
}

function onFileSelected(e) {
  pendingFile.value = e.target.files[0] || null
  e.target.value = ''
}

function emitTyping() {
  clearTimeout(typingTimeout)
  if (props.contextType === 'room') {
    socket.emit('typing', { room_id: props.contextId })
  } else {
    socket.emit('typing', { chat_id: props.contextId })
  }
  typingTimeout = setTimeout(() => {}, 2000)
}

async function send() {
  if (!canSend.value) return
  const content = text.value.trim() || null
  const reply_to_id = replyTo.value?.id || null

  const url = props.contextType === 'room'
    ? `/rooms/${props.contextId}/messages`
    : `/chats/${props.contextId}/messages`

  const { data: msg } = await api.post(url, { content, reply_to_id })

  if (pendingFile.value) {
    const form = new FormData()
    form.append('message_id', msg.id)
    form.append('file', pendingFile.value)
    if (fileComment.value) form.append('comment', fileComment.value)
    try {
      await api.post('/upload', form, { headers: { 'Content-Type': 'multipart/form-data' } })
    } catch {}
    pendingFile.value = null
    fileComment.value = ''
  }

  text.value = ''
  replyTo.value = null
  inputEl.value.style.height = 'auto'
  emit('sent', msg)
}

defineExpose({ setReply: (msg) => { replyTo.value = msg } })
</script>

<style scoped>
.input-area {
  border-top: 1px solid var(--border);
  padding: 10px 16px;
  background: var(--bg2);
  flex-shrink: 0;
}
.reply-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  color: var(--text2);
  margin-bottom: 6px;
  padding: 4px 8px;
  background: var(--bg3);
  border-radius: 4px;
}
.input-row { display: flex; align-items: flex-end; gap: 8px; }
.attach-btn {
  font-size: 18px;
  cursor: pointer;
  padding: 4px;
  color: var(--text2);
  transition: color 0.15s;
  line-height: 1;
  align-self: flex-end;
  padding-bottom: 6px;
}
.attach-btn:hover { color: var(--text); }
.msg-input {
  flex: 1;
  resize: none;
  min-height: 38px;
  max-height: 160px;
  line-height: 1.5;
  overflow-y: auto;
}
.send-btn { align-self: flex-end; height: 36px; padding: 0 16px; }
.file-preview {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  padding: 6px 8px;
  background: var(--bg3);
  border-radius: 4px;
}
</style>
