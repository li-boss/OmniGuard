import { defineStore } from 'pinia'
import { login as loginApi, getProfile } from '../api/auth'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('access_token') || '',
    user: null
  }),
  getters: {
    isAuthenticated: (state) => Boolean(state.token)
  },
  actions: {
    async login(credentials) {
      const data = await loginApi(credentials)
      this.token = data.access_token
      this.user = data.user
      localStorage.setItem('access_token', data.access_token)
    },
    async loadProfile() {
      this.user = await getProfile()
    },
    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem('access_token')
    }
  }
})
