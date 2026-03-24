import { defineStore } from 'pinia'
import { ref, reactive } from 'vue'
import api from '@/api/client'

export const useChatStore = defineStore('chat', () => {
  const rooms = ref([])
  const myRooms = ref([])
  const activeRoomId = ref(null)
  const activeChatId = ref(null)
  const messages = reactive({})
  const personalChats = ref([])
  const unread = reactive({})

  async function fetchMyRooms() {
    const { data } = await api.get('/rooms/my')
    myRooms.value = data
  }

  async function fetchPublicRooms(search = '') {
    const { data } = await api.get('/rooms', { params: { search } })
    rooms.value = data
  }

  async function fetchPersonalChats() {
    const { data } = await api.get('/chats')
    personalChats.value = data
  }

  async function loadRoomMessages(roomId, before = null) {
    const params = { limit: 50 }
    if (before) params.before = before
    const { data } = await api.get(`/rooms/${roomId}/messages`, { params })
    if (!messages[roomId]) messages[roomId] = []
    if (before) {
      messages[roomId] = [...data, ...messages[roomId]]
    } else {
      messages[roomId] = data
    }
    return data
  }

  async function loadChatMessages(chatId, before = null) {
    const params = { limit: 50 }
    if (before) params.before = before
    const { data } = await api.get(`/chats/${chatId}/messages`, { params })
    if (!messages[chatId]) messages[chatId] = []
    if (before) {
      messages[chatId] = [...data, ...messages[chatId]]
    } else {
      messages[chatId] = data
    }
    return data
  }

  function appendMessage(contextId, msg) {
    if (!messages[contextId]) messages[contextId] = []
    const exists = messages[contextId].find(m => m.id === msg.id)
    if (!exists) messages[contextId].push(msg)
  }

  function updateMessage(contextId, updated) {
    if (!messages[contextId]) return
    const idx = messages[contextId].findIndex(m => m.id === updated.id)
    if (idx !== -1) messages[contextId][idx] = updated
  }

  function markDeleted(contextId, messageId) {
    if (!messages[contextId]) return
    const msg = messages[contextId].find(m => m.id === messageId)
    if (msg) { msg.is_deleted = true; msg.content = null }
  }

  function incrementUnread(contextId) {
    unread[contextId] = (unread[contextId] || 0) + 1
  }

  function clearUnread(contextId) {
    unread[contextId] = 0
  }

  return {
    rooms, myRooms, activeRoomId, activeChatId,
    messages, personalChats, unread,
    fetchMyRooms, fetchPublicRooms, fetchPersonalChats,
    loadRoomMessages, loadChatMessages,
    appendMessage, updateMessage, markDeleted,
    incrementUnread, clearUnread,
  }
})
