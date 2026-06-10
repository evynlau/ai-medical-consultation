/** 影像分析 API 客户端 */
import http from './http'

/**
 * 上传胸片进行肺炎分析
 * @param {FormData} formData - 包含 file 等字段
 * @returns {Promise}
 */
export const analyzePneumonia = (formData) => {
  return http.post('/imaging/pneumonia/analyze', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
}

/**
 * 获取分析历史
 * @param {Object} params - { patient_id, doctor_id, limit, offset }
 */
export const getAnalysisHistory = (params) => {
  return http.get('/imaging/history', { params })
}

/**
 * 获取分析详情
 * @param {number} id
 */
export const getAnalysisDetail = (id) => {
  return http.get(`/imaging/${id}`)
}

/**
 * 提交医生标注
 * @param {number} id
 * @param {Object} data - { annotation, agreement, correct_label }
 */
export const submitAnnotation = (id, data) => {
  return http.post(`/imaging/${id}/annotate`, data)
}

/**
 * 获取标注列表
 * @param {number} analysisId
 */
export const getAnnotations = (analysisId) => {
  return http.get(`/imaging/${analysisId}/annotations`)
}

/**
 * 获取可用模型列表
 */
export const listModels = () => {
  return http.get('/imaging/models/list')
}