<script setup>
import { computed } from 'vue'
import { BellRing, X } from '@lucide/vue'

import { useAlarmsStore } from '../store/alarms'

const alarms = useAlarmsStore()
const alarm = computed(() => alarms.popup)
</script>

<template>
  <transition name="popup">
    <aside v-if="alarm" class="alarm-popup">
      <div class="popup-icon">
        <BellRing />
      </div>
      <div>
        <strong>{{ alarm.title }}</strong>
        <span>{{ alarm.cameraId }} / {{ alarm.severity }}</span>
        <small>{{ alarm.description || alarm.occurredAt }}</small>
      </div>
      <el-tooltip content="关闭" placement="top">
        <button class="icon-button" type="button" @click="alarms.closePopup">
          <X />
        </button>
      </el-tooltip>
    </aside>
  </transition>
</template>
