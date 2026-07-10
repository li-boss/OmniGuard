import { defineStore } from 'pinia'

export const useCameraStore = defineStore('camera', {
  state: () => ({
    selectedCameraId: 'cam-1',
    cameras: [
      {
        id: 'cam-1',
        name: '校园主入口',
        streamUrl: '/api/streams/demo.mjpg',
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
