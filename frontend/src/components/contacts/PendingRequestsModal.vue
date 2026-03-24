<template>
  <div class="modal-overlay" @click.self="$emit('close')">
    <div class="modal">
      <h2>Pending Friend Requests</h2>
      <div v-if="!friendsStore.pendingRequests.length" class="text-muted text-sm mt-2">
        No pending requests.
      </div>
      <div
        v-for="req in friendsStore.pendingRequests"
        :key="req.id"
        class="request-row mt-2"
      >
        <div class="flex-col gap-1 flex-1">
          <span class="text-sm font-bold">{{ req.sender.username }}</span>
          <span v-if="req.message" class="text-xs text-muted">{{ req.message }}</span>
        </div>
        <div class="flex gap-2">
          <button class="btn-primary btn-sm" @click="accept(req.id)">Accept</button>
          <button class="btn-secondary btn-sm" @click="reject(req.id)">Reject</button>
        </div>
      </div>
      <button class="btn-secondary w-full mt-3" @click="$emit('close')">Close</button>
    </div>
  </div>
</template>

<script setup>
import { useFriendsStore } from '@/stores/friends'

const emit = defineEmits(['close'])
const friendsStore = useFriendsStore()

async function accept(id) {
  await friendsStore.acceptRequest(id)
}

async function reject(id) {
  await friendsStore.rejectRequest(id)
}
</script>

<style scoped>
.request-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px solid var(--border);
}
</style>
