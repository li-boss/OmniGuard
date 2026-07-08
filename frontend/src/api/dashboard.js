import request from './request'

/**
 * 大盘统计接口 - IDashboard
 * 接口负责人：E
 * 文件：backend/api/dashboard_api.py
 * 调用者：A
 */

export const dashboardApi = {
  /**
   * 获取统计数据
   * GET /api/dashboard/summary
   */
  getSummary() {
    return request({
      url: '/dashboard/summary',
      method: 'GET'
    })
  }
}