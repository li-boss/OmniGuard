import request from './request'

export function getFaces() {
  return request.get('/faces')
}

export function registerFace(payload) {
  return request.post('/faces/register', payload)
}

export function deleteFace(id) {
  return request.delete(`/faces/${id}`)
}
