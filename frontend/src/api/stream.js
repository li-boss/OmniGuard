import request from './request'

export function getStreamConfig() {
  return request({
    url: '/streams/config',
    method: 'get',
  })
}

export function toggleCam1Source() {
  return request({
    url: '/streams/cam-1/toggle_source',
    method: 'post',
  })
}
