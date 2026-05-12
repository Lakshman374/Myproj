import api from './api'

export interface SystemSettings {
  monitoring: {
    process_interval: number
    filesystem_interval: number
    network_interval: number
    watched_paths: string[]
    excluded_processes: string[]
  }
  alerts: {
    max_per_hour: number
    retention_days: number
    email_notifications: boolean
    webhook_url?: string
  }
  database: {
    retention_days: number
    auto_cleanup: boolean
    max_size_mb: number
  }
  logging: {
    level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR'
    max_file_size_mb: number
    backup_count: number
  }
}

export const settingsService = {
  async getSettings() {
    const { data } = await api.get<SystemSettings>('/settings')
    return data
  },

  async updateSettings(settings: Partial<SystemSettings>) {
    const { data } = await api.put<SystemSettings>('/settings', settings)
    return data
  },

  async resetSettings() {
    const { data } = await api.post<SystemSettings>('/settings/reset')
    return data
  },

  async getSystemStatus() {
    const { data } = await api.get('/system/status')
    return data
  },

  async restartService() {
    await api.post('/system/restart')
  },

  async getDatabaseInfo() {
    const { data } = await api.get('/system/database/info')
    return data
  },

  async cleanupDatabase() {
    await api.post('/system/database/cleanup')
  },

  async backupDatabase() {
    const response = await api.get('/system/database/backup', {
      responseType: 'arraybuffer',
    })
    return new Blob([response.data], { type: 'application/octet-stream' })
  },
}
