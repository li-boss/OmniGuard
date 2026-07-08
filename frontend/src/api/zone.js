import request from './request'

export function getZones(params) {
  return request.get('/zones', { params })
}

export function createZone(payload) {
  return request.post('/zones', payload)
}

export function updateZone(id, payload) {
  return request.put(`/zones/${id}`, payload)
}

export function deleteZone(id) {
  return request.delete(`/zones/${id}`)
}
