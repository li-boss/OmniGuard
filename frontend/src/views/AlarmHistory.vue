<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { useAlarmsStore } from '../store/alarms'

const alarms = useAlarmsStore()
const loading = ref(false)
const filters = reactive({
  page: 1,
  pageSize: 10,
  severity: '',
  status: '',
})

const previewVisible = ref(false)
const previewSrc = ref('')
const clipVisible = ref(false)
const clipUrl = ref('')

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

function showSnapshot(row) {
  if (!row.snapshotUrl && !row.snapshot_path) return
  previewSrc.value = row.snapshotUrl || row.snapshot_path
  previewVisible.value = true
}

function showClip(row) {
  clipUrl.value = `/api/alarms/${row.id}/clip`
  clipVisible.value = true
}

onMounted(load)
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
      <el-table-column label="快照" width="90">
        <template #default="{ row }">
          <el-image
            v-if="row.snapshotUrl || row.snapshot_path"
            :src="row.snapshotUrl || row.snapshot_path"
            :preview-src-list="[row.snapshotUrl || row.snapshot_path]"
            fit="cover"
            style="width: 60px; height: 40px; border-radius: 4px; cursor: pointer"
            :preview-teleported="true"
          />
          <span v-else style="color: #999; font-size: 12px">无</span>
        </template>
      </el-table-column>
      <el-table-column prop="title" label="标题" min-width="160" />
      <el-table-column prop="cameraId" label="摄像头" width="100" />
      <el-table-column prop="severity" label="等级" width="80" />
      <el-table-column prop="status" label="状态" width="90" />
      <el-table-column label="时间" min-width="160">
        <template #default="{ row }">{{ formatTime(row.occurredAt) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="240" fixed="right">
        <template #default="{ row }">
          <el-button
            v-if="row.clipUrl || row.clip_url"
            size="small"
            type="warning"
            @click="showClip(row)"
          >
            回放
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

    <el-dialog v-model="clipVisible" title="告警视频回放" width="720px" destroy-on-close>
      <video
        v-if="clipVisible"
        :src="clipUrl"
        controls
        autoplay
        style="width: 100%; border-radius: 6px; background: #000"
      />
    </el-dialog>
  </section>
</template>
