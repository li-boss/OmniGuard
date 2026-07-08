<template>
  <div class="alarm-history">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>告警历史</span>
          <div class="filter-area">
            <el-date-picker
              v-model="dateRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              size="small"
              style="margin-right: 10px;"
            />
            <el-select v-model="alarmType" placeholder="告警类型" size="small" style="width: 120px; margin-right: 10px;">
              <el-option label="全部" value="" />
              <el-option label="人员入侵" value="intrusion" />
              <el-option label="越界行为" value="crossing" />
              <el-option label="异常聚集" value="gathering" />
            </el-select>
            <el-select v-model="severity" placeholder="告警级别" size="small" style="width: 120px; margin-right: 10px;">
              <el-option label="全部" value="" />
              <el-option label="低" value="low" />
              <el-option label="中" value="medium" />
              <el-option label="高" value="high" />
            </el-select>
            <el-button type="primary" size="small" @click="handleSearch">查询</el-button>
            <el-button size="small" @click="handleReset">重置</el-button>
          </div>
        </div>
      </template>
      
      <el-table
        :data="alarmList"
        style="width: 100%"
        v-loading="loading"
      >
        <el-table-column prop="id" label="告警ID" width="80" />
        <el-table-column prop="type" label="告警类型" width="120">
          <template #default="{ row }">
            <el-tag :type="getTypeTag(row.type)">{{ getTypeText(row.type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="severity" label="告警级别" width="100">
          <template #default="{ row }">
            <el-tag :type="getSeverityTag(row.severity)">{{ getSeverityText(row.severity) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="cameraName" label="摄像头" width="150" />
        <el-table-column prop="zoneName" label="围栏区域" width="150" />
        <el-table-column prop="timestamp" label="触发时间" width="180" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusTag(row.status)">{{ getStatusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button size="small" @click="handleView(row)">查看</el-button>
            <el-button 
              size="small" 
              type="primary" 
              v-if="row.status === 'pending'"
              @click="handleProcess(row)"
            >
              处置
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :page-sizes="[10, 20, 50, 100]"
        :total="total"
        layout="total, sizes, prev, pager, next, jumper"
        style="margin-top: 20px; justify-content: flex-end;"
        @size-change="handleSizeChange"
        @current-change="handleCurrentChange"
      />
    </el-card>
    
    <el-dialog v-model="detailDialogVisible" title="告警详情" width="800px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="告警ID">{{ currentAlarm.id }}</el-descriptions-item>
        <el-descriptions-item label="告警类型">{{ getTypeText(currentAlarm.type) }}</el-descriptions-item>
        <el-descriptions-item label="告警级别">{{ getSeverityText(currentAlarm.severity) }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ getStatusText(currentAlarm.status) }}</el-descriptions-item>
        <el-descriptions-item label="摄像头">{{ currentAlarm.cameraName }}</el-descriptions-item>
        <el-descriptions-item label="围栏区域">{{ currentAlarm.zoneName }}</el-descriptions-item>
        <el-descriptions-item label="触发时间">{{ currentAlarm.timestamp }}</el-descriptions-item>
        <el-descriptions-item label="处置人">{{ currentAlarm.handler || '-' }}</el-descriptions-item>
        <el-descriptions-item label="备注" :span="2">{{ currentAlarm.note || '-' }}</el-descriptions-item>
      </el-descriptions>
      <div style="margin-top: 20px;">
        <h4>告警截图</h4>
        <div class="alarm-image">
          <p>图片区域（待实现）</p>
        </div>
      </div>
    </el-dialog>
    
    <el-dialog v-model="processDialogVisible" title="告警处置" width="500px">
      <el-form :model="processForm" label-width="80px">
        <el-form-item label="处置方式">
          <el-radio-group v-model="processForm.action">
            <el-radio label="ignore">忽略</el-radio>
            <el-radio label="handle">已处理</el-radio>
            <el-radio label="escalate">上报</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="备注">
          <el-input
            v-model="processForm.note"
            type="textarea"
            :rows="3"
            placeholder="请输入处置备注"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="processDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmitProcess">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { alarmApi } from '@/api/alarm'

const loading = ref(false)
const dateRange = ref([])
const alarmType = ref('')
const severity = ref('')
const currentPage = ref(1)
const pageSize = ref(10)
const total = ref(0)

const alarmList = ref([])

const detailDialogVisible = ref(false)
const processDialogVisible = ref(false)
const currentAlarm = ref({})
const processForm = reactive({
  action: 'handle',
  note: ''
})

const getTypeText = (type) => {
  const map = {
    intrusion: '人员入侵',
    crossing: '越界行为',
    gathering: '异常聚集'
  }
  return map[type] || type
}

const getTypeTag = (type) => {
  const map = {
    intrusion: 'danger',
    crossing: 'warning',
    gathering: 'info'
  }
  return map[type] || 'info'
}

const getSeverityText = (severity) => {
  const map = {
    low: '低',
    medium: '中',
    high: '高'
  }
  return map[severity] || severity
}

const getSeverityTag = (severity) => {
  const map = {
    low: 'info',
    medium: 'warning',
    high: 'danger'
  }
  return map[severity] || 'info'
}

const getStatusText = (status) => {
  const map = {
    pending: '待处理',
    processing: '处理中',
    completed: '已完成',
    ignored: '已忽略'
  }
  return map[status] || status
}

const getStatusTag = (status) => {
  const map = {
    pending: 'warning',
    processing: 'info',
    completed: 'success',
    ignored: 'info'
  }
  return map[status] || 'info'
}

const handleSearch = () => {
  currentPage.value = 1
  loadAlarmList()
}

const handleReset = () => {
  dateRange.value = []
  alarmType.value = ''
  severity.value = ''
  currentPage.value = 1
  loadAlarmList()
}

const handleSizeChange = () => {
  currentPage.value = 1
  loadAlarmList()
}

const handleCurrentChange = () => {
  loadAlarmList()
}

const loadAlarmList = async () => {
  loading.value = true
  try {
    const response = await alarmApi.getList({
      page: currentPage.value,
      pageSize: pageSize.value,
      type: alarmType.value,
      severity: severity.value
    })
    
    alarmList.value = response.list
    total.value = response.total
  } catch (error) {
    ElMessage.error('加载告警列表失败')
  } finally {
    loading.value = false
  }
}

const handleView = (row) => {
  currentAlarm.value = row
  detailDialogVisible.value = true
}

const handleProcess = (row) => {
  currentAlarm.value = row
  processForm.action = 'handle'
  processForm.note = ''
  processDialogVisible.value = true
}

const handleSubmitProcess = async () => {
  try {
    await alarmApi.handle(currentAlarm.value.id, processForm)
    
    ElMessage.success('处置成功')
    processDialogVisible.value = false
    loadAlarmList()
  } catch (error) {
    ElMessage.error('处置失败')
  }
}

loadAlarmList()
</script>

<style scoped>
.alarm-history {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.filter-area {
  display: flex;
  align-items: center;
}

.alarm-image {
  width: 100%;
  height: 300px;
  background: #f5f5f5;
  display: flex;
  justify-content: center;
  align-items: center;
  color: #999;
}
</style>