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
const detailDialogVisible = ref(false)
const currentAlarm = ref(null)
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

const snapshotPlaceholder = 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(
  '<svg xmlns="http://www.w3.org/2000/svg" width="120" height="72"><rect width="100%" height="100%" fill="#f2f3f5"/><text x="50%" y="50%" text-anchor="middle" dominant-baseline="middle" fill="#909399" font-size="14">暂无图片</text></svg>'
)

function snapshotSrc(row) {
  return row.snapshot_url || row.snapshotUrl || snapshotPlaceholder
}

function useSnapshotPlaceholder(event) {
  event.target.onerror = null
  event.target.src = snapshotPlaceholder
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
    if (error.response?.status === 404) {
      ElMessage.warning('录像正在生成，请稍后再试')
    } else {
      ElMessage.error('视频暂不可用，请稍后刷新')
    }
  } finally {
    videoLoading.value = false
  }
}

function handleVideoError() {
  ElMessage.error('视频暂不可用，请稍后刷新')
}

function closeReplay() {
  videoDialogVisible.value = false
  releaseVideoUrl()
}

function showDetail(row) {
  currentAlarm.value = row
  detailDialogVisible.value = true
}

function closeDetail() {
  detailDialogVisible.value = false
  currentAlarm.value = null
}

async function playVideoInDetail() {
  if (!currentAlarm.value?.id) return
  
  videoLoading.value = true
  releaseVideoUrl()
  try {
    const videoBlob = await getAlarmVideo(currentAlarm.value.id)
    videoUrl.value = URL.createObjectURL(videoBlob)
    videoDialogVisible.value = true
  } catch (error) {
    if (error.response?.status === 404) {
      ElMessage.warning('录像正在生成，请稍后再试')
    } else {
      ElMessage.error('视频暂不可用，请稍后刷新')
    }
  } finally {
    videoLoading.value = false
  }
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
      <el-table-column label="告警图片" width="150">
        <template #default="{ row }">
          <img
            :src="snapshotSrc(row)"
            alt="告警抓拍图"
            class="alarm-snapshot"
            @error="useSnapshotPlaceholder"
          >
        </template>
      </el-table-column>
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
            size="small"
            @click="showDetail(row)"
          >
            详情
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

    <div class="pagination-bar">
      <el-pagination
        v-model:current-page="filters.page"
        v-model:page-size="filters.pageSize"
        :total="alarms.total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="load"
        @current-change="load"
      />
    </div>

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
        @error="handleVideoError"
      >
        当前浏览器不支持 HTML5 视频播放。
      </video>
    </el-dialog>

    <!-- 告警详情对话框 -->
    <el-dialog
      v-model="detailDialogVisible"
      title="告警详情"
      width="800px"
      destroy-on-close
      @closed="closeDetail"
    >
      <div v-if="currentAlarm" class="alarm-detail">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="告警ID">{{ currentAlarm.id }}</el-descriptions-item>
          <el-descriptions-item label="告警类型">{{ currentAlarm.type || currentAlarm.alarm_type }}</el-descriptions-item>
          <el-descriptions-item label="摄像头">{{ currentAlarm.cameraId || currentAlarm.camera_id }}</el-descriptions-item>
          <el-descriptions-item label="等级">{{ currentAlarm.severity }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ currentAlarm.status }}</el-descriptions-item>
          <el-descriptions-item label="发生时间">{{ formatTime(currentAlarm.occurredAt || currentAlarm.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="告警描述" :span="2">
            {{ currentAlarm.description || '无' }}
          </el-descriptions-item>
          <el-descriptions-item label="检测数据" :span="2">
            <pre v-if="currentAlarm.detection_data">{{ JSON.stringify(currentAlarm.detection_data, null, 2) }}</pre>
            <span v-else>无</span>
          </el-descriptions-item>
        </el-descriptions>
        
        <div v-if="currentAlarm.snapshot_url || currentAlarm.snapshotUrl" class="snapshot-section">
          <h4>告警抓拍图</h4>
          <img
            :src="currentAlarm.snapshot_url || currentAlarm.snapshotUrl"
            alt="告警抓拍图"
            class="detail-snapshot"
            @error="useSnapshotPlaceholder"
          >
        </div>
        
        <div class="action-buttons">
          <el-button
            :disabled="!currentAlarm.id"
            :loading="videoLoading"
            type="primary"
            @click="playVideoInDetail"
          >
            查看回放
          </el-button>
          <el-button
            v-if="currentAlarm.status !== 'handled'"
            type="success"
            @click="handle(currentAlarm); closeDetail()"
          >
            立即处置
          </el-button>
        </div>
      </div>
    </el-dialog>

    <!-- 视频回放对话框 -->
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
        @error="handleVideoError"
      >
        当前浏览器不支持 HTML5 视频播放。
      </video>
    </el-dialog>
  </section>
</template>

<style scoped>
.alarm-snapshot {
  display: block;
  width: 120px;
  height: 72px;
  border-radius: 4px;
  object-fit: cover;
  background: #f2f3f5;
}

.pagination-bar {
  display: flex;
  justify-content: center;
  margin-top: 20px;
  padding: 10px 0;
}

.alarm-detail {
  padding: 10px 0;
}

.snapshot-section {
  margin-top: 20px;
}

.snapshot-section h4 {
  margin-bottom: 10px;
  color: #303133;
}

.detail-snapshot {
  max-width: 100%;
  max-height: 400px;
  border-radius: 4px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.action-buttons {
  margin-top: 20px;
  display: flex;
  gap: 10px;
  justify-content: center;
}

pre {
  background: #f5f7fa;
  padding: 10px;
  border-radius: 4px;
  font-size: 12px;
  overflow-x: auto;
}
</style>
