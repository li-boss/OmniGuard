import request from './request'

export const login = (payload) => request.post('/auth/login', payload)
export const register = (payload) => request.post('/auth/register', payload)
export const refreshToken = () => request.post('/auth/refresh')
export const getProfile = () => request.get('/auth/profile')
