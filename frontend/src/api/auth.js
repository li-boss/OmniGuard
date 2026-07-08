import request from './request'

/**
 * 鉴权接口 - IAuth
 * 接口负责人：C
 * 文件：backend/api/user_api.py, backend/middleware/auth_middleware.py
 * 调用者：A / B
 */

export const authApi = {
  /**
   * 用户注册
   * POST /api/auth/register
   */
  register(data) {
    return request({
      url: '/auth/register',
      method: 'POST',
      data
    })
  },

  /**
   * 用户登录
   * POST /api/auth/login
   * @returns {token: string, user: object}
   */
  login(data) {
    return request({
      url: '/auth/login',
      method: 'POST',
      data
    })
  },

  /**
   * 刷新token
   * POST /api/auth/refresh
   */
  refresh() {
    return request({
      url: '/auth/refresh',
      method: 'POST'
    })
  }
}