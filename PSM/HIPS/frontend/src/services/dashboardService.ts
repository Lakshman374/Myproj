import api from './api'
import { DashboardMetrics, Alert, ActivityLog } from '../types'

export const dashboardService = {
  async getMetrics(): Promise<DashboardMetrics> {
    const response = await api.get<DashboardMetrics>('/metrics/dashboard')
    return response.data
  },

  async getRecentAlerts(limit: number = 5): Promise<Alert[]> {
    const response = await api.get('/alerts', { params: { limit } })
    return response.data.alerts
  },

  async getRecentLogs(limit: number = 10): Promise<ActivityLog[]> {
    const response = await api.get('/logs', { params: { limit } })
    return response.data.logs
  },
}
