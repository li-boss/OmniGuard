<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Trash2 } from '@lucide/vue'

import * as faceApi from '../api/face'

const faces = ref([])
const loading = ref(false)
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
  } finally {
    loading.value = false
  }
}

function pickImage(event) {
  const file = event.target.files?.[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = () => {
    form.image = reader.result
  }
  reader.readAsDataURL(file)
}

async function submit() {
  if (!form.studentId || !form.name || !form.image) {
    ElMessage.warning('请补全人脸信息')
    return
  }
  try {
    await faceApi.registerFace(form)
    ElMessage.success('人脸已录入')
    form.studentId = ''
    form.name = ''
    form.image = ''
    await load()
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '人脸录入失败')
  }
}

async function remove(face) {
  await faceApi.deleteFace(face.id)
  ElMessage.success('人脸已删除')
  await load()
}

onMounted(load)
</script>

<template>
  <div class="face-layout" v-loading="loading">
    <section class="panel">
      <div class="section-head">
        <h2>人脸录入</h2>
        <el-button type="primary" @click="submit">录入</el-button>
      </div>
      <el-form class="form-grid" label-position="top">
        <el-form-item label="学号">
          <el-input v-model="form.studentId" />
        </el-form-item>
        <el-form-item label="姓名">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="照片">
          <input accept="image/*" type="file" @change="pickImage" />
        </el-form-item>
      </el-form>
      <img v-if="form.image" class="preview-image" :src="form.image" alt="预览" />
    </section>

    <section class="face-grid">
      <article v-for="face in faces" :key="face.id" class="face-card">
        <img v-if="face.imagePreview" :src="face.imagePreview" alt="人脸" />
        <div class="avatar-fallback" v-else>{{ face.name.slice(0, 1) }}</div>
        <div>
          <strong>{{ face.name }}</strong>
          <span>{{ face.studentId }}</span>
        </div>
        <el-tooltip content="删除" placement="top">
          <el-button :icon="Trash2" circle @click="remove(face)" />
        </el-tooltip>
      </article>
      <el-empty v-if="!faces.length" description="暂无人脸" />
    </section>
  </div>
</template>
