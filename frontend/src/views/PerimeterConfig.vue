<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import CanvasDraw from '../components/CanvasDraw.vue'
import * as zoneApi from '../api/zone'

const loading = ref(false)
const zones = ref([])
const form = reactive({
  cameraId: 'cam-1',
  name: '主入口电子围栏',
  ruleType: 'intrusion',
  points: [],
})

async function load() {
  loading.value = true
  try {
    const result = await zoneApi.getZones({ camera_id: form.cameraId })
    zones.value = result.data
  } finally {
    loading.value = false
  }
}

async function save() {
  if (form.points.length < 3) {
    ElMessage.warning('至少需要 3 个点')
    return
  }
  await zoneApi.createZone({ ...form })
  ElMessage.success('围栏已保存')
  form.points = []
  await load()
}

async function remove(zone) {
  await zoneApi.deleteZone(zone.id)
  ElMessage.success('围栏已删除')
  await load()
}

onMounted(load)
</script>

<template>
  <div class="zone-layout" v-loading="loading">
    <section class="panel">
      <div class="section-head">
        <h2>电子围栏</h2>
        <el-button type="primary" @click="save">保存</el-button>
      </div>
      <el-form class="compact-form" label-position="top">
        <el-form-item label="摄像头">
          <el-input v-model="form.cameraId" @change="load" />
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="form.name" />
        </el-form-item>
      </el-form>
      <CanvasDraw v-model="form.points" />
    </section>

    <section class="panel">
      <div class="section-head">
        <h2>围栏列表</h2>
      </div>
      <div class="list-stack">
        <article v-for="zone in zones" :key="zone.id" class="list-row">
          <div>
            <strong>{{ zone.name }}</strong>
            <span>{{ zone.cameraId }} / {{ zone.points.length }} 点</span>
          </div>
          <el-button size="small" @click="remove(zone)">删除</el-button>
        </article>
        <el-empty v-if="!zones.length" description="暂无围栏" />
      </div>
    </section>
  </div>
</template>
