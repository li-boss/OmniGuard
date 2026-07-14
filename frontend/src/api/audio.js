import request from './request'

export function getAudioStatus() {
  return request({
    url: '/multimodal/audio-status',
    method: 'get',
  })
}

export function analyzeAudioChunk(formData) {
  return request({
    url: '/multimodal/analyze-wav',
    method: 'post',
    data: formData,
    timeout: 30000,
  })
}
