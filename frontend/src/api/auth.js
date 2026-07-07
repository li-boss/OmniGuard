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

/* ========== 模拟数据（测试用，联调时删除） ========== */
export const authApiMock = {
  async login(data) {
    await new Promise(resolve => setTimeout(resolve, 500))
    return {
      token: 'mock-token-' + Date.now(),
      user: {
        id: 1,
        username: data.username,
        role: 'admin'
      }
    }
  },

  async register(data) {
    await new Promise(resolve => setTimeout(resolve, 500))
    return {
      message: '注册成功'
    }
  },

  async refresh() {
    await new Promise(resolve => setTimeout(resolve, 300))
    return {
      token: 'mock-token-refreshed-' + Date.now()
    }
  }
}
/* ========== 模拟数据结束 ========== */