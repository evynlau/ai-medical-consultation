import http from './http'

export const knowledgeApi = {
  list: (params) => http.get('/knowledge', { params }),
  detail: (id) => http.get(`/knowledge/${id}`),
  search: (q, topK = 5) => http.get('/knowledge/search/query', { params: { q, top_k: topK } }),
  reindex: () => http.post('/knowledge/reindex')
}
