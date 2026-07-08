import { createRouter, createWebHistory } from 'vue-router'
import Login from '@/views/Login.vue'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: Login,
    meta: { requiresAuth: false }
  },
  {
    path: '/',
    redirect: '/dashboard'
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('@/views/Dashboard.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/alarm-history',
    name: 'AlarmHistory',
    component: () => import('@/views/AlarmHistory.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/perimeter-config',
    name: 'PerimeterConfig',
    component: () => import('@/views/PerimeterConfig.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/face-access',
    name: 'FaceAccess',
    component: () => import('@/views/FaceAccess.vue'),
    meta: { requiresAuth: true }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  
  if (to.meta.requiresAuth && !token) {
    next('/login')
  } else if (to.path === '/login' && token) {
    next('/dashboard')
  } else {
    next()
  }
})

export default router
