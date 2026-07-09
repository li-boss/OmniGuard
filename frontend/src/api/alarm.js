import request from './request'

export function getAlarms(params) {
  return request.get('/alarms', { params })
}

export function createAlarm(payload) {
  return request.post('/alarms', payload)
}

export function handleAlarm(id, payload) {
  return request.put(`/alarms/${id}/handle`, payload)
}

export function getAlarmClip(id) {
  return request.get(`/alarms/${id}/clip`)
}

export function deleteAlarm(id) {
  return request.delete(`/alarms/${id}`)
}
