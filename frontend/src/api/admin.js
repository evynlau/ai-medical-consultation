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
  reindex: () => http.post('/admin/knowledge/reindex')
}
