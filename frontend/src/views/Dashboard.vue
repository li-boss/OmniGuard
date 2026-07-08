<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Bell, Map, Radio, Users } from '@lucide/vue'

import VideoPlayer from '../components/VideoPlayer.vue'
import { getSummary } from '../api/dashboard'
import { useAlarmsStore } from '../store/alarms'
import { useCameraStore } from '../store/camera'

const alarms = useAlarmsStore()
const camera = useCameraStore()
const loading = ref(false)
const summary = ref({
  cameraCount: 0,
  zoneCount: 0,
  faceCount: 0,
  alarmCount: 0,
  pendingAlarmCount: 0,
  videoFeedUrl: '',
  recentAlarms: [],
  trend: [],
})

const metrics = [
  { key: 'cameraCount', label: '摄像头', icon: Radio },
  { key: 'zoneCount', label: '围栏', icon: Map },
  { key: 'faceCount', label: '人脸库', icon: Users },
  { key: 'pendingAlarmCount', label: '待处置', icon: Bell },
]

async function load() {
  loading.value = true
  try {
    const result = await getSummary()
    summary.value = result.data
  } finally {
    loading.value = false
  }
}

async function simulateAlarm() {
  await alarms.simulate({
    cameraId: camera.selectedCamera.id,
    title: '主入口围栏入侵',
    severity: 'high',
    description: '模拟检测管线触发的告警',
    confidence: 0.92,
  })
  ElMessage.success('告警已生成')
  await load()
}

onMounted(load)
</script>

<template>
  <div class="dashboard-grid" v-loading="loading">
    <section class="metric-grid">
      <article v-for="item in metrics" :key="item.key" class="metric-card">
        <component :is="item.icon" />
        <span>{{ item.label }}</span>
        <strong>{{ summary[item.key] }}</strong>
      </article>
    </section>

    <div class="dashboard-main">
      <VideoPlayer
        :src="summary.videoFeedUrl || camera.selectedCamera.streamUrl"
        :title="camera.selectedCamera.name"
      />

      <section class="panel">
        <div class="section-head">
          <h2>七日趋势</h2>
          <el-button type="primary" @click="simulateAlarm">模拟告警</el-button>
        </div>
        <div class="trend-chart">
          <div v-for="item in summary.trend" :key="item.date" class="trend-item">
            <div class="bar" :style="{ height: `${Math.max(item.count * 24, 8)}px` }" />
            <span>{{ item.date.slice(5) }}</span>
          </div>
        </div>
      </section>
    </div>

    <section class="panel">
      <div class="section-head">
        <h2>最近告警</h2>
      </div>
      <div class="list-stack">
        <article v-for="alarm in summary.recentAlarms" :key="alarm.id" class="list-row">
          <strong>{{ alarm.title }}</strong>
          <span>{{ alarm.severity }} / {{ alarm.status }}</span>
        </article>
        <el-empty v-if="!summary.recentAlarms.length" description="暂无告警" />
      </div>
    </section>
  </div>
</template>
