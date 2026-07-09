import request from './request'

export function login(payload) {
  return request.post('/auth/login', payload)
}

export function register(payload) {
  return request.post('/auth/register', payload)
}

export function refreshToken() {
  return request.post('/auth/refresh')
}

export function getMe() {
  return request.get('/users/me')
}

export function changePassword(payload) {
  return request.put('/users/me/password', payload)
}
