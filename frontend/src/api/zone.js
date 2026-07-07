import request from './request'

export const listZones = (params) => request.get('/zones', { params })
export const createZone = (payload) => request.post('/zones', payload)
export const updateZone = (id, payload) => request.put(`/zones/${id}`, payload)
export const deleteZone = (id) => request.delete(`/zones/${id}`)
