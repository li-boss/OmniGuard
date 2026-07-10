<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Trash2, UploadCloud, UserCheck } from '@lucide/vue'

import * as faceApi from '../api/face'

const faces = ref([])
const loading = ref(false)
const submitting = ref(false)
const form = reactive({
  studentId: '',
  name: '',
  image: '',
})

async function load() {
  loading.value = true
  try {
    const result = await faceApi.getFaces()
    faces.value = result.data
  } catch (error) {
    console.error('Failed to load faces:', error)
    ElMessage.error('获取人脸列表失败')
  } finally {
    loading.value = false
  }
}

function pickImage(event) {
  const file = event.target.files?.[0]
  if (!file) return
  
  // Validate file type
  if (!file.type.startsWith('image/')) {
    ElMessage.warning('请选择图片文件')
    return
  }
  
  // Validate size (limit to 5MB)
  if (file.size > 5 * 1024 * 1024) {
    ElMessage.warning('图片大小不能超过 5MB')
    return
  }

  const reader = new FileReader()
  reader.onload = () => {
    form.image = reader.result
    console.log('Image successfully loaded for preview, length:', reader.result.length)
  }
  reader.onerror = (err) => {
    console.error('FileReader error:', err)
    ElMessage.error('图片读取失败')
  }
  reader.readAsDataURL(file)
}

async function submit() {
  if (!form.studentId) {
    ElMessage.warning('请输入学号')
    return
  }
  if (!form.name) {
    ElMessage.warning('请输入姓名')
    return
  }
  if (!form.image) {
    ElMessage.warning('请选择并上传照片')
    return
  }

  submitting.value = true
  try {
    const result = await faceApi.registerFace(form)
    if (result.code === 0) {
      ElMessage.success(result.message || '人脸录入成功')
      form.studentId = ''
      form.name = ''
      form.image = ''
      // Reset the file input
      const fileInput = document.getElementById('face-file-input')
      if (fileInput) fileInput.value = ''
      await load()
    } else {
      ElMessage.error(result.message || '人脸录入失败')
    }
  } catch (error) {
    console.error('Face registration failed:', error)
    const errorMsg = error.response?.data?.message || '人脸录入失败，请重试'
    ElMessage.error(errorMsg)
  } finally {
    submitting.value = false
  }
}

async function remove(face) {
  loading.value = true
  try {
    await faceApi.deleteFace(face.id)
    ElMessage.success('人脸删除成功')
    await load()
  } catch (error) {
    console.error('Delete face failed:', error)
    ElMessage.error('删除人脸失败')
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="face-layout" v-loading="loading">
    <!-- Left panel: Registration Form -->
    <section class="panel" v-loading="submitting" element-loading-text="人脸特征提取中...">
      <div class="section-head">
        <h2>人脸录入</h2>
        <el-button type="primary" @click="submit" :loading="submitting">录入系统</el-button>
      </div>
      
      <el-form class="form-grid-vertical" label-position="top">
        <el-form-item label="学号 / 工号" required>
          <el-input v-model="form.studentId" placeholder="请输入唯一学号" />
        </el-form-item>
        <el-form-item label="姓名" required>
          <el-input v-model="form.name" placeholder="请输入真实姓名" />
        </el-form-item>
        
        <el-form-item label="人脸照片" required>
          <div class="upload-area">
            <input 
              id="face-file-input" 
              accept="image/*" 
              type="file" 
              @change="pickImage" 
              class="hidden-input" 
            />
            <label for="face-file-input" class="upload-trigger">
              <template v-if="!form.image">
                <UploadCloud class="upload-icon" />
                <span class="upload-text">点击选择照片</span>
                <span class="upload-tip">支持 JPG/PNG 格式，小于 5MB</span>
              </template>
              <template v-else>
                <div class="preview-container">
                  <img :src="form.image" class="preview-img-large" alt="人脸预览" />
                  <div class="preview-overlay">
                    <span>点击更换照片</span>
                  </div>
                </div>
              </template>
            </label>
          </div>
        </el-form-item>
      </el-form>
    </section>

    <!-- Right panel: Face database grid -->
    <section class="face-grid-container">
      <div class="section-head">
        <h2>已录入人脸库 ({{ faces.length }})</h2>
      </div>
      <div class="face-grid">
        <article v-for="face in faces" :key="face.id" class="face-card">
          <img v-if="face.imagePreview" :src="face.imagePreview" alt="人脸" class="face-card-img" />
          <div class="avatar-fallback" v-else>{{ face.name.slice(0, 1) }}</div>
          <div class="face-card-info">
            <strong class="face-name">{{ face.name }}</strong>
            <span class="face-id">{{ face.studentId }}</span>
          </div>
          <el-tooltip content="删除该人脸" placement="top">
            <el-button 
              :icon="Trash2" 
              circle 
              type="danger" 
              plain
              size="small"
              class="delete-btn"
              @click="remove(face)" 
            />
          </el-tooltip>
        </article>
      </div>
      <el-empty v-if="!faces.length" description="暂无人脸数据" />
    </section>
  </div>
</template>

<style scoped>
.form-grid-vertical {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.upload-area {
  width: 100%;
  border: 2px dashed #dcdfe6;
  border-radius: 8px;
  transition: border-color 0.2s;
  background: #fcfdfe;
}

.upload-area:hover {
  border-color: #409eff;
}

.hidden-input {
  display: none;
}

.upload-trigger {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 30px 20px;
  cursor: pointer;
  width: 100%;
  min-height: 200px;
}

.upload-icon {
  width: 48px;
  height: 48px;
  color: #909399;
  margin-bottom: 12px;
}

.upload-text {
  font-size: 14px;
  color: #303133;
  font-weight: 500;
  margin-bottom: 6px;
}

.upload-tip {
  font-size: 12px;
  color: #909399;
}

.preview-container {
  position: relative;
  width: 160px;
  height: 160px;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  border: 1px solid #e4e7ed;
}

.preview-img-large {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.preview-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.4);
  color: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.2s;
  font-size: 13px;
  font-weight: 500;
}

.preview-container:hover .preview-overlay {
  opacity: 1;
}

.face-grid-container {
  background: #ffffff;
  border: 1px solid #d8e2e8;
  border-radius: 8px;
  min-height: 400px;
}

.face-card-img {
  width: 56px;
  height: 56px;
  object-fit: cover;
  border-radius: 6px;
  border: 1px solid #e4e7ed;
}

.face-card-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.face-name {
  font-size: 14px;
  color: #303133;
}

.face-id {
  font-size: 12px;
  color: #909399;
}

.delete-btn {
  opacity: 0.8;
  transition: opacity 0.2s;
}

.delete-btn:hover {
  opacity: 1;
}
</style>
