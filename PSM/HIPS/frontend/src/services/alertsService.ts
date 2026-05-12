import api from './api'
import { Alert, BlockedAction } from '../types'

export interface AlertFilters {
  severity?: string
  status?: string
  category?: string
  start_date?: string
  end_date?: string
  limit?: number
  offset?: number
}

export const alertsService = {
  async getAlerts(filters: AlertFilters = {}) {
    const { data } = await api.get<{ total: number; alerts: Alert[] }>('/alerts', { params: filters })
    return data.alerts
  },

  async getAlertById(id: number) {
    const { data } = await api.get<Alert>(`/alerts/${id}`)
    return data
  },

  async acknowledgeAlert(id: number) {
    const { data } = await api.post<Alert>(`/alerts/${id}/acknowledge`)
    return data
  },

  async resolveAlert(id: number) {
    const { data } = await api.post<Alert>(`/alerts/${id}/resolve`)
    return data
  },

  async deleteAlert(id: number) {
    await api.delete(`/alerts/${id}`)
  },

  async bulkAcknowledge(ids: number[]) {
    const { data } = await api.post('/alerts/bulk-acknowledge', { ids })
    return data
  },

  async bulkResolve(ids: number[]) {
    const { data } = await api.post('/alerts/bulk-resolve', { ids })
    return data
  },

  async bulkDelete(ids: number[]) {
    await api.post('/alerts/bulk-delete', { ids })
  },

  async getBlockedActions(limit = 50, offset = 0) {
    const { data } = await api.get<{ total: number; blocked_actions: BlockedAction[] }>(
      '/alerts/blocked',
      { params: { limit, offset } }
    )
    return data
  },
}
