<template>
  <div class="modal-overlay" @click.self="$emit('close')">
    <div class="modal">
      <h2>Create Room</h2>
      <div class="field">
        <label>Name</label>
        <input v-model="name" placeholder="room-name" />
      </div>
      <div class="field mt-2">
        <label>Description</label>
        <input v-model="description" placeholder="Optional" />
      </div>
      <div class="field mt-2">
        <label>Visibility</label>
        <select v-model="visibility">
          <option value="public">Public</option>
          <option value="private">Private</option>
        </select>
      </div>
      <p v-if="error" class="error">{{ error }}</p>
      <div class="flex gap-2 mt-3">
        <button class="btn-primary" @click="submit">Create</button>
        <button class="btn-secondary" @click="$emit('close')">Cancel</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import api from '@/api/client'

const emit = defineEmits(['close', 'created'])
const name = ref('')
const description = ref('')
const visibility = ref('public')
const error = ref('')

async function submit() {
  error.value = ''
  try {
    const { data } = await api.post('/rooms', {
      name: name.value,
      description: description.value || null,
      visibility: visibility.value,
    })
    emit('created', data)
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed'
  }
}
</script>

<style scoped>
.field { display: flex; flex-direction: column; gap: 4px; }
.field label { font-size: 13px; color: var(--text2); }
</style>
