import { defineStore } from 'pinia'

export const useCameraStore = defineStore('camera', {
  state: () => ({
    selectedCameraId: 'cam-1',
    cameras: [
      {
        id: 'cam-1',
        name: '电脑摄像头 (本地)',
        streamUrl: '/api/streams/cam-1.mjpg',
      },
      {
        id: 'cam-2',
        name: '手机摄像头 (RTMP)',
        streamUrl: '/api/streams/cam-2.mjpg',
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
  },
})
