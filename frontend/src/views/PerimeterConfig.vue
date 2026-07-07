<template>
  <div class="perimeter-config">
    <el-row :gutter="20">
      <el-col :span="8">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>摄像头列表</span>
              <el-button type="primary" size="small" @click="handleAddCamera">添加</el-button>
            </div>
          </template>
          
          <el-tree
            :data="cameraTree"
            :props="{ label: 'name', children: 'children' }"
            node-key="id"
            highlight-current
            @node-click="handleCameraSelect"
          >
            <template #default="{ node, data }">
              <span class="tree-node">
                <span>{{ node.label }}</span>
                <span class="node-actions">
                  <el-tag v-if="data.status === 'online'" type="success" size="small">在线</el-tag>
                  <el-tag v-else type="info" size="small">离线</el-tag>
                </span>
              </span>
            </template>
          </el-tree>
        </el-card>
      </el-col>
      
      <el-col :span="16">
        <el-card>
          <template #header>
            <div class="card-header">
              <span class="card-title" :title="currentCamera?.name || '请选择摄像头'">
                围栏配置 - {{ currentCamera?.name || '请选择摄像头' }}
              </span>
              <div v-if="currentCamera" class="card-actions">
                <el-button type="primary" size="small" @click="handleAddZone">添加围栏</el-button>
                <el-button size="small" @click="handleRefreshZones">刷新</el-button>
              </div>
            </div>
          </template>
          
          <div v-if="!currentCamera" class="empty-area">
            <el-empty description="请从左侧选择摄像头" />
          </div>
          
          <div v-else>
            <div class="video-area">
              <div class="video-placeholder">
                <p>视频画面区域（待集成VideoPlayer组件）</p>
                <p>CanvasDraw组件将在此绘制围栏</p>
              </div>
            </div>
            
            <div style="margin-top: 20px;">
              <el-table :data="zoneList" style="width: 100%">
                <el-table-column prop="name" label="围栏名称" width="150" />
                <el-table-column prop="type" label="围栏类型" width="120">
                  <template #default="{ row }">
                    {{ getZoneTypeText(row.type) }}
                  </template>
                </el-table-column>
                <el-table-column prop="status" label="状态" width="100">
                  <template #default="{ row }">
                    <el-tag :type="row.status === 'active' ? 'success' : 'info'">
                      {{ row.status === 'active' ? '启用' : '禁用' }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="alarmLevel" label="告警级别" width="100">
                  <template #default="{ row }">
                    <el-tag :type="getSeverityTag(row.alarmLevel)">
                      {{ getSeverityText(row.alarmLevel) }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="description" label="描述" />
                <el-table-column label="操作" width="200">
                  <template #default="{ row }">
                    <el-button size="small" @click="handleEditZone(row)">编辑</el-button>
                    <el-button 
                      size="small" 
                      :type="row.status === 'active' ? 'warning' : 'success'"
                      @click="handleToggleZone(row)"
                    >
                      {{ row.status === 'active' ? '禁用' : '启用' }}
                    </el-button>
                    <el-button size="small" type="danger" @click="handleDeleteZone(row)">删除</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
    
    <el-dialog v-model="zoneDialogVisible" :title="zoneForm.id ? '编辑围栏' : '添加围栏'" width="600px">
      <el-form :model="zoneForm" :rules="zoneRules" ref="zoneFormRef" label-width="100px">
        <el-form-item label="围栏名称" prop="name">
          <el-input v-model="zoneForm.name" placeholder="请输入围栏名称" />
        </el-form-item>
        <el-form-item label="围栏类型" prop="type">
          <el-select v-model="zoneForm.type" placeholder="请选择围栏类型">
            <el-option label="禁止区域" value="forbidden" />
            <el-option label="警戒区域" value="warning" />
            <el-option label="监控区域" value="monitor" />
          </el-select>
        </el-form-item>
        <el-form-item label="告警级别" prop="alarmLevel">
          <el-select v-model="zoneForm.alarmLevel" placeholder="请选择告警级别">
            <el-option label="低" value="low" />
            <el-option label="中" value="medium" />
            <el-option label="高" value="high" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="zoneForm.description"
            type="textarea"
            :rows="3"
            placeholder="请输入围栏描述"
          />
        </el-form-item>
        <el-form-item label="围栏坐标">
          <div class="coord-area">
            <p>请在视频画面上绘制围栏多边形</p>
            <el-input
              v-model="zoneForm.coordinates"
              type="textarea"
              :rows="3"
              placeholder="坐标数据（由CanvasDraw组件生成）"
              readonly
            />
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="zoneDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmitZone">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { zoneApi, zoneApiMock } from '@/api/zone'

const currentCamera = ref(null)
const cameraTree = ref([])
const zoneList = ref([])

const zoneDialogVisible = ref(false)
const zoneFormRef = ref(null)
const zoneForm = reactive({
  id: null,
  name: '',
  type: 'forbidden',
  alarmLevel: 'high',
  description: '',
  coordinates: ''
})

const zoneRules = {
  name: [{ required: true, message: '请输入围栏名称', trigger: 'blur' }],
  type: [{ required: true, message: '请选择围栏类型', trigger: 'change' }],
  alarmLevel: [{ required: true, message: '请选择告警级别', trigger: 'change' }]
}

const getZoneTypeText = (type) => {
  const map = {
    forbidden: '禁止区域',
    warning: '警戒区域',
    monitor: '监控区域'
  }
  return map[type] || type
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

const loadCameraTree = async () => {
  try {
    /* ========== 使用模拟API（测试用，联调时改为真实API） ========== */
    cameraTree.value = await zoneApiMock.getCameraTree()
    /* ========== 模拟API结束 ========== */
    
    // 真实API调用（联调时启用）
    // cameraTree.value = await cameraApi.getTree()
  } catch (error) {
    ElMessage.error('加载摄像头列表失败')
  }
}

const loadZoneList = async () => {
  if (!currentCamera.value) return
  
  try {
    /* ========== 使用模拟API（测试用，联调时改为真实API） ========== */
    zoneList.value = await zoneApiMock.getList({ cameraId: currentCamera.value.id })
    /* ========== 模拟API结束 ========== */
    
    // 真实API调用（联调时启用）
    // zoneList.value = await zoneApi.getList({ cameraId: currentCamera.value.id })
  } catch (error) {
    ElMessage.error('加载围栏列表失败')
  }
}

const handleCameraSelect = (data) => {
  currentCamera.value = data
  loadZoneList()
}

const handleAddCamera = () => {
  ElMessage.info('添加摄像头功能待实现')
}

const handleAddZone = () => {
  zoneForm.id = null
  zoneForm.name = ''
  zoneForm.type = 'forbidden'
  zoneForm.alarmLevel = 'high'
  zoneForm.description = ''
  zoneForm.coordinates = ''
  zoneDialogVisible.value = true
}

const handleEditZone = (row) => {
  Object.assign(zoneForm, row)
  zoneDialogVisible.value = true
}

const handleToggleZone = async (row) => {
  try {
    const action = row.status === 'active' ? '禁用' : '启用'
    await ElMessageBox.confirm(`确认${action}该围栏？`, '提示', {
      type: 'warning'
    })
    
    /* ========== 使用模拟API（测试用，联调时改为真实API） ========== */
    await zoneApiMock.update(row.id, { 
      status: row.status === 'active' ? 'inactive' : 'active' 
    })
    /* ========== 模拟API结束 ========== */
    
    // 真实API调用（联调时启用）
    // await zoneApi.update(row.id, { status: row.status === 'active' ? 'inactive' : 'active' })
    
    ElMessage.success(`${action}成功`)
    loadZoneList()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('操作失败')
    }
  }
}

const handleDeleteZone = async (row) => {
  try {
    await ElMessageBox.confirm('确认删除该围栏？', '提示', {
      type: 'warning'
    })
    
    /* ========== 使用模拟API（测试用，联调时改为真实API） ========== */
    await zoneApiMock.delete(row.id)
    /* ========== 模拟API结束 ========== */
    
    // 真实API调用（联调时启用）
    // await zoneApi.delete(row.id)
    
    ElMessage.success('删除成功')
    loadZoneList()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const handleSubmitZone = async () => {
  if (!zoneFormRef.value) return
  
  await zoneFormRef.value.validate(async (valid) => {
    if (valid) {
      try {
        /* ========== 使用模拟API（测试用，联调时改为真实API） ========== */
        if (zoneForm.id) {
          await zoneApiMock.update(zoneForm.id, zoneForm)
        } else {
          await zoneApiMock.create({ ...zoneForm, cameraId: currentCamera.value.id })
        }
        /* ========== 模拟API结束 ========== */
        
        // 真实API调用（联调时启用）
        // if (zoneForm.id) {
        //   await zoneApi.update(zoneForm.id, zoneForm)
        // } else {
        //   await zoneApi.create({ ...zoneForm, cameraId: currentCamera.value.id })
        // }
        
        ElMessage.success('保存成功')
        zoneDialogVisible.value = false
        loadZoneList()
      } catch (error) {
        ElMessage.error('保存失败')
      }
    }
  })
}

const handleRefreshZones = () => {
  loadZoneList()
}

loadCameraTree()
</script>

<style scoped>
.perimeter-config {
  width: 100%;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

.card-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

.card-actions {
  flex-shrink: 0;
  display: flex;
  gap: 10px;
}

.tree-node {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  padding-right: 10px;
}

.node-actions {
  margin-left: 10px;
}

.empty-area {
  height: 280px;
  display: flex;
  justify-content: center;
  align-items: center;
}

.video-area {
  width: 100%;
  height: 280px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  overflow: hidden;
}

.video-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  color: #909399;
  background: #f5f5f5;
}

.coord-area {
  width: 100%;
}

.coord-area p {
  margin-bottom: 10px;
  color: #909399;
  font-size: 12px;
}
</style>