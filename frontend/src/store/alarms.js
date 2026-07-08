import { defineStore } from 'pinia'

import * as alarmApi from '../api/alarm'

export const useAlarmsStore = defineStore('alarms', {
  state: () => ({
    items: [],
    total: 0,
    popup: null,
  }),
  actions: {
    async fetch(params = {}) {
      const result = await alarmApi.getAlarms(params)
      this.items = result.data.items
      this.total = result.data.total
      return result.data
    },
    async simulate(payload) {
      const result = await alarmApi.createAlarm(payload)
      this.receiveAlarm(result.data)
      return result.data
    },
    async handle(id, note) {
      const result = await alarmApi.handleAlarm(id, { note })
      const index = this.items.findIndex((item) => item.id === id)
      if (index >= 0) {
        this.items[index] = result.data
      }
      return result.data
    },
    receiveAlarm(alarm) {
      if (!alarm?.id) return
      this.popup = alarm
      const exists = this.items.some((item) => item.id === alarm.id)
      if (!exists) {
        this.items = [alarm, ...this.items].slice(0, 50)
        this.total += 1
      }
    },
    closePopup() {
      this.popup = null
    },
  },
})
