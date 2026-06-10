import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/stores/user'

const routes = [
  {
    path: '/',
    name: 'home',
    component: () => import('@/views/Home.vue'),
    meta: { title: 'AI 智能问诊 - 首页' }
  },
  {
    path: '/chat',
    name: 'chat',
    component: () => import('@/views/Chat.vue'),
    meta: { title: '在线问诊' }
  },
  {
    path: '/history',
    name: 'history',
    component: () => import('@/views/History.vue'),
    meta: { title: '问诊记录', auth: true }
  },
  {
    path: '/history/:id',
    name: 'history-detail',
    component: () => import('@/views/Chat.vue'),
    meta: { title: '问诊详情' }
  },
  {
    path: '/knowledge',
    name: 'knowledge',
    component: () => import('@/views/Knowledge.vue'),
    meta: { title: '知识库' }
  },
  {
    path: '/ocr',
    name: 'ocr',
    component: () => import('@/views/ocr/OCR.vue'),
    meta: { title: 'OCR 识别' }
  },
  // ============== 影像分析 ==============
  {
    path: '/imaging',
    name: 'imaging',
    component: () => import('@/views/Imaging/Analysis.vue'),
    meta: { title: 'AI 影像分析', auth: true }
  },
  {
    path: '/imaging/history',
    name: 'imaging-history',
    component: () => import('@/views/Imaging/History.vue'),
    meta: { title: '影像分析历史', auth: true }
  },
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/Login.vue'),
    meta: { title: '登录' }
  },
  // ============== Admin 后台 ==============
  {
    path: '/admin',
    component: () => import('@/views/admin/AdminLayout.vue'),
    meta: { requiresAdmin: true, title: '管理后台' },
    children: [
      { path: '', component: () => import('@/views/admin/Dashboard.vue'), meta: { title: '数据概览' } },
      { path: 'consultations', component: () => import('@/views/admin/Consultations.vue'), meta: { title: '问诊管理' } },
      { path: 'emergency', component: () => import('@/views/admin/Emergency.vue'), meta: { title: '紧急看板' } },
      { path: 'knowledge', component: () => import('@/views/admin/KnowledgeAdmin.vue'), meta: { title: '知识库管理' } },
      { path: 'users', component: () => import('@/views/admin/Users.vue'), meta: { title: '用户管理' } },
      { path: 'imaging', component: () => import('@/views/Imaging/History.vue'), meta: { title: '影像分析管理' } }
    ]
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach(async (to, from, next) => {
  document.title = to.meta.title || 'AI 智能问诊系统'

  // 需登录
  if (to.meta.auth && !localStorage.getItem('token')) {
    return next({ name: 'login', query: { redirect: to.fullPath } })
  }

  // 需管理员
  if (to.matched.some((r) => r.meta.requiresAdmin)) {
    const userStore = useUserStore()
    if (!userStore.token) {
      return next({ name: 'login', query: { redirect: to.fullPath } })
    }
    if (!userStore.profile) {
      await userStore.fetchProfile()
    }
    if (!userStore.profile?.is_admin) {
      // 普通用户跳回首页
      alert('需要管理员权限')
      return next('/')
    }
  }
  next()
})

export default router
