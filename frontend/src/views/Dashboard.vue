<template>
  <div class="dashboard-content">
    <el-row :gutter="20">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-item">
            <div class="stat-value">{{ stats.todayAlarms }}</div>
            <div class="stat-label">今日告警</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-item">
            <div class="stat-value">{{ stats.activeCameras }}</div>
            <div class="stat-label">在线摄像头</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-item">
            <div class="stat-value">{{ stats.recognizedFaces }}</div>
            <div class="stat-label">已识别人脸</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-item">
            <div class="stat-value">{{ stats.activeZones }}</div>
            <div class="stat-label">活跃围栏</div>
          </div>
        </el-card>
      </el-col>
    </el-row>
    
    <el-row :gutter="20" style="margin-top: 20px;">
      <el-col :span="16">
        <el-card>
          <template #header>
            <span>告警趋势</span>
          </template>
          <div class="chart-placeholder">
            <p>图表区域（待实现）</p>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card>
          <template #header>
            <span>告警类型分布</span>
          </template>
          <div class="chart-placeholder">
            <p>图表区域（待实现）</p>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { reactive, onMounted } from 'vue'
import { dashboardApi, dashboardApiMock } from '@/api/dashboard'

const stats = reactive({
  todayAlarms: 0,
  activeCameras: 0,
  recognizedFaces: 0,
  activeZones: 0
})

const loadDashboardData = async () => {
  try {
    /* ========== 使用模拟API（测试用，联调时改为真实API） ========== */
    const data = await dashboardApiMock.getSummary()
    /* ========== 模拟API结束 ========== */
    
    // 真实API调用（联调时启用）
    // const data = await dashboardApi.getSummary()
    
    Object.assign(stats, data)
  } catch (error) {
    console.error('加载统计数据失败:', error)
  }
}

onMounted(() => {
  loadDashboardData()
})
</script>

<style scoped>
.dashboard-content {
  width: 100%;
}

.stat-card {
  text-align: center;
}

.stat-item {
  padding: 10px 0;
}

.stat-value {
  font-size: 32px;
  font-weight: bold;
  color: #409eff;
  margin-bottom: 10px;
}

.stat-label {
  font-size: 14px;
  color: #909399;
}

.chart-placeholder {
  height: 300px;
  display: flex;
  justify-content: center;
  align-items: center;
  color: #909399;
}
</style>
