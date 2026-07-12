<script setup>
import { computed, ref, onBeforeUnmount } from 'vue'
import { RefreshCcw, Video } from '@lucide/vue'
import { ElMessage } from 'element-plus'
import { useCameraStore } from '../store/camera'

const props = defineProps({
  id: { type: String, default: '' },
  title: { type: String, default: '实时监控' },
  src: { type: String, default: '' },
})

const cameraStore = useCameraStore()
const version = ref(Date.now())
const imgRef = ref(null)

const videoSrc = computed(() => {
  if (!props.src) return ''
  const separator = props.src.includes('?') ? '&' : '?'
  return `${props.src}${separator}t=${version.value}`
})

function refresh() {
  version.value = Date.now()
}

async function toggleMode() {
  try {
    const data = await cameraStore.toggleSource()
    const modeName = data.source === '0' ? '本地直连' : 'RTMP 推流'
    ElMessage.success(`成功切换为 ${modeName}`)
    refresh()
  } catch (error) {
    ElMessage.error('切换摄像源失败')
  }
}

onBeforeUnmount(() => {
  if (imgRef.value) {
    imgRef.value.src = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'
  }
})
</script>

<template>
  <section class="video-module">
    <div class="section-head">
      <div>
        <h2>{{ title }}</h2>
        <p>{{ src || '等待视频流地址' }}</p>
      </div>
      <div style="display: flex; align-items: center; gap: 8px;">
        <el-button 
          v-if="id === 'cam-1'"
          :type="cameraStore.cameras.find(c => c.id === 'cam-1')?.isLocal ? 'primary' : 'success'"
          size="small"
          round
          plain
          @click="toggleMode"
        >
          {{ cameraStore.cameras.find(c => c.id === 'cam-1')?.isLocal ? '切换为 RTMP 推流' : '切换为本地直连' }}
        </el-button>
        <el-tooltip content="重连视频流" placement="top">
          <el-button :icon="RefreshCcw" circle @click="refresh" />
        </el-tooltip>
      </div>
    </div>
    <div class="video-stage">
      <img v-if="videoSrc" ref="imgRef" :src="videoSrc" alt="实时视频" />
      <div v-else class="video-empty">
        <Video />
      </div>
    </div>
  </section>
</template>
