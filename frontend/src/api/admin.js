import http from './http'

export const adminApi = {
  // 仪表盘
  stats: () => http.get('/admin/stats'),

  // 问诊管理
  consultations: (params) => http.get('/admin/consultations', { params }),
  consultationDetail: (id) => http.get(`/admin/consultations/${id}`),
  doctorReply: (id, data) => http.post(`/admin/consultations/${id}/reply`, data),

  // 紧急看板
  emergency: (params) => http.get('/admin/emergency', { params }),

  // 用户管理
  users: (params) => http.get('/admin/users', { params }),
  updateUser: (id, data) => http.put(`/admin/users/${id}`, data),

  // 知识库管理
  createKnowledge: (data) => http.post('/admin/knowledge', data),
  updateKnowledge: (id, data) => http.put(`/admin/knowledge/${id}`, data),
  deleteKnowledge: (id) => http.delete(`/admin/knowledge/${id}`),
  reindex: () => http.post('/admin/knowledge/reindex'),

  // 异步重建索引(通用,知识库+名医录共用)
  reindexAsync: () => http.post('/admin/reindex'),
  reindexStatus: () => http.get('/admin/reindex/status'),
  reindexInfo: () => http.get('/admin/reindex/info'),

  // 名医录管理
  createDoctor: (data) => http.post('/admin/doctors', data),
  updateDoctor: (id, data) => http.put(`/admin/doctors/${id}`, data),
  deleteDoctor: (id) => http.delete(`/admin/doctors/${id}`)
}
