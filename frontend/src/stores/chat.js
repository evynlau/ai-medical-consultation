import { defineStore } from 'pinia'
import { consultApi } from '@/api/consult'

export const useChatStore = defineStore('chat', {
  state: () => ({
    currentConsultationId: null,
    currentConsultation: null,
    messages: [],
    consultationsList: [],
    isLoading: false,
    error: null,
    pendingContext: null  // 来自 OCR/报告等的初始上下文
  }),
  getters: {
    isInConsultation: (s) => !!s.currentConsultationId,
    hasPendingContext: (s) => !!s.pendingContext
  },
  actions: {
    async startConsultation(chiefComplaint) {
      this.isLoading = true
      this.error = null
      try {
        const cons = await consultApi.create({ chief_complaint: chiefComplaint })
        this.currentConsultationId = cons.id
        this.currentConsultation = cons
        this.messages = cons.messages || []
        return cons
      } catch (e) {
        this.error = e.message
        throw e
      } finally {
        this.isLoading = false
      }
    },

    async loadConsultation(id) {
      this.isLoading = true
      try {
        const cons = await consultApi.detail(id)
        this.currentConsultationId = cons.id
        this.currentConsultation = cons
        this.messages = cons.messages || []
        return cons
      } finally {
        this.isLoading = false
      }
    },

    async sendMessage(content) {
      if (!this.currentConsultationId) {
        await this.startConsultation(content)
        return
      }

      // 1. 立即显示用户消息
      const tempUser = {
        id: `temp_${Date.now()}`,
        role: 'user',
        content,
        created_at: new Date().toISOString()
      }
      this.messages.push(tempUser)

      this.isLoading = true
      try {
        // 2. 调 API
        const resp = await consultApi.sendMessage(this.currentConsultationId, {
          role: 'user',
          content,
          message_type: 'text'
        })

        // 3. 移除临时消息,用后端返回的为准
        this.messages = this.messages.filter((m) => m.id !== tempUser.id)
        this.messages.push(resp.message)
        this.currentConsultation = resp.consultation
        return resp
      } catch (e) {
        this.messages = this.messages.filter((m) => m.id !== tempUser.id)
        throw e
      } finally {
        this.isLoading = false
      }
    },

    async fetchList() {
      this.consultationsList = await consultApi.list()
      return this.consultationsList
    },

    clearCurrent() {
      this.currentConsultationId = null
      this.currentConsultation = null
      this.messages = []
    }
  }
})
