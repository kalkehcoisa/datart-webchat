<template>
  <div class="modal-overlay" @click.self="$emit('close')">
    <div class="modal">
      <h2>Add Friend</h2>
      <div class="flex gap-2 mt-2">
        <input v-model="username" placeholder="Username" @keydown.enter="send" />
        <button class="btn-primary" @click="send">Send</button>
      </div>
      <div class="field mt-2">
        <label>Message (optional)</label>
        <input v-model="message" placeholder="Hey, let's connect!" />
      </div>
      <p v-if="result" :class="result.ok ? 'success' : 'error'">{{ result.text }}</p>
      <button class="btn-secondary w-full mt-3" @click="$emit('close')">Close</button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useFriendsStore } from '@/stores/friends'

const emit = defineEmits(['close'])
const friendsStore = useFriendsStore()
const username = ref('')
const message = ref('')
const result = ref(null)

async function send() {
  result.value = null
  try {
    await friendsStore.sendRequest(username.value, message.value)
    result.value = { ok: true, text: 'Friend request sent!' }
    username.value = ''
    message.value = ''
  } catch (e) {
    result.value = { ok: false, text: e.response?.data?.detail || 'Failed' }
  }
}
</script>

<style scoped>
.field { display: flex; flex-direction: column; gap: 4px; }
.field label { font-size: 13px; color: var(--text2); }
</style>
