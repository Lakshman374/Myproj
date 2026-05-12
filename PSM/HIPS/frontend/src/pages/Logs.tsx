import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { format } from 'date-fns'
import { Search, Download, RefreshCw } from 'lucide-react'
import { useLocation } from 'react-router-dom'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { Button } from '../components/ui/button'
import { Input } from '../components/ui/input'
import { Badge } from '../components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/table'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../components/ui/dialog'
import { logsService, LogFilters } from '../services/logsService'
import { ActivityLog } from '../types'
import { websocketService } from '../services/websocketService'

export default function Logs() {
  const location = useLocation()
  const [filters, setFilters] = useState<LogFilters>({ limit: 100 })
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedLog, setSelectedLog] = useState<ActivityLog | null>(null)
  const [deepLinkLogId, setDeepLinkLogId] = useState<number | null>(null)

  useEffect(() => {
    const params = new URLSearchParams(location.search)
    const severity = params.get('severity') || undefined
    const start_date = params.get('start_date') || undefined
    const end_date = params.get('end_date') || undefined
    const logIdParam = params.get('log_id')
    const log_id = logIdParam ? Number(logIdParam) : null

    setFilters((current) => ({
      ...current,
      severity,
      start_date,
      end_date,
    }))

    setDeepLinkLogId(Number.isFinite(log_id) ? log_id : null)
  }, [location.search])

  const { data: logs = [], isLoading, refetch } = useQuery({
    queryKey: ['logs', filters],
    queryFn: () => logsService.getLogs(filters),
    refetchInterval: 3000,
  })

  useEffect(() => {
    // Wait for the main logs query to settle first so the dialog and table
    // always reflect the same data state.
    if (!deepLinkLogId || isLoading) return

    let cancelled = false
    logsService
      .getLogById(deepLinkLogId)
      .then((log) => {
        if (cancelled) return
        setSelectedLog(log)
      })
      .catch(() => {
        // ignore deep-link failures (e.g. log no longer exists)
      })

    return () => {
      cancelled = true
    }
  }, [deepLinkLogId, isLoading])

  // WebSocket integration for real-time updates
  useEffect(() => {
    const handleNewLog = () => {
      refetch()
    }

    websocketService.on('log', handleNewLog)
    websocketService.on('activity', handleNewLog)
    return () => {
      websocketService.off('log', handleNewLog)
      websocketService.off('activity', handleNewLog)
    }
  }, [refetch])

  const handleExport = async (format: 'csv' | 'json') => {
    try {
      const blob = await logsService.exportLogs(filters, format)
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `activity-logs-${format}-${Date.now()}.${format}`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (error) {
      console.error('Error exporting logs:', error)
    }
  }

  const filteredLogs = logs.filter((log) => {
    if (!searchTerm) return true
    const term = searchTerm.toLowerCase()
    return (
      log.event_type.toLowerCase().includes(term) ||
      (log.process_name && log.process_name.toLowerCase().includes(term)) ||
      (log.file_path && log.file_path.toLowerCase().includes(term)) ||
      (log.dst_ip && log.dst_ip.toLowerCase().includes(term)) ||
      (log.registry_key && log.registry_key.toLowerCase().includes(term)) ||
      (log.registry_value && log.registry_value.toLowerCase().includes(term))
    )
  })

  const getSeverityColor = (severity: string) => {
    switch (severity.toLowerCase()) {
      case 'critical':
        return 'bg-red-100 text-red-800'
      case 'high':
        return 'bg-orange-100 text-orange-800'
      case 'medium':
        return 'bg-yellow-100 text-yellow-800'
      case 'low':
      case 'info':
        return 'bg-blue-100 text-blue-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }

  const getEventTypeColor = (eventType: string) => {
    if (eventType.includes('process')) return 'bg-purple-100 text-purple-800'
    if (eventType.includes('file')) return 'bg-green-100 text-green-800'
    if (eventType.includes('network')) return 'bg-blue-100 text-blue-800'
    if (eventType.includes('registry')) return 'bg-yellow-100 text-yellow-800'
    return 'bg-gray-100 text-gray-800'
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Activity Logs</h2>
        <p className="text-muted-foreground">View system activity and event logs</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Activity Log Viewer</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Filters and Search */}
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search logs..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10"
              />
            </div>
            <Select
              value={filters.event_type || 'all'}
              onValueChange={(value) =>
                setFilters({ ...filters, event_type: value === 'all' ? undefined : value })
              }
            >
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Event Type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Events</SelectItem>
                <SelectItem value="process_create">Process Created</SelectItem>
                <SelectItem value="process_terminate">Process Terminated</SelectItem>
                <SelectItem value="file_created">File Created</SelectItem>
                <SelectItem value="file_modified">File Modified</SelectItem>
                <SelectItem value="file_deleted">File Deleted</SelectItem>
                <SelectItem value="network_connection">Network Connection</SelectItem>
                <SelectItem value="registry_change">Registry Change</SelectItem>
              </SelectContent>
            </Select>
            <Select
              value={filters.severity || 'all'}
              onValueChange={(value) =>
                setFilters({ ...filters, severity: value === 'all' ? undefined : value })
              }
            >
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Severity" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Severities</SelectItem>
                <SelectItem value="critical">Critical</SelectItem>
                <SelectItem value="high">High</SelectItem>
                <SelectItem value="medium">Medium</SelectItem>
                <SelectItem value="low">Low</SelectItem>
                <SelectItem value="info">Info</SelectItem>
              </SelectContent>
            </Select>
            <Button variant="outline" onClick={() => refetch()}>
              <RefreshCw className="h-4 w-4" />
            </Button>
          </div>

          {/* Export Actions */}
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => handleExport('csv')}>
              <Download className="h-4 w-4 mr-2" />
              Export CSV
            </Button>
            <Button variant="outline" size="sm" onClick={() => handleExport('json')}>
              <Download className="h-4 w-4 mr-2" />
              Export JSON
            </Button>
          </div>

          {/* Logs Table */}
          {isLoading ? (
            <div className="text-center py-8 text-muted-foreground">Loading logs...</div>
          ) : filteredLogs.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">No logs found</div>
          ) : (
            <div className="border rounded-md">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Timestamp</TableHead>
                    <TableHead>Event Type</TableHead>
                    <TableHead>Severity</TableHead>
                    <TableHead>Process</TableHead>
                    <TableHead>Details</TableHead>
                    <TableHead>Platform</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredLogs.map((log) => (
                    <TableRow key={log.id}>
                      <TableCell className="text-sm">
                        {format(new Date(log.timestamp), 'MMM dd, HH:mm:ss')}
                      </TableCell>
                      <TableCell>
                        <Badge className={getEventTypeColor(log.event_type)}>
                          {log.event_type}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge className={getSeverityColor(log.severity)}>
                          {log.severity}
                        </Badge>
                      </TableCell>
                      <TableCell className="font-mono text-xs">
                        {log.process_name && (
                          <div>
                            {log.process_name}
                            {log.process_pid && (
                              <span className="text-muted-foreground"> ({log.process_pid})</span>
                            )}
                          </div>
                        )}
                      </TableCell>
                      <TableCell className="max-w-xs truncate text-xs">
                        {log.file_path && <div>File: {log.file_path}</div>}
                        {log.file_operation && <div>Op: {log.file_operation}</div>}
                        {log.dst_ip && (
                          <div>
                            {log.dst_ip}:{log.dst_port}
                          </div>
                        )}
                        {log.registry_key && (
                          <div className="truncate" title={log.registry_key}>
                            Key: {log.registry_key}
                          </div>
                        )}
                        {log.registry_value && <div>Val: {log.registry_value}</div>}
                      </TableCell>
                      <TableCell className="text-xs">{log.platform}</TableCell>
                      <TableCell>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setSelectedLog(log)}
                        >
                          View
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}

          <div className="text-sm text-muted-foreground">
            Showing {filteredLogs.length} logs
          </div>
        </CardContent>
      </Card>

      {/* Log Detail Dialog */}
      <Dialog open={!!selectedLog} onOpenChange={() => setSelectedLog(null)}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>Activity Log Details</DialogTitle>
            <DialogDescription>
              {selectedLog &&
                format(new Date(selectedLog.timestamp), 'MMM dd, yyyy HH:mm:ss')}
            </DialogDescription>
          </DialogHeader>
          {selectedLog && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Event Type</p>
                  <Badge className={getEventTypeColor(selectedLog.event_type)}>
                    {selectedLog.event_type}
                  </Badge>
                </div>
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Severity</p>
                  <Badge className={getSeverityColor(selectedLog.severity)}>
                    {selectedLog.severity}
                  </Badge>
                </div>
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Platform</p>
                  <p className="text-sm">{selectedLog.platform}</p>
                </div>
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Log ID</p>
                  <p className="text-sm font-mono">{selectedLog.id}</p>
                </div>
              </div>

              {selectedLog.process_name && (
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Process Information</p>
                  <div className="mt-2 bg-muted p-3 rounded-md space-y-1">
                    <p className="text-sm">
                      <span className="font-medium">Name:</span> {selectedLog.process_name}
                    </p>
                    {selectedLog.process_pid && (
                      <p className="text-sm">
                        <span className="font-medium">PID:</span> {selectedLog.process_pid}
                      </p>
                    )}
                    {selectedLog.process_path && (
                      <p className="text-sm font-mono break-all">
                        <span className="font-medium">Path:</span> {selectedLog.process_path}
                      </p>
                    )}
                  </div>
                </div>
              )}

              {selectedLog.file_path && (
                <div>
                  <p className="text-sm font-medium text-muted-foreground">File Information</p>
                  <div className="mt-2 bg-muted p-3 rounded-md space-y-1">
                    <p className="text-sm font-mono break-all">
                      <span className="font-medium">Path:</span> {selectedLog.file_path}
                    </p>
                    {selectedLog.file_operation && (
                      <p className="text-sm">
                        <span className="font-medium">Operation:</span>{' '}
                        {selectedLog.file_operation}
                      </p>
                    )}
                  </div>
                </div>
              )}

              {selectedLog.dst_ip && (
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Network Information</p>
                  <div className="mt-2 bg-muted p-3 rounded-md space-y-1">
                    <p className="text-sm font-mono">
                      <span className="font-medium">Destination IP:</span> {selectedLog.dst_ip}
                    </p>
                    {selectedLog.dst_port && (
                      <p className="text-sm">
                        <span className="font-medium">Port:</span> {selectedLog.dst_port}
                      </p>
                    )}
                  </div>
                </div>
              )}

              {selectedLog.registry_key && (
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Registry Information</p>
                  <div className="mt-2 bg-muted p-3 rounded-md space-y-1">
                    <p className="text-sm font-mono break-all">
                      <span className="font-medium">Key:</span> {selectedLog.registry_key}
                    </p>
                    {selectedLog.registry_operation && (
                      <p className="text-sm">
                        <span className="font-medium">Operation:</span>{' '}
                        {selectedLog.registry_operation}
                      </p>
                    )}
                    {selectedLog.registry_value && (
                      <p className="text-sm font-mono">
                        <span className="font-medium">Value:</span> {selectedLog.registry_value}
                      </p>
                    )}
                  </div>
                </div>
              )}

              <div>
                <p className="text-sm font-medium text-muted-foreground">Raw Data</p>
                <pre className="mt-2 bg-muted p-3 rounded-md text-xs overflow-auto max-h-64">
                  {JSON.stringify(selectedLog, null, 2)}
                </pre>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
