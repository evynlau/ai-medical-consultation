/** 影像分析 API 客户端 */
import request from './request'

/**
 * 上传胸片进行肺炎分析
 * @param {FormData} formData - 包含 file 等字段
 * @returns {Promise}
 */
export const analyzePneumonia = (formData) => {
  return request({
    url: '/imaging/pneumonia/analyze',
    method: 'post',
    data: formData,
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
  return request({
    url: '/imaging/history',
    method: 'get',
    params
  })
}

/**
 * 获取分析详情
 * @param {number} id
 */
export const getAnalysisDetail = (id) => {
  return request({
    url: `/imaging/${id}`,
    method: 'get'
  })
}

/**
 * 提交医生标注
 * @param {number} id
 * @param {Object} data - { annotation, agreement, correct_label }
 */
export const submitAnnotation = (id, data) => {
  return request({
    url: `/imaging/${id}/annotate`,
    method: 'post',
    data
  })
}

/**
 * 获取标注列表
 * @param {number} analysisId
 */
export const getAnnotations = (analysisId) => {
  return request({
    url: `/imaging/${analysisId}/annotations`,
    method: 'get'
  })
}

/**
 * 获取可用模型列表
 */
export const listModels = () => {
  return request({
    url: '/imaging/models/list',
    method: 'get'
  })
}