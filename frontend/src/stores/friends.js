import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '@/api/client'

export const useFriendsStore = defineStore('friends', () => {
  const friends = ref([])
  const pendingRequests = ref([])
  const presence = ref({})

  async function fetchFriends() {
    const { data } = await api.get('/friends')
    friends.value = data
  }

  async function fetchPending() {
    const { data } = await api.get('/friends/requests/pending')
    pendingRequests.value = data
  }

  async function sendRequest(username, message = '') {
    await api.post('/friends/requests', { receiver_username: username, message })
  }

  async function acceptRequest(id) {
    await api.post(`/friends/requests/${id}/accept`)
    await fetchFriends()
    await fetchPending()
  }

  async function rejectRequest(id) {
    await api.post(`/friends/requests/${id}/reject`)
    await fetchPending()
  }

  async function removeFriend(username) {
    await api.delete(`/friends/${username}`)
    await fetchFriends()
  }

  async function banUser(username) {
    await api.post(`/friends/ban/${username}`)
    await fetchFriends()
  }

  function setPresence(userId, status) {
    presence.value[userId] = status
    const f = friends.value.find(u => u.id === userId)
    if (f) f.presence = status
  }

  return {
    friends, pendingRequests, presence,
    fetchFriends, fetchPending,
    sendRequest, acceptRequest, rejectRequest,
    removeFriend, banUser, setPresence,
  }
})
