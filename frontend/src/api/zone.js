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

/* ========== 模拟数据（测试用，联调时删除） ========== */
export const zoneApiMock = {
  mockZones: [
    {
      id: 1,
      name: '禁区A',
      type: 'forbidden',
      alarmLevel: 'high',
      status: 'active',
      description: '机房重地，禁止进入',
      coordinates: '[[100,100],[200,100],[200,200],[100,200]]',
      cameraId: 1
    },
    {
      id: 2,
      name: '警戒区B',
      type: 'warning',
      alarmLevel: 'medium',
      status: 'active',
      description: '仓库区域，注意安全',
      coordinates: '[[300,100],[400,100],[400,200],[300,200]]',
      cameraId: 1
    }
  ],

  mockCameras: [
    {
      id: 1,
      name: '东门摄像头',
      status: 'online'
    },
    {
      id: 2,
      name: '西门摄像头',
      status: 'online'
    },
    {
      id: 3,
      name: '北门摄像头',
      status: 'offline'
    }
  ],

  async getList(params = {}) {
    await new Promise(resolve => setTimeout(resolve, 500))
    const { cameraId } = params
    let filtered = this.mockZones
    if (cameraId) {
      filtered = filtered.filter(z => z.cameraId === cameraId)
    }
    return filtered
  },

  async create(data) {
    await new Promise(resolve => setTimeout(resolve, 500))
    const newZone = {
      id: this.mockZones.length + 1,
      ...data,
      status: 'active'
    }
    this.mockZones.push(newZone)
    return { message: '创建成功', data: newZone }
  },

  async update(id, data) {
    await new Promise(resolve => setTimeout(resolve, 500))
    const index = this.mockZones.findIndex(z => z.id === id)
    if (index !== -1) {
      this.mockZones[index] = { ...this.mockZones[index], ...data }
    }
    return { message: '更新成功' }
  },

  async delete(id) {
    await new Promise(resolve => setTimeout(resolve, 500))
    this.mockZones = this.mockZones.filter(z => z.id !== id)
    return { message: '删除成功' }
  },

  async getCameraTree() {
    await new Promise(resolve => setTimeout(resolve, 300))
    return this.mockCameras
  }
}
/* ========== 模拟数据结束 ========== */