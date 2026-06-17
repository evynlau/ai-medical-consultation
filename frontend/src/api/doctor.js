import http from './http'

export const doctorApi = {
  // 患者端
  list: (params) => http.get('/doctors', { params }),
  detail: (id) => http.get(`/doctors/${id}`),
  search: (q, topK = 10) => http.get('/doctors/search/query', { params: { q, top_k: topK } })
}

export const adminDoctorApi = {
  // 管理端
  create: (data) => http.post('/admin/doctors', data),
  update: (id, data) => http.put(`/admin/doctors/${id}`, data),
  remove: (id) => http.delete(`/admin/doctors/${id}`)
}
