/**
 * 移动端 API 封装
 * - 复用 FastAPI 后端(端口 8000)
 * - Token 存 uni.storage,带过期检测
 * - 401 自动跳登录
 */

// 后端地址:开发期指向本机 8000;打包时改为生产域名
// 注意:Android 真机/模拟器访问本机要用 10.0.2.2(模拟器) 或局域网 IP
// 这里留 TODO:部署时改
const BASE_URL = 'http://10.0.2.2:8000/api/v1'

// 登录态 key
const TOKEN_KEY = 'access_token'
const USER_KEY = 'user_profile'

export const getToken = () => uni.getStorageSync(TOKEN_KEY) || ''
export const setToken = (t) => uni.setStorageSync(TOKEN_KEY, t)
export const clearAuth = () => {
  uni.removeStorageSync(TOKEN_KEY)
  uni.removeStorageSync(USER_KEY)
}

export const getUser = () => uni.getStorageSync(USER_KEY) || null
export const setUser = (u) => uni.setStorageSync(USER_KEY, u)

/**
 * 通用请求(uni.request Promise 化)
 */
export const request = (options) => {
  return new Promise((resolve, reject) => {
    const token = getToken()
    uni.request({
      url: BASE_URL + options.url,
      method: options.method || 'GET',
      data: options.data || {},
      header: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(options.header || {}),
      },
      timeout: options.timeout || 30000,
      success: (res) => {
        // 401 → 跳登录
        if (res.statusCode === 401) {
          clearAuth()
          uni.showToast({ title: '登录已过期', icon: 'none' })
          uni.reLaunch({ url: '/pages/login/login' })
          return reject(new Error('未登录'))
        }
        // 2xx:resolve data
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data)
        } else {
          const msg = (res.data && (res.data.detail || res.data.message)) || `HTTP ${res.statusCode}`
          uni.showToast({ title: msg, icon: 'none', duration: 2500 })
          reject(new Error(msg))
        }
      },
      fail: (err) => {
        uni.showToast({ title: '网络异常', icon: 'none' })
        reject(err)
      },
    })
  })
}

// 业务 API 集合
export const api = {
  // 认证
  login: (data) => request({ url: '/auth/login', method: 'POST', data }),
  register: (data) => request({ url: '/auth/register', method: 'POST', data }),
  fetchProfile: () => request({ url: '/users/me' }),

  // 问诊
  listConsultations: (params) => request({ url: '/consultations', data: params }),
  getConsultation: (id) => request({ url: `/consultations/${id}` }),
  startConsultation: (data) => request({ url: '/consultations/start', method: 'POST', data }),
  sendMessage: (id, data) => request({ url: `/consultations/${id}/messages`, method: 'POST', data }),
  analyze: (data) => request({ url: '/agent/analyze', method: 'POST', data }),

  // 知识库
  listKnowledge: (params) => request({ url: '/knowledge', data: params }),
  searchKnowledge: (q) => request({ url: '/knowledge/search', data: { q } }),
  getKnowledge: (id) => request({ url: `/knowledge/${id}` }),

  // 名医录
  listDoctors: (params) => request({ url: '/doctors', data: params }),
  getDoctor: (id) => request({ url: `/doctors/${id}` }),

  // 胸片分析
  analyzeXray: (formData) => request({ url: '/imaging/analyze', method: 'POST', data: formData, header: { 'Content-Type': 'multipart/form-data' } }),

  // OCR
  ocrUpload: (formData) => request({ url: '/ocr/upload', method: 'POST', data: formData, header: { 'Content-Type': 'multipart/form-data' } }),
}
