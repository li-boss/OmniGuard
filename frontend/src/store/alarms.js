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
    async delete(id) {
      await alarmApi.deleteAlarm(id)
      this.items = this.items.filter((item) => item.id !== id)
      this.total = Math.max(0, this.total - 1)
    },
    receiveAlarm(alarm) {
      if (!alarm?.id) return
      const index = this.items.findIndex((item) => item.id === alarm.id)
      if (index >= 0) {
        const updatedAlarm = { ...this.items[index], ...alarm }
        this.items[index] = updatedAlarm
        this.popup = updatedAlarm
      } else {
        this.popup = alarm
        this.items = [alarm, ...this.items].slice(0, 50)
        this.total += 1
      }
    },
    closePopup() {
      this.popup = null
    },
  },
})
