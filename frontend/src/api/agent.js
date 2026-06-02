import http from './http'

export const agentApi = {
  analyze: (data) => http.post('/agent/analyze', data),
  triage: (data) => http.post('/agent/triage', data)
}
