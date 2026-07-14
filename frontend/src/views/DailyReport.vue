<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'

const router = useRouter()
const loading = ref(false)
const reports = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)

const detailDialogVisible = ref(false)
const selectedReport = ref(null)

async function load() {
  loading.value = true
  try {
    const response = await fetch(`/api/reports?page=${page.value}&per_page=${pageSize.value}`, {
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('smart-campus-token')}`
      }
    })
    const result = await response.json()
    if (result.code === 0) {
      reports.value = result.data.items
      total.value = result.data.total
    }
  } finally {
    loading.value = false
  }
}

async function viewDetail(row) {
  try {
    const response = await fetch(`/api/reports/${row.id}`, {
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('smart-campus-token')}`
      }
    })
    const result = await response.json()
    if (result.code === 0) {
      selectedReport.value = result.data
      detailDialogVisible.value = true
    }
  } catch (error) {
    ElMessage.error('获取详情失败')
  }
}

async function deleteReport(row) {
  try {
    const response = await fetch(`/api/reports/${row.id}`, {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('smart-campus-token')}`
      }
    })
    const result = await response.json()
    if (result.code === 0) {
      ElMessage.success('删除成功')
      await load()
    }
  } catch (error) {
    ElMessage.error('删除失败')
  }
}

async function downloadReport(row) {
  const token = localStorage.getItem('smart-campus-token')
  try {
    const response = await fetch(`/api/reports/${row.id}/download`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    })
    if (!response.ok) {
      const result = await response.json()
      ElMessage.error(result.message || '下载失败')
      return
    }
    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `校园安全日报_${row.generated_at?.slice(0, 10) || 'report'}.pdf`
    a.click()
    window.URL.revokeObjectURL(url)
  } catch (error) {
    ElMessage.error('下载失败')
  }
}

function formatTime(value) {
  return value ? new Date(value).toLocaleString() : '-'
}

onMounted(load)
</script>

<template>
  <section class="panel" v-loading="loading">
    <div class="filter-bar">
      <el-button type="primary" @click="load">刷新</el-button>
    </div>

    <el-table :data="reports" table-layout="fixed">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column label="生成时间" width="180">
        <template #default="{ row }">{{ formatTime(row.generated_at) }}</template>
      </el-table-column>
      <el-table-column prop="summary" label="监控情况" min-width="200" />
      <el-table-column label="风险评分" width="120">
        <template #default="{ row }">
          <el-tag :type="row.risk_level === '高' ? 'danger' : row.risk_level === '中' ? 'warning' : 'success'">
            {{ row.risk_score }}分 ({{ row.risk_level }})
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="total_alarms" label="告警数" width="100" />
      <el-table-column label="操作" width="240" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="viewDetail(row)">详情</el-button>
          <el-button size="small" type="primary" @click="downloadReport(row)">下载</el-button>
          <el-button size="small" type="danger" @click="deleteReport(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination-container">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="load"
      />
    </div>

    <el-dialog v-model="detailDialogVisible" title="日报详情" width="800px">
      <div v-if="selectedReport" class="report-detail">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="标题">{{ selectedReport.title }}</el-descriptions-item>
          <el-descriptions-item label="生成时间">{{ formatTime(selectedReport.generated_at) }}</el-descriptions-item>
          <el-descriptions-item label="风险评分">{{ selectedReport.risk_score }}分</el-descriptions-item>
          <el-descriptions-item label="风险等级">{{ selectedReport.risk_level }}</el-descriptions-item>
          <el-descriptions-item label="告警总数">{{ selectedReport.total_alarms }}次</el-descriptions-item>
          <el-descriptions-item label="监控时段">{{ formatTime(selectedReport.start_time) }} 至 {{ formatTime(selectedReport.end_time) }}</el-descriptions-item>
        </el-descriptions>
        
        <div v-if="selectedReport.content" class="report-content">
          <h3>安全分析</h3>
          <p v-for="(item, index) in selectedReport.content.analysis" :key="index">{{ index + 1 }}. {{ item }}</p>
          
          <h3>改进建议</h3>
          <p v-for="(item, index) in selectedReport.content.suggestions" :key="index">{{ index + 1 }}. {{ item }}</p>
        </div>
      </div>
    </el-dialog>
  </section>
</template>

<style scoped>
.pagination-container {
  margin-top: 20px;
  display: flex;
  justify-content: center;
}

.report-detail {
  max-height: 600px;
  overflow-y: auto;
}

.report-content {
  margin-top: 20px;
}

.report-content h3 {
  margin: 15px 0 10px;
  font-size: 16px;
}

.report-content p {
  margin: 8px 0;
  line-height: 1.6;
}
</style>