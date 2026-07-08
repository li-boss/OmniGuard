import request from './request'

/**
 * 人脸管理接口 - IFace
 * 接口负责人：C
 * 文件：backend/api/face_api.py, backend/models/face.py
 * 调用者：A / D
 */

export const faceApi = {
  /**
   * 注册人脸
   * POST /api/faces/register
   */
  register(data) {
    return request({
      url: '/faces/register',
      method: 'POST',
      data
    })
  },

  /**
   * 获取人脸列表
   * GET /api/faces
   */
  getList(params) {
    return request({
      url: '/faces',
      method: 'GET',
      params
    })
  },

  /**
   * 删除人脸
   * DELETE /api/faces/<id>
   */
  delete(id) {
    return request({
      url: `/faces/${id}`,
      method: 'DELETE'
    })
  },

  /**
   * 更新人脸信息
   * PUT /api/faces/<id>
   */
  update(id, data) {
    return request({
      url: `/faces/${id}`,
      method: 'PUT',
      data
    })
  },

  /**
   * 获取人脸统计信息
   */
  getStats() {
    return request({
      url: '/faces/stats',
      method: 'GET'
    })
  },

  /**
   * 获取人脸识别记录
   * GET /api/faces/<id>/logs
   */
  getRecognitionLogs(id) {
    return request({
      url: `/faces/${id}/logs`,
      method: 'GET'
    })
  }
}