import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '@/api/client'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const loading = ref(false)

  async function init() {
    const token = localStorage.getItem('access_token')
    if (!token) return
    try {
      const { data } = await api.get('/auth/me')
      user.value = data
    } catch {
      user.value = null
    }
  }

  async function login(email, password) {
    const { data } = await api.post('/auth/login', { email, password })
    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('refresh_token', data.refresh_token)
    const me = await api.get('/auth/me')
    user.value = me.data
  }

  async function register(username, email, password) {
    await api.post('/auth/register', { username, email, password })
    await login(email, password)
  }

  async function logout() {
    const refresh = localStorage.getItem('refresh_token')
    if (refresh) {
      try { await api.post('/auth/logout', { refresh_token: refresh }) } catch {}
    }
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    user.value = null
  }

  return { user, loading, init, login, register, logout }
})
