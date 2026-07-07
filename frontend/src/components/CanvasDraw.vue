<template>
  <canvas ref="canvasRef" class="draw-canvas" @click="addPoint" />
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'

const props = defineProps({
  points: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['update:points'])
const canvasRef = ref(null)

const draw = () => {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  canvas.width = canvas.clientWidth
  canvas.height = canvas.clientHeight
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  ctx.strokeStyle = '#18a058'
  ctx.fillStyle = '#18a058'
  ctx.lineWidth = 2
  ctx.beginPath()
  props.points.forEach((point, index) => {
    const x = point.x * canvas.width
    const y = point.y * canvas.height
    if (index === 0) ctx.moveTo(x, y)
    else ctx.lineTo(x, y)
    ctx.fillRect(x - 3, y - 3, 6, 6)
  })
  if (props.points.length > 2) ctx.closePath()
  ctx.stroke()
}

const addPoint = (event) => {
  const canvas = canvasRef.value
  const rect = canvas.getBoundingClientRect()
  const point = {
    x: (event.clientX - rect.left) / rect.width,
    y: (event.clientY - rect.top) / rect.height
  }
  emit('update:points', [...props.points, point])
}

onMounted(draw)
watch(() => props.points, draw, { deep: true })
</script>

<style scoped>
.draw-canvas {
  width: 100%;
  aspect-ratio: 16 / 9;
  display: block;
  cursor: crosshair;
}
</style>
