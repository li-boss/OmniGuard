<template>
  <router-view v-if="$route.path === '/login'" />
  <el-container v-else class="app-container">
    <el-header class="app-header">
      <div class="header-left">
        <h1>智慧校园安防系统</h1>
      </div>
      <div class="header-right">
        <el-dropdown>
          <span class="user-info">
            <el-icon><User /></el-icon>
            {{ username }}
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item divided @click="handleLogout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </el-header>
    
    <el-container>
      <el-aside width="200px" class="app-aside">
        <el-menu
          :default-active="$route.path"
          router
          class="aside-menu"
        >
          <el-menu-item index="/dashboard">
            <el-icon><DataLine /></el-icon>
            <span>数据概览</span>
          </el-menu-item>
          <el-menu-item index="/alarm-history">
            <el-icon><Bell /></el-icon>
            <span>告警历史</span>
          </el-menu-item>
          <el-menu-item index="/perimeter-config">
            <el-icon><Setting /></el-icon>
            <span>围栏配置</span>
          </el-menu-item>
          <el-menu-item index="/face-access">
            <el-icon><UserFilled /></el-icon>
            <span>人脸管理</span>
          </el-menu-item>
        </el-menu>
      </el-aside>
      
      <el-main class="app-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { User, DataLine, Bell, Setting, UserFilled } from '@element-plus/icons-vue'

const router = useRouter()
const username = ref('管理员')

onMounted(() => {
  const storedUsername = localStorage.getItem('username')
  if (storedUsername) {
    username.value = storedUsername
  }
})

const handleLogout = () => {
  localStorage.removeItem('token')
  localStorage.removeItem('username')
  router.push('/login')
}
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: 'Helvetica Neue', Helvetica, 'PingFang SC', 'Hiragino Sans GB',
    'Microsoft YaHei', '微软雅黑', Arial, sans-serif;
}

#app {
  width: 100vw;
  height: 100vh;
}
</style>

<style scoped>
.app-container {
  width: 100%;
  height: 100vh;
}

.app-header {
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
}

.header-left h1 {
  font-size: 20px;
  color: #303133;
  margin: 0;
}

.header-right {
  display: flex;
  align-items: center;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 5px;
  cursor: pointer;
  color: #606266;
}

.app-aside {
  background: #fff;
  border-right: 1px solid #e4e7ed;
}

.aside-menu {
  border: none;
}

.app-main {
  background: #f0f2f5;
  padding: 20px;
}
</style>
