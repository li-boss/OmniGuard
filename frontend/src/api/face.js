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

/* ========== 模拟数据（测试用，联调时删除） ========== */
export const faceApiMock = {
  mockFaces: [
    {
      id: 1,
      name: '张三',
      employeeId: 'EMP001',
      department: '技术部',
      position: '工程师',
      phone: '13800138001',
      photoUrl: '',
      status: 'active',
      createdAt: '2024-01-15 09:30:00'
    },
    {
      id: 2,
      name: '李四',
      employeeId: 'EMP002',
      department: '市场部',
      position: '经理',
      phone: '13800138002',
      photoUrl: '',
      status: 'active',
      createdAt: '2024-01-16 10:20:00'
    },
    {
      id: 3,
      name: '王五',
      employeeId: 'EMP003',
      department: '行政部',
      position: '主管',
      phone: '13800138003',
      photoUrl: '',
      status: 'inactive',
      createdAt: '2024-01-17 14:15:00'
    }
  ],

  async getList(params = {}) {
    await new Promise(resolve => setTimeout(resolve, 500))
    const { page = 1, pageSize = 10, keyword = '' } = params
    let filtered = this.mockFaces
    
    if (keyword) {
      filtered = filtered.filter(f => 
        f.name.includes(keyword) || f.employeeId.includes(keyword)
      )
    }
    
    return {
      list: filtered.slice((page - 1) * pageSize, page * pageSize),
      total: filtered.length
    }
  },

  async register(data) {
    await new Promise(resolve => setTimeout(resolve, 800))
    const newFace = {
      id: this.mockFaces.length + 1,
      ...data,
      createdAt: new Date().toLocaleString()
    }
    this.mockFaces.push(newFace)
    return { message: '注册成功', data: newFace }
  },

  async delete(id) {
    await new Promise(resolve => setTimeout(resolve, 500))
    this.mockFaces = this.mockFaces.filter(f => f.id !== id)
    return { message: '删除成功' }
  },

  async update(id, data) {
    await new Promise(resolve => setTimeout(resolve, 500))
    const index = this.mockFaces.findIndex(f => f.id === id)
    if (index !== -1) {
      this.mockFaces[index] = { ...this.mockFaces[index], ...data }
    }
    return { message: '更新成功' }
  },

  async getStats() {
    await new Promise(resolve => setTimeout(resolve, 300))
    return {
      totalFaces: this.mockFaces.length,
      todayRecognitions: 156,
      successRate: 95.5
    }
  },

  async getRecognitionLogs(id) {
    await new Promise(resolve => setTimeout(resolve, 300))
    return [
      {
        timestamp: '2024-01-20 09:15:30',
        location: '东门',
        confidence: 0.95
      },
      {
        timestamp: '2024-01-20 10:22:15',
        location: '西门',
        confidence: 0.92
      }
    ]
  }
}
/* ========== 模拟数据结束 ========== */