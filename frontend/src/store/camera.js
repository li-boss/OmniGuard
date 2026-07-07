import { defineStore } from 'pinia'
import { listZones } from '../api/zone'

export const useCameraStore = defineStore('camera', {
  state: () => ({
    activeCameraId: '',
    zones: []
  }),
  actions: {
    setActiveCamera(cameraId) {
      this.activeCameraId = cameraId
    },
    async fetchZones(params = {}) {
      const data = await listZones(params)
      this.zones = data.items || data
    }
  }
})
