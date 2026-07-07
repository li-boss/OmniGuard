import { defineStore } from 'pinia'
import { listAlarms } from '../api/alarm'

export const useAlarmsStore = defineStore('alarms', {
  state: () => ({
    items: [],
    latest: null,
    loading: false
  }),
  actions: {
    async fetch(params = {}) {
      this.loading = true
      try {
        const data = await listAlarms(params)
        this.items = data.items || data
      } finally {
        this.loading = false
      }
    },
    pushRealtimeAlarm(alarm) {
      this.latest = alarm
      this.items.unshift(alarm)
    }
  }
})
