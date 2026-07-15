<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { CircleStop, Mic, Play, RefreshCw, Volume2 } from '@lucide/vue'

import {
  getAudioDevices,
  getAudioStatus,
  startAudioDetection,
  stopAudioDetection,
} from '../api/audioDetection'

const devices = ref([])
const selectedDevice = ref(null)
const status = ref({ running: false, last_result: null, thresholds: {} })
const heldResult = ref(null)
const heldUntil = ref(0)
const loading = ref(false)
let timer = null
let requestSequence = 0
let appliedSequence = 0
let lastTriggeredKey = null

const result = computed(() => (
  heldResult.value && Date.now() < heldUntil.value
    ? heldResult.value
    : status.value.last_result
))
const confidence = computed(() => `${(Number(result.value?.confidence || 0) * 100).toFixed(1)}%`)

function applyTriggeredResult(triggeredResult) {
  if (!triggeredResult?.triggered) return

  const key = `${triggeredResult.detected_at || ''}:${triggeredResult.category || ''}`
  if (key === lastTriggeredKey) return
  lastTriggeredKey = key

  const detectedAt = Date.parse(triggeredResult.detected_at)
  const eventAge = Number.isFinite(detectedAt) ? Date.now() - detectedAt : 0
  if (eventAge > 30000) return

  heldResult.value = triggeredResult
  heldUntil.value = Date.now() + Number(status.value.display_hold_seconds || 5) * 1000
}

async function refreshStatus() {
  const sequence = ++requestSequence
  try {
    const response = await getAudioStatus()
    if (sequence < appliedSequence) return
    appliedSequence = sequence
    status.value = response.data
    applyTriggeredResult(response.data.last_triggered_result)
  } catch (error) {
    status.value.last_error = error.response?.data?.message || error.message
  }
}

async function loadDevices() {
  try {
    const response = await getAudioDevices()
    devices.value = response.data.items || []
    status.value.last_error = null
    if (selectedDevice.value === null && devices.value.length) {
      selectedDevice.value = devices.value[0].id
    }
  } catch (error) {
    status.value.last_error = error.response?.data?.message || '无法读取麦克风设备'
  }
}

async function start() {
  loading.value = true
  try {
    const response = await startAudioDetection(selectedDevice.value)
    status.value = response.data
    lastTriggeredKey = response.data.last_triggered_result
      ? `${response.data.last_triggered_result.detected_at || ''}:${response.data.last_triggered_result.category || ''}`
      : null
    heldResult.value = null
    heldUntil.value = 0
    ElMessage.success(response.message)
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '声音检测启动失败')
  } finally {
    loading.value = false
  }
}

async function stop() {
  loading.value = true
  try {
    const response = await stopAudioDetection()
    status.value = response.data
    heldResult.value = null
    heldUntil.value = 0
    ElMessage.success(response.message)
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '声音检测停止失败')
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await Promise.all([refreshStatus(), loadDevices()])
  timer = window.setInterval(refreshStatus, 250)
})

onBeforeUnmount(() => {
  if (timer) window.clearInterval(timer)
})
</script>

<template>
  <section class="audio-monitor">
    <div class="audio-toolbar">
      <div class="device-control">
        <Mic :size="18" />
        <el-select v-model="selectedDevice" placeholder="选择麦克风" :disabled="status.running">
          <el-option
            v-for="device in devices"
            :key="device.id"
            :label="device.name"
            :value="device.id"
          />
        </el-select>
        <el-button :icon="RefreshCw" circle title="刷新设备" :disabled="status.running" @click="loadDevices" />
      </div>

      <div class="audio-actions">
        <el-button type="primary" :icon="Play" :loading="loading" :disabled="status.running || selectedDevice === null" @click="start">启动</el-button>
        <el-button type="danger" :icon="CircleStop" :loading="loading" :disabled="!status.running" @click="stop">停止</el-button>
      </div>
    </div>

    <div class="audio-state-band" :class="{ active: status.running, alert: result?.triggered }">
      <div class="audio-state-icon"><Volume2 /></div>
      <div>
        <span class="status-label">{{ status.running ? '监听中' : '已停止' }}</span>
        <strong>{{ result?.display_name || '等待声音输入' }}</strong>
      </div>
      <div class="confidence-value">
        <span>置信度</span>
        <strong>{{ confidence }}</strong>
      </div>
    </div>

    <el-descriptions :column="2" border>
      <el-descriptions-item label="YAMNet 原始类别">{{ result?.matched_raw_class || result?.raw_class || '-' }}</el-descriptions-item>
      <el-descriptions-item label="检测时间">{{ result?.detected_at || '-' }}</el-descriptions-item>
      <el-descriptions-item label="爆炸声阈值">{{ status.thresholds?.explosion ?? '-' }}</el-descriptions-item>
      <el-descriptions-item label="玻璃破碎阈值">{{ status.thresholds?.glass_break ?? '-' }}</el-descriptions-item>
    </el-descriptions>

    <el-alert v-if="status.last_error" type="error" :title="status.last_error" show-icon :closable="false" />
  </section>
</template>

<style scoped>
.audio-monitor { display: grid; gap: 18px; }
.audio-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.device-control, .audio-actions { display: flex; align-items: center; gap: 10px; }
.device-control .el-select { width: min(420px, 60vw); }
.audio-state-band { display: grid; grid-template-columns: 52px minmax(0, 1fr) auto; align-items: center; gap: 16px; min-height: 118px; padding: 20px 24px; border: 1px solid #d8e0e5; border-radius: 8px; background: #f7f9fa; }
.audio-state-band.active { border-color: #4b8f74; background: #f1f8f5; }
.audio-state-band.alert { border-color: #d94c4c; background: #fff3f3; }
.audio-state-icon { display: grid; width: 48px; height: 48px; place-items: center; border-radius: 8px; color: #fff; background: #314754; }
.audio-state-band strong { display: block; margin-top: 4px; font-size: 24px; letter-spacing: 0; }
.status-label, .confidence-value span { color: #667985; font-size: 13px; }
.confidence-value { min-width: 112px; text-align: right; }
.confidence-value strong { font-variant-numeric: tabular-nums; }
@media (max-width: 720px) {
  .audio-toolbar, .device-control { align-items: stretch; flex-direction: column; }
  .device-control .el-select { width: 100%; }
  .audio-state-band { grid-template-columns: 48px minmax(0, 1fr); }
  .confidence-value { grid-column: 1 / -1; text-align: left; }
}
</style>
