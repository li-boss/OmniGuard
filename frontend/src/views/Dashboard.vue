<script setup>
import { onMounted, ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Bell, Map, Radio, Users } from '@lucide/vue'

import VideoPlayer from '../components/VideoPlayer.vue'
import SoundMonitor from '../components/SoundMonitor.vue'
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

const maxTrendCount = computed(() => {
  if (!summary.value.trend || summary.value.trend.length === 0) return 10
  const maxVal = Math.max(...summary.value.trend.map(t => t.count), 0)
  return Math.max(maxVal, 10)
})

const metrics = [
  { key: 'cameraCount', label: '摄像头', icon: Radio },
  { key: 'zoneCount', label: '围栏', icon: Map },
  { key: 'faceCount', label: '人脸库', icon: Users },
  { key: 'pendingAlarmCount', label: '待处置', icon: Bell },
]

const dialogVisible = ref(false)
const alarmForm = ref({
  severity: 'high',
  alarmType: '围栏入侵告警'
})
const generatingReport = ref(false)

const severityOptions = [
  { value: 'critical', label: '严重告警' },
  { value: 'high', label: '高优先级' },
  { value: 'medium', label: '中优先级' },
  { value: 'low', label: '低优先级' }
]

const alarmTypeOptions = [
  { value: '围栏入侵告警', label: '围栏入侵告警' },
  { value: '陌生人告警', label: '陌生人告警' },
  { value: '异常活动告警', label: '异常活动告警' },
  { value: '跌倒告警', label: '跌倒告警' },
  { value: '火情告警', label: '火情告警' }
]

async function load() {
  loading.value = true
  try {
    const result = await getSummary()
    summary.value = result.data
    await camera.fetchConfig()
  } finally {
    loading.value = false
  }
}

function openSimulateDialog() {
  alarmForm.value = {
    severity: 'high',
    alarmType: '围栏入侵告警'
  }
  dialogVisible.value = true
}

async function generateReport() {
  generatingReport.value = true
  try {
    const token = localStorage.getItem('smart-campus-token')
    console.log('Token:', token ? 'exists' : 'null')
    console.log('Sending request to /api/reports/generate')
    
    const response = await fetch('/api/reports/generate', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({})
    })
    
    console.log('Response status:', response.status)
    const result = await response.json()
    console.log('Response:', result)
    
    if (result.code === 0) {
      ElMessage.success('日报生成成功')
    } else {
      ElMessage.error(result.message || '日报生成失败')
    }
  } catch (error) {
    console.error('Error:', error)
    ElMessage.error('日报生成失败')
  } finally {
    generatingReport.value = false
  }
}

async function submitSimulateAlarm() {
  let alarmType = alarmForm.value.alarmType
  let description = `模拟${alarmForm.value.alarmType}`
  
  if (alarmForm.value.alarmType === '跌倒告警' || alarmForm.value.alarmType === '火情告警') {
    alarmType = '异常活动告警'
    description = `检测到${alarmForm.value.alarmType === '跌倒告警' ? '人员跌倒' : '火情'}，属于异常活动`
  }
  
  await alarms.simulate({
    cameraId: camera.selectedCamera.id,
    title: alarmType,
    severity: alarmForm.value.severity,
    type: alarmType,
    description: description,
    confidence: 0.92,
  })
  ElMessage.success('告警已生成')
  dialogVisible.value = false
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
      <div class="video-grid">
        <VideoPlayer
          v-for="cam in camera.cameras"
          :key="cam.id"
          :id="cam.id"
          :src="cam.streamUrl"
          :title="cam.name"
        />
      </div>

      <section class="panel">
        <div class="section-head">
          <h2>七日趋势</h2>
          <div>
            <el-button @click="generateReport" :loading="generatingReport">生成日报</el-button>
            <el-button type="primary" @click="openSimulateDialog">模拟告警</el-button>
          </div>
        </div>
        <div class="trend-chart">
          <div v-for="item in summary.trend" :key="item.date" class="trend-item">
            <div class="bar" :style="{ height: `${Math.max((item.count / maxTrendCount) * 160, 8)}px` }" />
            <span>{{ item.date.slice(5) }}</span>
          </div>
        </div>
      </section>
    </div>

    <SoundMonitor :cameras="camera.cameras" :default-camera-id="camera.selectedCamera.id" />

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

    <el-dialog v-model="dialogVisible" title="模拟告警" width="400px">
      <el-form :model="alarmForm" label-width="80px">
        <el-form-item label="风险等级">
          <el-select v-model="alarmForm.severity" placeholder="请选择风险等级">
            <el-option
              v-for="item in severityOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="告警类型">
          <el-select v-model="alarmForm.alarmType" placeholder="请选择告警类型">
            <el-option
              v-for="item in alarmTypeOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="submitSimulateAlarm">确定</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>
