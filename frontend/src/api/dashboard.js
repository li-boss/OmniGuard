import request from './request'

export const getDashboardSummary = () => request.get('/dashboard/summary')
export const getAlarmTrend = (params) => request.get('/dashboard/alarm-trend', { params })
export const getDisposalRate = (params) => request.get('/dashboard/disposal-rate', { params })
