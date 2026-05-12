import api from './api'
import { ActivityLog } from '../types'

export interface LogFilters {
  event_type?: string
  severity?: string
  process_name?: string
  start_date?: string
  end_date?: string
  limit?: number
  offset?: number
}

export const logsService = {
  async getLogs(filters: LogFilters = {}) {
    const { data } = await api.get<{ total: number; logs: ActivityLog[] }>('/logs', { params: filters })
    return data.logs
  },

  async getLogById(id: number) {
    const { data } = await api.get<ActivityLog>(`/logs/${id}`)
    return data
  },

  async exportLogs(filters: LogFilters = {}, format: 'csv' | 'json' = 'csv') {
    const response = await api.get(`/logs/export`, {
      params: { ...filters, format },
      responseType: 'arraybuffer',
    })
    const mimeType = format === 'json' ? 'application/json' : 'text/csv'
    return new Blob([response.data], { type: mimeType })
  },

  async clearOldLogs(days: number) {
    await api.delete('/logs/cleanup', { params: { days } })
  },
}
