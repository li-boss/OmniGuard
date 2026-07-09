import axios from 'axios'

const request = axios.create({
  baseURL: '/api',
  timeout: 12000,
})

request.interceptors.request.use((config) => {
  const token = localStorage.getItem('smart-campus-token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

request.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('smart-campus-token')
      // If not already on the login page, redirect the user to login
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  },
)

export default request
