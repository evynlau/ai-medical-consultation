import { defineStore } from 'pinia'
import { userApi } from '@/api/user'

export const useUserStore = defineStore('user', {
  state: () => ({
    token: localStorage.getItem('token') || '',
    profile: null
  }),
  getters: {
    isLogin: (state) => !!state.token,
    displayName: (state) => state.profile?.full_name || state.profile?.username || '访客'
  },
  actions: {
    async login(payload) {
      const { access_token, user } = await userApi.login(payload)
      this.token = access_token
      this.profile = user
      localStorage.setItem('token', access_token)
      return user
    },
    async register(payload) {
      const { access_token, user } = await userApi.register(payload)
      this.token = access_token
      this.profile = user
      localStorage.setItem('token', access_token)
      return user
    },
    async fetchProfile() {
      if (!this.token) return null
      try {
        this.profile = await userApi.me()
        return this.profile
      } catch {
        this.logout()
        return null
      }
    },
    logout() {
      this.token = ''
      this.profile = null
      localStorage.removeItem('token')
    }
  }
})
