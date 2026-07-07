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

/* ========== 模拟数据（测试用，联调时删除） ========== */
export const dashboardApiMock = {
  async getSummary() {
    await new Promise(resolve => setTimeout(resolve, 500))
    return {
      todayAlarms: 23,
      activeCameras: 18,
      recognizedFaces: 156,
      activeZones: 12,
      alarmTrend: [
        { date: '01-15', count: 12 },
        { date: '01-16', count: 18 },
        { date: '01-17', count: 15 },
        { date: '01-18', count: 22 },
        { date: '01-19', count: 19 },
        { date: '01-20', count: 23 }
      ],
      alarmTypeDistribution: [
        { type: '人员入侵', count: 45 },
        { type: '越界行为', count: 32 },
        { type: '异常聚集', count: 18 }
      ]
    }
  }
}
/* ========== 模拟数据结束 ========== */