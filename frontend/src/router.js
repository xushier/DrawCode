import { createRouter, createWebHistory } from 'vue-router'
import { useApp } from './store'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { public: true, title: '登录' }
  },
  {
    path: '/',
    component: () => import('@/layout/MainLayout.vue'),
    children: [
      { path: '', name: 'dashboard', component: () => import('@/views/DashboardView.vue'), meta: { title: '仪表盘', icon: 'Odometer' } },
      { path: 'data', name: 'data', component: () => import('@/views/DataView.vue'), meta: { title: '图号数据', icon: 'Collection' } },
      { path: 'records', name: 'records', component: () => import('@/views/RecordsView.vue'), meta: { title: '操作记录', icon: 'List', admin: true } },
      { path: 'logs', name: 'logs', component: () => import('@/views/LogsView.vue'), meta: { title: '系统日志', icon: 'Document', admin: true } },
      { path: 'settings', name: 'settings', component: () => import('@/views/SettingsView.vue'), meta: { title: '系统设置', icon: 'Setting', admin: true } }
    ]
  },
  { path: '/:pathMatch(.*)*', redirect: '/' }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach(async to => {
  const store = useApp()
  await store.init()
  if (to.meta.public) {
    if (to.path === '/login' && store.authed) return '/'
    return true
  }
  if (to.meta.admin && !store.authed) return '/login'
  if (!store.authed && !store.guestMode) return '/login'
  return true
})

export default router
