import request from './request'

export function getAccessLogs(params) {
  return request.get('/access-logs', { params })
}

export function getAccessLogDetail(id) {
  return request.get(`/access-logs/${id}`)
}

export function deleteAccessLog(id) {
  return request.delete(`/access-logs/${id}`)
}