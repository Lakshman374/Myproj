import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { format } from 'date-fns'
import { AlertTriangle, Download, FileText, RefreshCw, ScrollText } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { Input } from '../components/ui/input'
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
import { ReportFilters } from '../types'
import { reportsService } from '../services/reportsService'

const defaultDateRange = () => {
  const end = new Date()
  const start = new Date(end.getTime() - 24 * 60 * 60 * 1000)
  return { start, end }
}

const toInputDate = (date: Date) => {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000)
  return local.toISOString().slice(0, 16)
}

const toIso = (value: string) => {
  if (!value) return undefined
  return new Date(value).toISOString()
}

export default function Reports() {
  const navigate = useNavigate()
  const range = useMemo(() => defaultDateRange(), [])
  const [filters, setFilters] = useState<ReportFilters>({
    start_date: toIso(toInputDate(range.start)),
    end_date: toIso(toInputDate(range.end)),
    platform: 'windows',
    severity: undefined,
  })
  const [startInput, setStartInput] = useState(toInputDate(range.start))
  const [endInput, setEndInput] = useState(toInputDate(range.end))
  const [appliedFilters, setAppliedFilters] = useState<ReportFilters>(filters)
  const [isExporting, setIsExporting] = useState(false)

  const { data: summary, isLoading, refetch } = useQuery({
    queryKey: ['report-summary', appliedFilters],
    queryFn: () => reportsService.getSummary(appliedFilters),
  })

  const applyFilters = () => {
    setAppliedFilters({
      ...filters,
      start_date: toIso(startInput),
      end_date: toIso(endInput),
    })
  }

  const handleDownloadPdf = async () => {
    setIsExporting(true)
    try {
      const blob = await reportsService.exportPdf(appliedFilters)
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `chips-security-report-${Date.now()}.pdf`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (error) {
      console.error('Failed to export PDF report', error)
    } finally {
      setIsExporting(false)
    }
  }

  const getStatusVariant = (status?: string) => {
    if (status === 'critical') return 'destructive'
    if (status === 'warning') return 'warning'
    return 'secondary'
  }

  const toQueryParams = (value: ReportFilters & { alert_id?: number; log_id?: number }) => {
    const params = new URLSearchParams()
    if (value.start_date) params.set('start_date', value.start_date)
    if (value.end_date) params.set('end_date', value.end_date)
    if (value.severity) params.set('severity', value.severity)
    if (value.alert_id) params.set('alert_id', String(value.alert_id))
    if (value.log_id) params.set('log_id', String(value.log_id))
    return params.toString()
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Security Reports</h2>
        <p className="text-muted-foreground">Generate and download PDF protection reports</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Report Filters</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            <Input
              type="datetime-local"
              value={startInput}
              onChange={(e) => setStartInput(e.target.value)}
            />
            <Input
              type="datetime-local"
              value={endInput}
              onChange={(e) => setEndInput(e.target.value)}
            />
            <Select value="windows" disabled>
              <SelectTrigger>
                <SelectValue placeholder="Platform" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="windows">Windows</SelectItem>
              </SelectContent>
            </Select>
            <Select
              value={filters.severity || 'all'}
              onValueChange={(value) =>
                setFilters((current) => ({
                  ...current,
                  severity: value === 'all' ? undefined : value,
                }))
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="Severity" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Severities</SelectItem>
                <SelectItem value="critical">Critical</SelectItem>
                <SelectItem value="high">High</SelectItem>
                <SelectItem value="medium">Medium</SelectItem>
                <SelectItem value="low">Low</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="flex flex-wrap gap-2">
            <Button onClick={applyFilters}>
              <FileText className="mr-2 h-4 w-4" />
              Generate Report
            </Button>
            <Button variant="outline" onClick={() => refetch()}>
              <RefreshCw className="mr-2 h-4 w-4" />
              Refresh
            </Button>
            <Button variant="outline" onClick={handleDownloadPdf} disabled={isExporting}>
              <Download className="mr-2 h-4 w-4" />
              {isExporting ? 'Downloading...' : 'Download PDF'}
            </Button>
            <Button
              variant="outline"
              onClick={() => navigate(`/alerts?${toQueryParams(appliedFilters)}`)}
            >
              <AlertTriangle className="mr-2 h-4 w-4" />
              Open Alerts
            </Button>
            <Button variant="outline" onClick={() => navigate(`/logs?${toQueryParams(appliedFilters)}`)}>
              <ScrollText className="mr-2 h-4 w-4" />
              Open Logs
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Total Alerts</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{summary?.totals.total_alerts ?? 0}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Critical Alerts</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold text-destructive">{summary?.totals.critical_alerts ?? 0}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Blocked Actions</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{summary?.totals.blocked_actions ?? 0}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Device Status</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <Badge variant={getStatusVariant(summary?.device_status.status)}>
              {summary?.device_status.status ?? 'unknown'}
            </Badge>
            <p className="text-xs text-muted-foreground">{summary?.device_status.device_name ?? 'N/A'}</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Top Alerts</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="py-4 text-center text-muted-foreground">Loading report preview...</p>
          ) : !summary?.top_alerts?.length ? (
            <p className="py-4 text-center text-muted-foreground">No alerts found for selected filters.</p>
          ) : (
            <div className="border rounded-md">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Time</TableHead>
                    <TableHead>Rule</TableHead>
                    <TableHead>Severity</TableHead>
                    <TableHead>Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {summary.top_alerts.map((alert) => (
                    <TableRow
                      key={alert.id}
                      className="cursor-pointer"
                      onClick={() =>
                        navigate(
                          `/alerts?${toQueryParams({
                            ...appliedFilters,
                            severity: appliedFilters.severity || alert.severity,
                            alert_id: alert.id,
                          })}`
                        )
                      }
                    >
                      <TableCell>{format(new Date(alert.timestamp), 'PPpp')}</TableCell>
                      <TableCell>{alert.rule_name}</TableCell>
                      <TableCell>{alert.severity}</TableCell>
                      <TableCell>{alert.status}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Recent Activity Logs</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="py-4 text-center text-muted-foreground">Loading report preview...</p>
          ) : !summary?.recent_logs?.length ? (
            <p className="py-4 text-center text-muted-foreground">No logs found for selected filters.</p>
          ) : (
            <div className="border rounded-md">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Time</TableHead>
                    <TableHead>Event Type</TableHead>
                    <TableHead>Severity</TableHead>
                    <TableHead>Details</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {summary.recent_logs.map((log) => (
                    <TableRow
                      key={log.id}
                      className="cursor-pointer"
                      onClick={() =>
                        navigate(
                          `/logs?${toQueryParams({
                            ...appliedFilters,
                            severity: appliedFilters.severity || log.severity || undefined,
                            log_id: log.id,
                          })}`
                        )
                      }
                    >
                      <TableCell>{format(new Date(log.timestamp), 'PPpp')}</TableCell>
                      <TableCell>{log.event_type}</TableCell>
                      <TableCell>{log.severity || 'N/A'}</TableCell>
                      <TableCell>{log.process_name || log.file_path || 'System event'}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
