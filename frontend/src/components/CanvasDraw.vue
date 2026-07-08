<script setup>
import { onMounted, ref, watch } from 'vue'
import { RotateCcw, Trash2 } from '@lucide/vue'

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:modelValue'])
const canvas = ref(null)
const draggingIndex = ref(null)

function getCanvasPoint(event) {
  const node = canvas.value
  const rect = node.getBoundingClientRect()
  return {
    x: Math.round((event.clientX - rect.left) * (node.width / rect.width)),
    y: Math.round((event.clientY - rect.top) * (node.height / rect.height)),
  }
}

function clampPoint(point) {
  const node = canvas.value
  return {
    x: Math.max(0, Math.min(node.width, point.x)),
    y: Math.max(0, Math.min(node.height, point.y)),
  }
}

function findPointIndex(point) {
  const hitRadius = 12
  return props.modelValue.findIndex((item) => {
    const distance = Math.hypot(item.x - point.x, item.y - point.y)
    return distance <= hitRadius
  })
}

function draw() {
  const node = canvas.value
  if (!node) return
  const context = node.getContext('2d')
  const width = node.width
  const height = node.height
  context.clearRect(0, 0, width, height)
  context.fillStyle = '#17212b'
  context.fillRect(0, 0, width, height)
  context.strokeStyle = '#4f6272'
  context.lineWidth = 1
  for (let x = 0; x <= width; x += 80) {
    context.beginPath()
    context.moveTo(x, 0)
    context.lineTo(x, height)
    context.stroke()
  }
  for (let y = 0; y <= height; y += 60) {
    context.beginPath()
    context.moveTo(0, y)
    context.lineTo(width, y)
    context.stroke()
  }

  const points = props.modelValue
  if (points.length) {
    context.beginPath()
    context.moveTo(points[0].x, points[0].y)
    points.slice(1).forEach((point) => context.lineTo(point.x, point.y))
    if (points.length >= 3) context.closePath()
    context.fillStyle = 'rgba(47, 180, 124, 0.22)'
    context.strokeStyle = '#2fb47c'
    context.lineWidth = 2
    context.fill()
    context.stroke()
  }

  points.forEach((point, index) => {
    context.beginPath()
    context.arc(point.x, point.y, 5, 0, Math.PI * 2)
    context.fillStyle = '#f6c35b'
    context.fill()
    context.fillStyle = '#111820'
    context.font = '12px sans-serif'
    context.fillText(String(index + 1), point.x + 8, point.y - 8)
  })
}

function updatePoint(index, point) {
  const next = props.modelValue.map((item, itemIndex) => (
    itemIndex === index ? clampPoint(point) : item
  ))
  emit('update:modelValue', next)
}

function startDraw(event) {
  const point = getCanvasPoint(event)
  const pointIndex = findPointIndex(point)
  if (pointIndex >= 0) {
    draggingIndex.value = pointIndex
    canvas.value.setPointerCapture?.(event.pointerId)
    return
  }

  emit('update:modelValue', [...props.modelValue, clampPoint(point)])
}

function dragPoint(event) {
  if (draggingIndex.value === null) return
  updatePoint(draggingIndex.value, getCanvasPoint(event))
}

function stopDrag(event) {
  if (draggingIndex.value !== null) {
    canvas.value.releasePointerCapture?.(event.pointerId)
  }
  draggingIndex.value = null
}

function undo() {
  emit('update:modelValue', props.modelValue.slice(0, -1))
}

function clear() {
  emit('update:modelValue', [])
}

watch(() => props.modelValue, draw, { deep: true })
onMounted(draw)
</script>

<template>
  <div class="canvas-tool">
    <canvas
      ref="canvas"
      width="800"
      height="450"
      @pointerdown="startDraw"
      @pointermove="dragPoint"
      @pointerup="stopDrag"
      @pointercancel="stopDrag"
      @pointerleave="stopDrag"
    />
    <div class="canvas-actions">
      <el-tooltip content="撤销" placement="top">
        <el-button :icon="RotateCcw" circle @click="undo" />
      </el-tooltip>
      <el-tooltip content="清空" placement="top">
        <el-button :icon="Trash2" circle @click="clear" />
      </el-tooltip>
    </div>
  </div>
</template>
