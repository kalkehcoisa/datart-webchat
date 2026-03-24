<template>
  <div class="auth-wrap">
    <div class="card auth-card">
      <h1>WebChat</h1>
      <h2>Create account</h2>
      <form @submit.prevent="submit">
        <div class="field">
          <label>Username</label>
          <input v-model="username" type="text" required autocomplete="username" />
        </div>
        <div class="field">
          <label>Email</label>
          <input v-model="email" type="email" required autocomplete="email" />
        </div>
        <div class="field">
          <label>Password</label>
          <input v-model="password" type="password" required autocomplete="new-password" />
        </div>
        <p v-if="error" class="error">{{ error }}</p>
        <button class="btn-primary w-full mt-3" :disabled="loading">
          {{ loading ? 'Registering…' : 'Register' }}
        </button>
      </form>
      <p class="mt-2 text-sm text-muted">
        Have an account? <router-link to="/login">Sign in</router-link>
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const username = ref('')
const email = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function submit() {
  error.value = ''
  loading.value = true
  try {
    await auth.register(username.value, email.value, password.value)
    router.push('/')
  } catch (e) {
    error.value = e.response?.data?.detail || 'Registration failed'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-wrap {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
}
.auth-card { width: 360px; }
h1 { font-size: 24px; color: var(--accent); margin-bottom: 4px; }
h2 { font-size: 16px; color: var(--text2); margin-bottom: 20px; }
.field { margin-bottom: 12px; }
.field label { display: block; font-size: 13px; color: var(--text2); margin-bottom: 4px; }
</style>
