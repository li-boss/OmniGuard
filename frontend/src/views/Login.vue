<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ShieldCheck } from '@lucide/vue'

import { useAuthStore } from '../store/auth'

const router = useRouter()
const auth = useAuthStore()
const loading = ref(false)
const form = reactive({
  username: 'admin',
  password: 'admin123',
})

async function submit() {
  loading.value = true
  try {
    await auth.login(form)
    router.push('/dashboard')
  } catch (error) {
    if (!error.response) {
      ElMessage.error('无法连接到后端服务，请等待系统模型加载完成（约10-15秒）')
    } else if (error.response.status === 401) {
      ElMessage.error('用户名或密码错误')
    } else {
      ElMessage.error(error.response.data?.message || '登录失败')
    }
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="login-page">
    <section class="login-panel">
      <div class="login-brand">
        <ShieldCheck />
        <div>
          <h1>智慧校园安防系统</h1>
          <p>实时视频分析监测控制台</p>
        </div>
      </div>

      <el-form label-position="top" @submit.prevent="submit">
        <el-form-item label="账号">
          <el-input v-model="form.username" autocomplete="username" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="form.password"
            autocomplete="current-password"
            show-password
            type="password"
            @keyup.enter="submit"
          />
        </el-form-item>
        <el-button :loading="loading" type="primary" class="full-button" @click="submit">
          登录
        </el-button>
      </el-form>
    </section>
  </main>
</template>
