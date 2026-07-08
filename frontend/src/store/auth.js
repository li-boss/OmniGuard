import { defineStore } from 'pinia'

import * as authApi from '../api/auth'

const TOKEN_KEY = 'smart-campus-token'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem(TOKEN_KEY) || '',
    user: null,
  }),
  actions: {
    setSession(token, user) {
      this.token = token
      this.user = user
      localStorage.setItem(TOKEN_KEY, token)
    },
    async login(payload) {
      const result = await authApi.login(payload)
      this.setSession(result.data.token, result.data.user)
      return result.data.user
    },
    async ensureUser() {
      if (!this.token) return null
      try {
        const result = await authApi.getMe()
        this.user = result.data
        return this.user
      } catch {
        this.logout()
        return null
      }
    },
    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem(TOKEN_KEY)
    },
  },
})
