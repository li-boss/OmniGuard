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

function formatTime(value) {
  return value ? new Date(value).toLocaleString() : '-'
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
      <el-table-column prop="title" label="标题" min-width="180" />
      <el-table-column prop="cameraId" label="摄像头" width="120" />
      <el-table-column prop="severity" label="等级" width="100" />
      <el-table-column prop="status" label="状态" width="110" />
      <el-table-column label="时间" min-width="180">
        <template #default="{ row }">{{ formatTime(row.occurredAt) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <el-button
            :disabled="row.status === 'handled'"
            size="small"
            type="primary"
            @click="handle(row)"
          >
            处置
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </section>
</template>
