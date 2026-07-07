import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from '../views/Dashboard.vue'
import FaceAccess from '../views/FaceAccess.vue'
import PerimeterConfig from '../views/PerimeterConfig.vue'
import AlarmHistory from '../views/AlarmHistory.vue'

const routes = [
  { path: '/', name: 'dashboard', component: Dashboard },
  { path: '/face-access', name: 'face-access', component: FaceAccess },
  { path: '/perimeter-config', name: 'perimeter-config', component: PerimeterConfig },
  { path: '/alarm-history', name: 'alarm-history', component: AlarmHistory }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to) => {
  const publicPages = ['dashboard']
  const token = localStorage.getItem('access_token')
  if (!token && !publicPages.includes(to.name)) {
    return { name: 'dashboard' }
  }
  return true
})

export default router
