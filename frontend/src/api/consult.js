import http from './http'

export const consultApi = {
  create: (data) => http.post('/consult', data),
  list: (params) => http.get('/consult', { params }),
  detail: (id) => http.get(`/consult/${id}`),
  sendMessage: (id, data) => http.post(`/consult/${id}/messages`, data),
  close: (id) => http.post(`/consult/${id}/close`)
}
