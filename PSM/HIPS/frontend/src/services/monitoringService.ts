import api from './api'

export interface ProcessInfo {
  pid: number
  name: string
  username: string | null
  cpu_percent: number
  memory_percent: number
  status: string
  create_time: number
}

export interface NetworkConnection {
  local_address: string
  local_port: number
  remote_address: string
  remote_port: number
  status: string
  pid: number
  process_name: string
}

export interface FileSystemActivity {
  timestamp: string
  operation: string
  path: string
  process_name: string
  process_pid: number
}

export interface SystemMetrics {
  cpu_percent: number
  memory_percent: number
  disk_percent: number
  network_connections: number
  process_count: number
  uptime: number
}

export const monitoringService = {
  async getProcesses() {
    const { data } = await api.get<ProcessInfo[]>('/monitoring/processes')
    return data
  },

  async getNetworkConnections() {
    const { data } = await api.get<NetworkConnection[]>('/monitoring/network')
    return data
  },

  async getFileSystemActivity(limit: number = 100) {
    const { data } = await api.get<FileSystemActivity[]>('/monitoring/filesystem', {
      params: { limit },
    })
    return data
  },

  async getSystemMetrics() {
    const { data } = await api.get<SystemMetrics>('/monitoring/system')
    return data
  },

  async killProcess(pid: number) {
    await api.post(`/monitoring/processes/${pid}/kill`)
  },

  async blockConnection(ip: string, port: number) {
    await api.post('/monitoring/network/block', { ip, port })
  },
}
