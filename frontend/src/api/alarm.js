import request from './request'

/**
 * 告警查询与处置接口 - IAlarm
 * 接口负责人：E
 * 文件：backend/api/event_api.py, backend/models/alarm.py
 * 调用者：A / B / D
 */

export const alarmApi = {
  /**
   * 获取告警列表
   * GET /api/alarms?page=&type=&severity=
   */
  getList(params) {
    return request({
      url: '/alarms',
      method: 'GET',
      params
    })
  },

  /**
   * 处置告警
   * PUT /api/alarms/<id>/handle
   */
  handle(id, data) {
    return request({
      url: `/alarms/${id}/handle`,
      method: 'PUT',
      data
    })
  },

  /**
   * 获取告警视频片段
   * GET /api/alarms/<id>/clip
   */
  getClip(id) {
    return request({
      url: `/alarms/${id}/clip`,
      method: 'GET'
    })
  }
}