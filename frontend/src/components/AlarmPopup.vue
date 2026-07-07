<template>
  <aside v-if="alarm" class="alarm-popup">
    <strong>{{ alarm.type }}</strong>
    <span>{{ alarm.level }} - {{ alarm.camera_id }}</span>
  </aside>
</template>

<script setup>
defineProps({
  alarm: {
    type: Object,
    default: null
  }
})
</script>

<style scoped>
.alarm-popup {
  position: fixed;
  right: 24px;
  bottom: 24px;
  width: min(360px, calc(100vw - 48px));
  display: grid;
  gap: 6px;
  padding: 16px;
  color: #7a1f1f;
  background: #fff3f3;
  border: 1px solid #ffd1d1;
  border-radius: 8px;
  box-shadow: 0 12px 32px rgb(20 29 47 / 18%);
}
</style>
