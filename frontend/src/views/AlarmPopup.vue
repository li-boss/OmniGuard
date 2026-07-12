<script setup>
2import { computed } from 'vue'
3import { BellRing, X } from '@lucide/vue'
4
5import { useAlarmsStore } from '../store/alarms'
6
7const alarms = useAlarmsStore()
8const alarm = computed(() => alarms.popup)
9</script>
10
11<template>
12  <transition name="popup">
13    <aside v-if="alarm" class="alarm-popup">
14      <div class="popup-icon">
15        <BellRing />
16      </div>
17-      <div>
18+      <div class="popup-body">
19        <strong>{{ alarm.title }}</strong>
20        <span>{{ alarm.cameraId }} / {{ alarm.severity }}</span>
21        <small>{{ alarm.description || alarm.occurredAt }}</small>
22+        <img
23+          v-if="alarm.snapshotUrl || alarm.snapshot_path"
24+          :src="alarm.snapshotUrl || alarm.snapshot_path"
25+          alt="告警快照"
26+          class="popup-snapshot"
27+        />
28      </div>
29      <el-tooltip content="关闭" placement="top">
30        <button class="icon-button" type="button" @click="alarms.closePopup">
31          <X />
32        </button>
33      </el-tooltip>
34    </aside>
35  </transition>
36</template>
37+
38+<style scoped>
39+.popup-snapshot {
40+  width: 100%;
41+  max-height: 120px;
42+  object-fit: cover;
43+  border-radius: 4px;
44+  margin-top: 6px;
45+}
46+</style>