<script setup>
import { computed, ref } from 'vue'
import { RefreshCcw, Video } from '@lucide/vue'

const props = defineProps({
  title: { type: String, default: '实时监控' },
  src: { type: String, default: '' },
})

const version = ref(Date.now())
const videoSrc = computed(() => {
  if (!props.src) return ''
  const separator = props.src.includes('?') ? '&' : '?'
  return `${props.src}${separator}t=${version.value}`
})

function refresh() {
  version.value = Date.now()
}
</script>

<template>
  <section class="video-module">
    <div class="section-head">
      <div>
        <h2>{{ title }}</h2>
        <p>{{ src || '等待视频流地址' }}</p>
      </div>
      <el-tooltip content="重连视频流" placement="top">
        <el-button :icon="RefreshCcw" circle @click="refresh" />
      </el-tooltip>
    </div>
    <div class="video-stage">
      <img v-if="videoSrc" :src="videoSrc" alt="实时视频" />
      <div v-else class="video-empty">
        <Video />
      </div>
    </div>
  </section>
</template>
