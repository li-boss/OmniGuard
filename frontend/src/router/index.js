import { createRouter, createWebHistory } from 'vue-router'

import AlarmHistory from '../views/AlarmHistory.vue'
import Dashboard from '../views/Dashboard.vue'
import FaceAccess from '../views/FaceAccess.vue'
import Login from '../views/Login.vue'
import PerimeterConfig from '../views/PerimeterConfig.vue'
import DailyReport from '../views/DailyReport.vue'
import AccessHistory from '../views/AccessHistory.vue'
import { useAuthStore } from '../store/auth'

const routes = [
  { path: '/', redirect: '/dashboard' },
  { path: '/login', name: 'login', component: Login, meta: { title: '登录' } },
  {
    path: '/dashboard',
    name: 'dashboard',
    component: Dashboard,
    meta: { title: '实时大盘', requiresAuth: true },
  },
  {
    path: '/alarms',
    name: 'alarms',
    component: AlarmHistory,
    meta: { title: '告警历史', requiresAuth: true },
  },
  {
    path: '/zones',
    name: 'zones',
    component: PerimeterConfig,
    meta: { title: '围栏配置', requiresAuth: true },
  },
  {
    path: '/faces',
    name: 'faces',
    component: FaceAccess,
    meta: { title: '人脸管理', requiresAuth: true },
  },
  {
    path: '/reports',
    name: 'reports',
    component: DailyReport,
    meta: { title: '日报列表', requiresAuth: true },
  },
  {
    path: '/access-history',
    name: 'access-history',
    component: AccessHistory,
    meta: { title: '通行历史', requiresAuth: true },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.requiresAuth && !auth.token) {
    return '/login'
  }
  if (to.name === 'login' && auth.token) {
    return '/dashboard'
  }
  return true
})

export default router
