import http from './http'

export const userApi = {
  register: (data) => http.post('/user/register', data),
  login: (data) => http.post('/user/login', data),
  me: () => http.get('/user/me'),
  updateMe: (data) => http.put('/user/me', data)
}
