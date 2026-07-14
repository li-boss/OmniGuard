<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getAccessLogs, getAccessLogDetail, deleteAccessLog } from '../api/accessLog'

const loading = ref(false)
const detailDialogVisible = ref(false)
const currentLog = ref(null)
const tableData = ref([])
const total = ref(0)

const filters = reactive({
  page: 1,
  pageSize: 20,
  user_id: '',
  result: '',
})

async function load() {
  loading.value = true
  try {
    const params = { ...filters }
    if (!params.user_id) delete params.user_id
    if (!params.result) delete params.result
    
    const res = await getAccessLogs(params)
    if (res.code === 0) {
      tableData.value = res.data.items
      total.value = res.data.total
    } else {
      ElMessage.error(res.message || '加载失败')
    }
  } catch (error) {
    ElMessage.error('加载通行历史失败')
  } finally {
    loading.value = false
  }
}

function formatTime(value) {
  return value ? new Date(value).toLocaleString() : '-'
}

function getResultType(result) {
  const typeMap = {
    'granted': 'success',
    'denied': 'danger',
    'pending': 'warning'
  }
  return typeMap[result] || 'info'
}

function getResultText(result) {
  const textMap = {
    'granted': '通过',
    'denied': '拒绝',
    'pending': '待定'
  }
  return textMap[result] || result
}

function getMethodText(method) {
  const textMap = {
    'face': '人脸识别',
    'card': '刷卡',
    'password': '密码'
  }
  return textMap[method] || method
}

async function showDetail(row) {
  try {
    const res = await getAccessLogDetail(row.id)
    if (res.code === 0) {
      currentLog.value = res.data
      detailDialogVisible.value = true
    } else {
      ElMessage.error(res.message || '获取详情失败')
    }
  } catch (error) {
    ElMessage.error('获取详情失败')
  }
}

function closeDetail() {
  detailDialogVisible.value = false
  currentLog.value = null
}

function handlePageChange(page) {
  filters.page = page
  load()
}

function handleSizeChange(size) {
  filters.pageSize = size
  filters.page = 1
  load()
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(
      `确定要删除此通行记录吗？`,
      '确认删除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
    
    const res = await deleteAccessLog(row.id)
    if (res.code === 0) {
      ElMessage.success('删除成功')
      await load()
    } else {
      ElMessage.error(res.message || '删除失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

onMounted(load)
</script>

<template>
  <section class="panel" v-loading="loading">
    <div class="filter-bar">
      <el-input
        v-model="filters.user_id"
        clearable
        placeholder="用户ID"
        style="width: 200px; margin-right: 10px"
      />
      <el-select v-model="filters.result" clearable placeholder="结果" style="width: 150px; margin-right: 10px">
        <el-option label="通过" value="granted" />
        <el-option label="拒绝" value="denied" />
        <el-option label="待定" value="pending" />
      </el-select>
      <el-button type="primary" @click="load">查询</el-button>
    </div>

    <el-table :data="tableData" table-layout="fixed">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="username" label="用户名" width="120">
        <template #default="{ row }">
          {{ row.username || '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="real_name" label="姓名" width="120">
        <template #default="{ row }">
          {{ row.real_name || '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="access_method" label="通行方式" width="120">
        <template #default="{ row }">
          {{ getMethodText(row.access_method) }}
        </template>
      </el-table-column>
      <el-table-column prop="direction" label="方向" width="80">
        <template #default="{ row }">
          {{ row.direction === 'in' ? '进入' : '离开' }}
        </template>
      </el-table-column>
      <el-table-column prop="result" label="结果" width="100">
        <template #default="{ row }">
          <el-tag :type="getResultType(row.result)" size="small">
            {{ getResultText(row.result) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="zone_name" label="区域" width="150">
        <template #default="{ row }">
          {{ row.zone_name || '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="device_code" label="设备" width="120">
        <template #default="{ row }">
          {{ row.device_code || '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="confidence" label="置信度" width="100">
        <template #default="{ row }">
          {{ row.confidence ? (row.confidence * 100).toFixed(1) + '%' : '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="occurred_at" label="时间" width="180">
        <template #default="{ row }">
          {{ formatTime(row.occurred_at) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" link @click="showDetail(row)">详情</el-button>
          <el-button type="danger" link @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination">
      <el-pagination
        v-model:current-page="filters.page"
        v-model:page-size="filters.pageSize"
        :page-sizes="[10, 20, 50, 100]"
        :total="total"
        layout="total, sizes, prev, pager, next, jumper"
        @current-change="handlePageChange"
        @size-change="handleSizeChange"
      />
    </div>

    <el-dialog
      v-model="detailDialogVisible"
      title="通行详情"
      width="600px"
      @close="closeDetail"
    >
      <div v-if="currentLog" class="detail-content">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="日志ID">{{ currentLog.id }}</el-descriptions-item>
          <el-descriptions-item label="用户ID">{{ currentLog.user_id || '-' }}</el-descriptions-item>
          <el-descriptions-item label="用户名">{{ currentLog.username || '-' }}</el-descriptions-item>
          <el-descriptions-item label="姓名">{{ currentLog.real_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="区域ID">{{ currentLog.zone_id || '-' }}</el-descriptions-item>
          <el-descriptions-item label="区域名称">{{ currentLog.zone_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="通行方式">{{ getMethodText(currentLog.access_method) }}</el-descriptions-item>
          <el-descriptions-item label="方向">{{ currentLog.direction === 'in' ? '进入' : '离开' }}</el-descriptions-item>
          <el-descriptions-item label="结果">
            <el-tag :type="getResultType(currentLog.result)" size="small">
              {{ getResultText(currentLog.result) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="设备编码">{{ currentLog.device_code || '-' }}</el-descriptions-item>
          <el-descriptions-item label="置信度">
            {{ currentLog.confidence ? (currentLog.confidence * 100).toFixed(2) + '%' : '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="备注">{{ currentLog.remark || '-' }}</el-descriptions-item>
          <el-descriptions-item label="发生时间">{{ formatTime(currentLog.occurred_at) }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatTime(currentLog.created_at) }}</el-descriptions-item>
        </el-descriptions>
      </div>
    </el-dialog>
  </section>
</template>

<style scoped>
.panel {
  padding: 20px;
  background: #fff;
  border-radius: 4px;
}

.filter-bar {
  margin-bottom: 20px;
  display: flex;
  align-items: center;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

.detail-content {
  padding: 10px 0;
}
</style>