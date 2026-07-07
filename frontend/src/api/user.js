import request from './request'

/**
 * 用户管理接口 - IUser
 * 接口负责人：C
 * 文件：backend/api/user_api.py, backend/models/user.py
 * 调用者：A / B
 */

export const userApi = {
  /**
   * 获取当前用户信息
   * GET /api/users/me
   */
  getCurrentUser() {
    return request({
      url: '/users/me',
      method: 'GET'
    })
  },

  /**
   * 修改密码
   * PUT /api/users/me/password
   */
  changePassword(data) {
    return request({
      url: '/users/me/password',
      method: 'PUT',
      data
    })
  }
}

/* ========== 模拟数据（测试用，联调时删除） ========== */
export const userApiMock = {
  async getCurrentUser() {
    await new Promise(resolve => setTimeout(resolve, 300))
    return {
      id: 1,
      username: localStorage.getItem('username') || 'admin',
      role: 'admin',
      email: 'admin@example.com',
      createdAt: '2024-01-01 10:00:00'
    }
  },

  async changePassword(data) {
    await new Promise(resolve => setTimeout(resolve, 500))
    return {
      message: '密码修改成功'
    }
  }
}
/* ========== 模拟数据结束 ========== */