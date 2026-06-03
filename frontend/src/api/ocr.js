import http from './http'

export const ocrApi = {
  upload: (formData) => http.post('/ocr/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),
  records: (params) => http.get('/ocr/records', { params }),
  record: (id) => http.get(`/ocr/records/${id}`),
  remove: (id) => http.delete(`/ocr/records/${id}`)
}
