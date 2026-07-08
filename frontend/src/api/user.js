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