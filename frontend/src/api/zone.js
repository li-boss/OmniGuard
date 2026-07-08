import request from './request'

/**
 * 围栏配置接口 - IZone
 * 接口负责人：D
 * 文件：backend/api/rule_api.py, backend/models/zone.py
 * 调用者：A / B / D自己
 */

export const zoneApi = {
  /**
   * 获取围栏列表
   * GET /api/zones?camera_id=
   */
  getList(params) {
    return request({
      url: '/zones',
      method: 'GET',
      params
    })
  },

  /**
   * 创建围栏
   * POST /api/zones
   */
  create(data) {
    return request({
      url: '/zones',
      method: 'POST',
      data
    })
  },

  /**
   * 更新围栏
   * PUT /api/zones/<id>
   */
  update(id, data) {
    return request({
      url: `/zones/${id}`,
      method: 'PUT',
      data
    })
  },

  /**
   * 删除围栏
   * DELETE /api/zones/<id>
   */
  delete(id) {
    return request({
      url: `/zones/${id}`,
      method: 'DELETE'
    })
  }
}