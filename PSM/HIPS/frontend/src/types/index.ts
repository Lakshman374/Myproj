export interface Alert {
  id: number
  timestamp: string
  rule_id: string
  rule_name: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  category: string
  message: string
  status: 'new' | 'acknowledged' | 'resolved'
  platform: string
  acknowledged_at?: string
  resolved_at?: string
}

export interface ActivityLog {
  id: number
  timestamp: string
  event_type: string
  platform: string
  severity: string
  process_name?: string
  process_pid?: number
  process_path?: string
  file_path?: string
  file_operation?: string
  dst_ip?: string
  dst_port?: number
  registry_key?: string
  registry_operation?: string
  registry_value?: string
}

export interface DashboardMetrics {
  total_alerts: number
  new_alerts: number
  critical_alerts: number
  blocked_actions: number
  events_last_hour: number
  events_last_24h: number
}

export interface BlockedAction {
  id: number
  timestamp: string
  rule_id?: string
  action_type: string
  target?: string
  reason?: string
  platform?: string
}

export interface Rule {
  id: string
  name: string
  description: string
  enabled: boolean
  severity: 'low' | 'medium' | 'high' | 'critical'
  category: string
  conditions: any
  actions: any[]
  metadata?: any
}

export interface ReportFilters {
  start_date?: string
  end_date?: string
  platform?: string
  severity?: string
}

export interface ReportTotals {
  total_alerts: number
  critical_alerts: number
  blocked_actions: number
  activity_events: number
}

export interface ReportDeviceStatus {
  device_name: string
  platform: string
  status: 'healthy' | 'warning' | 'critical'
  last_seen?: string
}

export interface ReportAlertItem {
  id: number
  timestamp: string
  rule_name: string
  severity: string
  category: string
  message: string
  status: string
}

export interface ReportLogItem {
  id: number
  timestamp: string
  event_type: string
  severity?: string
  process_name?: string
  file_path?: string
}

export interface ReportSummary {
  generated_at: string
  filters: Required<ReportFilters>
  totals: ReportTotals
  device_status: ReportDeviceStatus
  top_alerts: ReportAlertItem[]
  recent_logs: ReportLogItem[]
}
