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

/* ========== 模拟数据（测试用，联调时删除） ========== */
export const alarmApiMock = {
  mockAlarms: [
    {
      id: 1,
      type: 'intrusion',
      severity: 'high',
      cameraName: '东门摄像头',
      zoneName: '禁区A',
      timestamp: '2024-01-20 09:15:30',
      status: 'pending',
      handler: null,
      note: null
    },
    {
      id: 2,
      type: 'crossing',
      severity: 'medium',
      cameraName: '西门摄像头',
      zoneName: '警戒区B',
      timestamp: '2024-01-20 10:22:15',
      status: 'completed',
      handler: '管理员',
      note: '已现场确认，无异常'
    },
    {
      id: 3,
      type: 'gathering',
      severity: 'low',
      cameraName: '北门摄像头',
      zoneName: '监控区C',
      timestamp: '2024-01-20 11:05:42',
      status: 'pending',
      handler: null,
      note: null
    }
  ],

  async getList(params = {}) {
    await new Promise(resolve => setTimeout(resolve, 500))
    const { page = 1, pageSize = 10, type, severity } = params
    let filtered = this.mockAlarms
    
    if (type) {
      filtered = filtered.filter(a => a.type === type)
    }
    if (severity) {
      filtered = filtered.filter(a => a.severity === severity)
    }
    
    return {
      list: filtered.slice((page - 1) * pageSize, page * pageSize),
      total: filtered.length
    }
  },

  async handle(id, data) {
    await new Promise(resolve => setTimeout(resolve, 500))
    const index = this.mockAlarms.findIndex(a => a.id === id)
    if (index !== -1) {
      this.mockAlarms[index] = {
        ...this.mockAlarms[index],
        status: data.action === 'ignore' ? 'ignored' : 'completed',
        handler: localStorage.getItem('username') || '管理员',
        note: data.note
      }
    }
    return { message: '处置成功' }
  },

  async getClip(id) {
    await new Promise(resolve => setTimeout(resolve, 300))
    return {
      clipUrl: '/mock/alarm-clip.mp4',
      duration: 30
    }
  }
}
/* ========== 模拟数据结束 ========== */