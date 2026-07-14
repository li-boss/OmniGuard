<script setup>
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Bell,
  ChartNoAxesCombined,
  LogOut,
  Map,
  ShieldCheck,
  Users,
  FileText,
  DoorOpen,
} from '@lucide/vue'

import AlarmPopup from './components/AlarmPopup.vue'
import { useAuthStore } from './store/auth'
import { useAlarmsStore } from './store/alarms'
import { connectAlarmStream } from './services/websocket'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const alarms = useAlarmsStore()

const isLogin = computed(() => route.name === 'login')

const navItems = [
  { path: '/dashboard', label: '大盘', icon: ChartNoAxesCombined },
  { path: '/alarms', label: '告警', icon: Bell },
  { path: '/reports', label: '日报', icon: FileText },
  { path: '/access-history', label: '通行', icon: DoorOpen },
  { path: '/zones', label: '围栏', icon: Map },
  { path: '/faces', label: '人脸', icon: Users },
]

function logout() {
  auth.logout()
  router.push('/login')
}

onMounted(async () => {
  if (auth.token) {
    await auth.ensureUser()
    connectAlarmStream(auth.token, (alarm) => alarms.receiveAlarm(alarm))
  }
})
</script>

<template>
  <router-view v-if="isLogin" />

  <div v-else class="app-shell">
    <aside class="sidebar">
      <div class="brand">
        <ShieldCheck />
        <strong>智慧校园安防</strong>
      </div>

      <nav class="nav">
        <router-link
          v-for="item in navItems"
          :key="item.path"
          class="nav-item"
          :to="item.path"
        >
          <component :is="item.icon" />
          <span>{{ item.label }}</span>
        </router-link>
      </nav>

      <button class="logout-button" type="button" @click="logout">
        <LogOut />
        <span>退出</span>
      </button>
    </aside>

    <main class="main">
      <header class="topbar">
        <div>
          <p class="eyebrow">Smart Campus Security</p>
          <h1>{{ route.meta.title }}</h1>
        </div>
        <div class="user-pill">{{ auth.user?.username || 'operator' }}</div>
      </header>

      <router-view />
    </main>

    <AlarmPopup />
  </div>
</template>
