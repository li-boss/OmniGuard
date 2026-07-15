import request from './request'

export function getAudioStatus() {
  return request.get('/audio-detection/status', {
    params: { _: Date.now() },
  })
}

export function getAudioDevices() {
  return request.get('/audio-detection/devices')
}

export function startAudioDetection(device) {
  return request.post('/audio-detection/start', { device }, { timeout: 300000 })
}

export function stopAudioDetection() {
  return request.post('/audio-detection/stop')
}
