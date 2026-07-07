<template>
  <div class="face-access">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>人脸管理</span>
          <div class="header-actions">
            <el-input
              v-model="searchKeyword"
              placeholder="搜索姓名或工号"
              style="width: 200px; margin-right: 10px;"
              clearable
            />
            <el-button type="primary" @click="handleAddFace">注册人脸</el-button>
            <el-button @click="handleBatchImport">批量导入</el-button>
          </div>
        </div>
      </template>
      
      <el-row :gutter="20">
        <el-col :span="6">
          <el-card shadow="never">
            <template #header>
              <span>统计信息</span>
            </template>
            <div class="stat-box">
              <div class="stat-item">
                <div class="stat-label">已注册人脸</div>
                <div class="stat-value">{{ stats.totalFaces }}</div>
              </div>
              <div class="stat-item">
                <div class="stat-label">今日识别</div>
                <div class="stat-value">{{ stats.todayRecognitions }}</div>
              </div>
              <div class="stat-item">
                <div class="stat-label">识别成功率</div>
                <div class="stat-value">{{ stats.successRate }}%</div>
              </div>
            </div>
          </el-card>
        </el-col>
        
        <el-col :span="18">
          <el-table
            :data="faceList"
            style="width: 100%"
            v-loading="loading"
          >
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column label="人脸照片" width="100">
              <template #default="{ row }">
                <el-avatar :size="60" :src="row.photoUrl">
                  <el-icon><UserFilled /></el-icon>
                </el-avatar>
              </template>
            </el-table-column>
            <el-table-column prop="name" label="姓名" width="120" />
            <el-table-column prop="employeeId" label="工号" width="120" />
            <el-table-column prop="department" label="部门" width="150" />
            <el-table-column prop="position" label="职位" width="120" />
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="row.status === 'active' ? 'success' : 'info'">
                  {{ row.status === 'active' ? '启用' : '禁用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="createdAt" label="注册时间" width="180" />
            <el-table-column label="操作" width="200">
              <template #default="{ row }">
                <el-button size="small" @click="handleViewFace(row)">查看</el-button>
                <el-button size="small" @click="handleEditFace(row)">编辑</el-button>
                <el-button size="small" type="danger" @click="handleDeleteFace(row)">删除</el-button>
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
        </el-col>
      </el-row>
    </el-card>
    
    <el-dialog v-model="faceDialogVisible" :title="faceForm.id ? '编辑人脸' : '注册人脸'" width="600px">
      <el-form :model="faceForm" :rules="faceRules" ref="faceFormRef" label-width="100px">
        <el-form-item label="人脸照片" prop="photoUrl">
          <el-upload
            class="face-uploader"
            :show-file-list="false"
            :before-upload="beforePhotoUpload"
          >
            <img v-if="faceForm.photoUrl" :src="faceForm.photoUrl" class="face-photo" />
            <el-icon v-else class="face-uploader-icon"><Plus /></el-icon>
          </el-upload>
          <div class="upload-tip">支持 jpg、png 格式，大小不超过 2MB</div>
        </el-form-item>
        <el-form-item label="姓名" prop="name">
          <el-input v-model="faceForm.name" placeholder="请输入姓名" />
        </el-form-item>
        <el-form-item label="工号" prop="employeeId">
          <el-input v-model="faceForm.employeeId" placeholder="请输入工号" />
        </el-form-item>
        <el-form-item label="部门" prop="department">
          <el-select v-model="faceForm.department" placeholder="请选择部门">
            <el-option label="技术部" value="tech" />
            <el-option label="市场部" value="market" />
            <el-option label="行政部" value="admin" />
            <el-option label="财务部" value="finance" />
          </el-select>
        </el-form-item>
        <el-form-item label="职位" prop="position">
          <el-input v-model="faceForm.position" placeholder="请输入职位" />
        </el-form-item>
        <el-form-item label="手机号">
          <el-input v-model="faceForm.phone" placeholder="请输入手机号" />
        </el-form-item>
        <el-form-item label="状态">
          <el-radio-group v-model="faceForm.status">
            <el-radio label="active">启用</el-radio>
            <el-radio label="inactive">禁用</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="faceDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmitFace" :loading="submitLoading">确定</el-button>
      </template>
    </el-dialog>
    
    <el-dialog v-model="detailDialogVisible" title="人脸详情" width="700px">
      <el-row :gutter="20">
        <el-col :span="8">
          <div class="detail-photo">
            <el-avatar :size="200" :src="currentFace.photoUrl">
              <el-icon><UserFilled /></el-icon>
            </el-avatar>
          </div>
        </el-col>
        <el-col :span="16">
          <el-descriptions :column="1" border>
            <el-descriptions-item label="姓名">{{ currentFace.name }}</el-descriptions-item>
            <el-descriptions-item label="工号">{{ currentFace.employeeId }}</el-descriptions-item>
            <el-descriptions-item label="部门">{{ currentFace.department }}</el-descriptions-item>
            <el-descriptions-item label="职位">{{ currentFace.position }}</el-descriptions-item>
            <el-descriptions-item label="手机号">{{ currentFace.phone || '-' }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="currentFace.status === 'active' ? 'success' : 'info'">
                {{ currentFace.status === 'active' ? '启用' : '禁用' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="注册时间">{{ currentFace.createdAt }}</el-descriptions-item>
          </el-descriptions>
        </el-col>
      </el-row>
      
      <div style="margin-top: 20px;">
        <h4>最近识别记录</h4>
        <el-table :data="currentFace.recentLogs || []" style="width: 100%">
          <el-table-column prop="timestamp" label="识别时间" width="180" />
          <el-table-column prop="location" label="识别位置" />
          <el-table-column prop="confidence" label="置信度">
            <template #default="{ row }">
              {{ (row.confidence * 100).toFixed(2) }}%
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UserFilled, Plus } from '@element-plus/icons-vue'
import { faceApi, faceApiMock } from '@/api/face'

const loading = ref(false)
const submitLoading = ref(false)
const searchKeyword = ref('')
const currentPage = ref(1)
const pageSize = ref(10)
const total = ref(0)

const faceList = ref([])

const stats = reactive({
  totalFaces: 0,
  todayRecognitions: 0,
  successRate: 0
})

const faceDialogVisible = ref(false)
const detailDialogVisible = ref(false)
const faceFormRef = ref(null)
const currentFace = ref({})

const faceForm = reactive({
  id: null,
  photoUrl: '',
  name: '',
  employeeId: '',
  department: '',
  position: '',
  phone: '',
  status: 'active'
})

const faceRules = {
  name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  employeeId: [{ required: true, message: '请输入工号', trigger: 'blur' }],
  department: [{ required: true, message: '请选择部门', trigger: 'change' }],
  position: [{ required: true, message: '请输入职位', trigger: 'blur' }]
}

const beforePhotoUpload = (file) => {
  const isJPG = file.type === 'image/jpeg'
  const isPNG = file.type === 'image/png'
  const isLt2M = file.size / 1024 / 1024 < 2

  if (!isJPG && !isPNG) {
    ElMessage.error('上传图片只能是 JPG/PNG 格式!')
    return false
  }
  if (!isLt2M) {
    ElMessage.error('上传图片大小不能超过 2MB!')
    return false
  }
  
  // TODO: 上传图片到服务器
  // const formData = new FormData()
  // formData.append('file', file)
  // const response = await uploadApi.upload(formData)
  // faceForm.photoUrl = response.data.url
  
  return false
}

const loadFaceList = async () => {
  loading.value = true
  try {
    /* ========== 使用模拟API（测试用，联调时改为真实API） ========== */
    const response = await faceApiMock.getList({
      page: currentPage.value,
      pageSize: pageSize.value,
      keyword: searchKeyword.value
    })
    /* ========== 模拟API结束 ========== */
    
    // 真实API调用（联调时启用）
    // const response = await faceApi.getList({
    //   page: currentPage.value,
    //   pageSize: pageSize.value,
    //   keyword: searchKeyword.value
    // })
    
    faceList.value = response.list
    total.value = response.total
  } catch (error) {
    ElMessage.error('加载人脸列表失败')
  } finally {
    loading.value = false
  }
}

const loadStats = async () => {
  try {
    /* ========== 使用模拟API（测试用，联调时改为真实API） ========== */
    const data = await faceApiMock.getStats()
    /* ========== 模拟API结束 ========== */
    
    // 真实API调用（联调时启用）
    // const data = await faceApi.getStats()
    
    Object.assign(stats, data)
  } catch (error) {
    console.error('加载统计信息失败')
  }
}

const handleSizeChange = () => {
  currentPage.value = 1
  loadFaceList()
}

const handleCurrentChange = () => {
  loadFaceList()
}

const handleAddFace = () => {
  faceForm.id = null
  faceForm.photoUrl = ''
  faceForm.name = ''
  faceForm.employeeId = ''
  faceForm.department = ''
  faceForm.position = ''
  faceForm.phone = ''
  faceForm.status = 'active'
  faceDialogVisible.value = true
}

const handleViewFace = async (row) => {
  currentFace.value = { ...row, recentLogs: [] }
  detailDialogVisible.value = true
  
  /* ========== 使用模拟API（测试用，联调时改为真实API） ========== */
  const logs = await faceApiMock.getRecognitionLogs(row.id)
  currentFace.value.recentLogs = logs
  /* ========== 模拟API结束 ========== */
  
  // 真实API调用（联调时启用）
  // const logs = await faceApi.getRecognitionLogs(row.id)
  // currentFace.value.recentLogs = logs
}

const handleEditFace = (row) => {
  Object.assign(faceForm, row)
  faceDialogVisible.value = true
}

const handleDeleteFace = async (row) => {
  try {
    await ElMessageBox.confirm('确认删除该人脸记录？删除后无法恢复', '提示', {
      type: 'warning'
    })
    
    /* ========== 使用模拟API（测试用，联调时改为真实API） ========== */
    await faceApiMock.delete(row.id)
    /* ========== 模拟API结束 ========== */
    
    // 真实API调用（联调时启用）
    // await faceApi.delete(row.id)
    
    ElMessage.success('删除成功')
    loadFaceList()
    loadStats()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const handleSubmitFace = async () => {
  if (!faceFormRef.value) return
  
  await faceFormRef.value.validate(async (valid) => {
    if (valid) {
      submitLoading.value = true
      try {
        /* ========== 使用模拟API（测试用，联调时改为真实API） ========== */
        if (faceForm.id) {
          await faceApiMock.update(faceForm.id, faceForm)
        } else {
          await faceApiMock.register(faceForm)
        }
        /* ========== 模拟API结束 ========== */
        
        // 真实API调用（联调时启用）
        // if (faceForm.id) {
        //   await faceApi.update(faceForm.id, faceForm)
        // } else {
        //   await faceApi.register(faceForm)
        // }
        
        ElMessage.success('保存成功')
        faceDialogVisible.value = false
        loadFaceList()
        loadStats()
      } catch (error) {
        ElMessage.error('保存失败')
      } finally {
        submitLoading.value = false
      }
    }
  })
}

const handleBatchImport = () => {
  ElMessage.info('批量导入功能待实现')
}

loadFaceList()
loadStats()
</script>

<style scoped>
.face-access {
  width: 100%;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-actions {
  display: flex;
  align-items: center;
}

.stat-box {
  padding: 10px 0;
}

.stat-item {
  margin-bottom: 20px;
  text-align: center;
}

.stat-label {
  font-size: 14px;
  color: #909399;
  margin-bottom: 5px;
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
  color: #409eff;
}

.face-uploader {
  border: 1px dashed #d9d9d9;
  border-radius: 6px;
  cursor: pointer;
  position: relative;
  overflow: hidden;
  width: 178px;
  height: 178px;
}

.face-uploader:hover {
  border-color: #409eff;
}

.face-uploader-icon {
  font-size: 28px;
  color: #8c939d;
  width: 178px;
  height: 178px;
  display: flex;
  justify-content: center;
  align-items: center;
}

.face-photo {
  width: 178px;
  height: 178px;
  display: block;
}

.upload-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 10px;
}

.detail-photo {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 200px;
}
</style>
