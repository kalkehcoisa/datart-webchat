import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes = [
  { path: '/login', component: () => import('@/views/LoginView.vue'), meta: { guest: true } },
  { path: '/register', component: () => import('@/views/RegisterView.vue'), meta: { guest: true } },
  {
    path: '/',
    component: () => import('@/views/ChatLayout.vue'),
    meta: { auth: true },
    children: [
      { path: '', redirect: '/rooms' },
      { path: 'rooms', component: () => import('@/views/RoomsView.vue') },
      { path: 'rooms/:id', component: () => import('@/views/RoomView.vue') },
      { path: 'chats/:id', component: () => import('@/views/PersonalChatView.vue') },
      { path: 'settings', component: () => import('@/views/SettingsView.vue') },
    ]
  },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!auth.user) await auth.init()
  if (to.meta.auth && !auth.user) return '/login'
  if (to.meta.guest && auth.user) return '/'
})

export default router
