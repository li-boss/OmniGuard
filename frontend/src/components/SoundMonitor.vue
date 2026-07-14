<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { Activity, Mic, MicOff } from '@lucide/vue'
import { ElMessage } from 'element-plus'

import { analyzeAudioChunk, getAudioStatus } from '../api/audio'
import { MicrophoneChunkRecorder } from '../services/microphone'

const props = defineProps({
  cameras: { type: Array, default: () => [] },
  defaultCameraId: { type: String, default: 'cam-1' },
})

const selectedCameraId = ref(props.defaultCameraId)
const state = ref('idle')
const level = ref(0)
const uploading = ref(false)
const latestEvents = ref([])
const latestResult = ref(null)
const serviceStatus = ref(null)
const errorMessage = ref('')
let recorder = null
const pendingChunks = []

const isRunning = computed(() => state.value === 'listening' || state.value === 'starting')
const levelPercent = computed(() => Math.min(100, Math.round(level.value * 350)))
const semanticStatus = computed(() => serviceStatus.value?.detectors?.semantic)

async function loadStatus() {
  try {
    const response = await getAudioStatus()
    serviceStatus.value = response.data
  } catch (error) {
    errorMessage.value = error.response?.data?.message || '声音检测服务不可用'
  }
}

async function uploadChunk(blob) {
  if (state.value !== 'listening') return
  pendingChunks.push(blob)
  if (uploading.value) return

  uploading.value = true
  try {
    while (pendingChunks.length && state.value === 'listening') {
      const nextChunk = pendingChunks.shift()
      const form = new FormData()
      form.append('audio', nextChunk, `audio-${Date.now()}.wav`)
      form.append('camera_id', selectedCameraId.value)
      form.append('create_alarm', 'true')
      try {
        const response = await analyzeAudioChunk(form)
        latestResult.value = response.data
        latestEvents.value = response.data.events || []
        serviceStatus.value = { ...serviceStatus.value, detectors: response.data.detectors }
      } catch (error) {
        errorMessage.value = error.response?.data?.message || error.message || '音频分析失败'
      }
    }
  } finally {
    uploading.value = false
  }
}

async function start() {
  state.value = 'starting'
  errorMessage.value = ''
  try {
    recorder = new MicrophoneChunkRecorder({
      chunkSeconds: serviceStatus.value?.chunk_seconds || 0.5,
      onLevel: (value) => { level.value = value },
      onChunk: uploadChunk,
    })
    await recorder.start()
    state.value = 'listening'
    ElMessage.success('声音检测已启动')
  } catch (error) {
    state.value = 'error'
    errorMessage.value = error.name === 'NotAllowedError'
      ? '麦克风权限被拒绝，请在浏览器地址栏中允许访问'
      : error.message
    await recorder?.stop()
    recorder = null
  }
}

async function stop() {
  await recorder?.stop()
  recorder = null
  pendingChunks.length = 0
  state.value = 'idle'
  uploading.value = false
  ElMessage.info('声音检测已停止')
}

onMounted(loadStatus)
onBeforeUnmount(async () => recorder?.stop())
</script>

<template>
  <section class="panel sound-monitor">
    <div class="section-head">
      <div>
        <h2>实时声音检测</h2>
        <p>{{ isRunning ? '正在监听并分析异常声音' : '启动后将请求浏览器麦克风权限' }}</p>
      </div>
      <el-button v-if="!isRunning" type="primary" :icon="Mic" :loading="state === 'starting'" @click="start">
        开始检测
      </el-button>
      <el-button v-else type="danger" :icon="MicOff" @click="stop">停止检测</el-button>
    </div>

    <div class="sound-monitor-body">
      <div class="sound-controls">
        <el-select v-model="selectedCameraId" :disabled="isRunning" aria-label="声音归属摄像头">
          <el-option v-for="camera in cameras" :key="camera.id" :label="camera.name" :value="camera.id" />
        </el-select>
        <el-tag :type="isRunning ? 'success' : 'info'">
          {{ isRunning ? (uploading ? '分析中' : '监听中') : '未启动' }}
        </el-tag>
        <el-tag :type="semanticStatus?.enabled ? 'success' : 'warning'">
          YAMNet {{ semanticStatus?.enabled ? (semanticStatus.loaded ? '已加载' : '待加载') : '未启用' }}
        </el-tag>
      </div>

      <div class="audio-meter" role="meter" aria-label="实时音量" :aria-valuenow="levelPercent">
        <Activity />
        <div><span :style="{ width: `${levelPercent}%` }" /></div>
        <strong>{{ levelPercent }}%</strong>
      </div>

      <div v-if="latestEvents.length" class="sound-events">
        <span v-for="event in latestEvents" :key="`${event.label}-${event.score}`">
          {{ event.raw_label || event.label }} · {{ Math.round(event.score * 100) }}%
        </span>
      </div>
      <p v-else class="sound-empty">
        {{ latestResult ? '当前分段未发现异常声音' : '尚无分析结果' }}
      </p>
      <p v-if="errorMessage" class="sound-error">{{ errorMessage }}</p>
    </div>
  </section>
</template>
