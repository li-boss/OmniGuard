<script setup>
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { useAlarmsStore } from '../store/alarms'
import { getAlarmVideo } from '../api/alarm'

const alarms = useAlarmsStore()
const loading = ref(false)
const videoDialogVisible = ref(false)
const videoLoading = ref(false)
const videoUrl = ref('')
const filters = reactive({
  page: 1,
  pageSize: 10,
  severity: '',
  status: '',
})

async function load() {
  loading.value = true
  try {
    await alarms.fetch(filters)
  } finally {
    loading.value = false
  }
}

async function handle(row) {
  await alarms.handle(row.id, '前端确认处置')
  ElMessage.success('告警已处置')
  await load()
}

async function remove(row) {
  try {
    await alarms.delete(row.id)
    ElMessage.success('告警已删除')
    await load()
  } catch (error) {
    ElMessage.error('删除失败')
  }
}

function formatTime(value) {
  return value ? new Date(value).toLocaleString() : '-'
}

function releaseVideoUrl() {
  if (videoUrl.value) {
    URL.revokeObjectURL(videoUrl.value)
    videoUrl.value = ''
  }
}

async function showReplay(row) {
  videoLoading.value = true
  releaseVideoUrl()
  try {
    const videoBlob = await getAlarmVideo(row.id)
    videoUrl.value = URL.createObjectURL(videoBlob)
    videoDialogVisible.value = true
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '告警录像暂不可用')
  } finally {
    videoLoading.value = false
  }
}

function closeReplay() {
  videoDialogVisible.value = false
  releaseVideoUrl()
}

onMounted(load)
onBeforeUnmount(releaseVideoUrl)
</script>

<template>
  <section class="panel" v-loading="loading">
    <div class="filter-bar">
      <el-select v-model="filters.severity" clearable placeholder="等级" @change="load">
        <el-option label="低" value="low" />
        <el-option label="中" value="medium" />
        <el-option label="高" value="high" />
        <el-option label="严重" value="critical" />
      </el-select>
      <el-select v-model="filters.status" clearable placeholder="状态" @change="load">
        <el-option label="待处置" value="pending" />
        <el-option label="已处置" value="handled" />
      </el-select>
      <el-button type="primary" @click="load">查询</el-button>
    </div>

    <el-table :data="alarms.items" table-layout="fixed">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="title" label="标题" min-width="180" />
      <el-table-column prop="cameraId" label="摄像头" width="120" />
      <el-table-column prop="severity" label="等级" width="100" />
      <el-table-column prop="status" label="状态" width="110" />
      <el-table-column label="时间" min-width="180">
        <template #default="{ row }">{{ formatTime(row.occurredAt) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="270" fixed="right">
        <template #default="{ row }">
          <el-button
            :disabled="!row.video_url"
            :loading="videoLoading"
            size="small"
            @click="showReplay(row)"
          >
            查看回放
          </el-button>
          <el-button
            :disabled="row.status === 'handled'"
            size="small"
            type="primary"
            @click="handle(row)"
          >
            处置
          </el-button>
          <el-button
            v-if="row.status === 'handled'"
            size="small"
            type="danger"
            @click="remove(row)"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog
      v-model="videoDialogVisible"
      title="告警监控回放"
      width="720px"
      destroy-on-close
      @closed="closeReplay"
    >
      <video
        v-if="videoUrl"
        :src="videoUrl"
        controls
        autoplay
        preload="metadata"
        style="display: block; width: 100%; max-height: 60vh; background: #000"
      >
        当前浏览器不支持 HTML5 视频播放。
      </video>
    </el-dialog>
  </section>
</template>
