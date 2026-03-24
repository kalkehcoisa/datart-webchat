import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useSocketStore = defineStore('socket', () => {
  const ws = ref(null)
  const connected = ref(false)
  const handlers = new Map()
  let afkTimer = null
  let reconnectTimer = null

  function on(type, fn) {
    if (!handlers.has(type)) handlers.set(type, new Set())
    handlers.get(type).add(fn)
    return () => handlers.get(type)?.delete(fn)
  }

  function emit(type, data = {}) {
    if (ws.value?.readyState === WebSocket.OPEN) {
      ws.value.send(JSON.stringify({ type, ...data }))
    }
  }

  function connect(token) {
    if (ws.value) ws.value.close()
    const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
    const socket = new WebSocket(`${protocol}://${location.host}/ws?token=${token}`)

    socket.onopen = () => {
      connected.value = true
      clearTimeout(reconnectTimer)
      _startAfkTracking()
    }

    socket.onmessage = ({ data }) => {
      try {
        const msg = JSON.parse(data)
        if (msg.type === 'ping') { emit('pong'); return }
        handlers.get(msg.type)?.forEach(fn => fn(msg))
        handlers.get('*')?.forEach(fn => fn(msg))
      } catch {}
    }

    socket.onclose = () => {
      connected.value = false
      _stopAfkTracking()
      reconnectTimer = setTimeout(() => {
        const t = localStorage.getItem('access_token')
        if (t) connect(t)
      }, 3000)
    }

    ws.value = socket
  }

  function disconnect() {
    clearTimeout(reconnectTimer)
    _stopAfkTracking()
    ws.value?.close()
    ws.value = null
    connected.value = false
  }

  function _startAfkTracking() {
    const reset = () => {
      clearTimeout(afkTimer)
      emit('active')
      afkTimer = setTimeout(() => emit('afk'), 60000)
    }
    ['mousemove', 'keydown', 'click', 'scroll', 'touchstart'].forEach(e => {
      window.addEventListener(e, reset, { passive: true })
    })
    window._afkReset = reset
    reset()
  }

  function _stopAfkTracking() {
    clearTimeout(afkTimer)
    if (window._afkReset) {
      ['mousemove', 'keydown', 'click', 'scroll', 'touchstart'].forEach(e => {
        window.removeEventListener(e, window._afkReset)
      })
      delete window._afkReset
    }
  }

  return { ws, connected, on, emit, connect, disconnect }
})
