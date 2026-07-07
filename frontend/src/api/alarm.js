import request from './request'

export const listAlarms = (params) => request.get('/alarms', { params })
export const getAlarm = (id) => request.get(`/alarms/${id}`)
export const updateAlarmStatus = (id, payload) => request.patch(`/alarms/${id}/status`, payload)
