<template>
  <video v-if="isHls" class="video-player" :src="src" controls autoplay muted />
  <img v-else class="video-player" :src="src" alt="camera stream" />
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  src: {
    type: String,
    required: true
  }
})

const isHls = computed(() => props.src.endsWith('.m3u8') || props.src.endsWith('.mp4'))
</script>

<style scoped>
.video-player {
  width: 100%;
  aspect-ratio: 16 / 9;
  object-fit: cover;
  background: #101828;
  border-radius: 8px;
}
</style>
