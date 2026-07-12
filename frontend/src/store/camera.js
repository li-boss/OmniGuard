import { defineStore } from 'pinia'
import { getStreamConfig, toggleCam1Source } from '../api/stream'

export const useCameraStore = defineStore('camera', {
  state: () => ({
    selectedCameraId: 'cam-1',
    cameras: [
      {
        id: 'cam-1',
        name: '电脑摄像头',
        streamUrl: '/api/streams/cam-1.mjpg',
        isLocal: false,
      },
      {
        id: 'cam-2',
        name: '手机摄像头 (RTMP)',
        streamUrl: '/api/streams/cam-2.mjpg',
        isLocal: false,
      },
    ],
  }),
  getters: {
    selectedCamera(state) {
      return state.cameras.find((camera) => camera.id === state.selectedCameraId) || state.cameras[0]
    },
  },
  actions: {
    select(cameraId) {
      this.selectedCameraId = cameraId
    },
    async fetchConfig() {
      try {
        const res = await getStreamConfig()
        if (res.code === 0 && res.data) {
          const cam1Source = res.data['cam-1'] || ''
          const isLocal = !cam1Source.startsWith('rtmp://')
          
          const cam1 = this.cameras.find(c => c.id === 'cam-1')
          if (cam1) {
            cam1.isLocal = isLocal
            cam1.name = isLocal ? '电脑摄像头 (本地直连)' : '电脑摄像头 (RTMP)'
          }
        }
      } catch (err) {
        console.error('Failed to fetch stream config:', err)
      }
    },
    async toggleSource() {
      try {
        const res = await toggleCam1Source()
        if (res.code === 0) {
          await this.fetchConfig()
          return res.data
        }
      } catch (err) {
        console.error('Failed to toggle camera source:', err)
        throw err
      }
    }
  },
})
