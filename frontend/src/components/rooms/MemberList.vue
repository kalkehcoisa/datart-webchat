<template>
  <div class="member-list">
    <div class="member-list-header">Members ({{ members.length }})</div>
    <div
      v-for="m in sortedMembers"
      :key="m.user_id"
      class="member-item"
    >
      <span class="presence-dot" :class="m.presence"></span>
      <span class="member-name truncate">{{ m.username }}</span>
      <span v-if="m.user_id === ownerId" class="role-badge owner">owner</span>
      <span v-else-if="m.is_admin" class="role-badge admin">admin</span>

      <div v-if="isAdmin && m.user_id !== ownerId && m.user_id !== authUserId" class="member-menu">
        <button class="btn-ghost btn-sm" @click="toggleMenu(m.user_id)">⋮</button>
        <div v-if="menuOpen === m.user_id" class="dropdown">
          <button @click="grantAdmin(m)" v-if="isOwner && !m.is_admin">Make admin</button>
          <button @click="revokeAdmin(m)" v-if="isOwner && m.is_admin">Remove admin</button>
          <button @click="banMember(m)" class="danger">Ban & remove</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import api from '@/api/client'

const props = defineProps({
  roomId: String,
  members: Array,
  isAdmin: Boolean,
  isOwner: Boolean,
  ownerId: String,
})
const emit = defineEmits(['refresh'])

const auth = useAuthStore()
const authUserId = computed(() => auth.user?.id)
const menuOpen = ref(null)

const sortedMembers = computed(() => {
  return [...props.members].sort((a, b) => {
    if (a.user_id === props.ownerId) return -1
    if (b.user_id === props.ownerId) return 1
    if (a.is_admin && !b.is_admin) return -1
    if (!a.is_admin && b.is_admin) return 1
    const order = { online: 0, afk: 1, offline: 2 }
    return (order[a.presence] || 2) - (order[b.presence] || 2)
  })
})

function toggleMenu(id) {
  menuOpen.value = menuOpen.value === id ? null : id
}

async function grantAdmin(m) {
  await api.post(`/rooms/${props.roomId}/members/${m.user_id}/admin`)
  menuOpen.value = null
  emit('refresh')
}

async function revokeAdmin(m) {
  await api.delete(`/rooms/${props.roomId}/members/${m.user_id}/admin`)
  menuOpen.value = null
  emit('refresh')
}

async function banMember(m) {
  if (confirm(`Ban ${m.username} from this room?`)) {
    await api.post(`/rooms/${props.roomId}/members/${m.user_id}/ban`)
    menuOpen.value = null
    emit('refresh')
  }
}
</script>

<style scoped>
.member-list { padding: 8px 0; }
.member-list-header {
  padding: 6px 12px;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  color: var(--text2);
  letter-spacing: 0.5px;
}
.member-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  font-size: 13px;
  position: relative;
}
.member-name { flex: 1; }
.role-badge {
  font-size: 10px;
  padding: 1px 5px;
  border-radius: 4px;
  font-weight: 700;
}
.role-badge.owner { background: var(--accent); color: #fff; }
.role-badge.admin { background: var(--accent2); color: #fff; }
.member-menu { position: relative; }
.dropdown {
  position: absolute;
  right: 0;
  top: 100%;
  background: var(--bg3);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  z-index: 100;
  min-width: 140px;
  box-shadow: var(--shadow);
}
.dropdown button {
  display: block;
  width: 100%;
  text-align: left;
  padding: 8px 12px;
  font-size: 13px;
  background: none;
  color: var(--text);
  border-radius: 0;
}
.dropdown button:hover { background: var(--bg2); }
.dropdown button.danger { color: var(--danger); }
</style>
