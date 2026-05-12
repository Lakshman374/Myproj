import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { format } from 'date-fns'
import { Search, Check, Trash2, RefreshCw, ShieldOff } from 'lucide-react'
import { useLocation } from 'react-router-dom'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { Button } from '../components/ui/button'
import { Input } from '../components/ui/input'
import { Badge } from '../components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs'
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
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../components/ui/dialog'
import { alertsService, AlertFilters } from '../services/alertsService'
import { Alert, BlockedAction } from '../types'
import { websocketService } from '../services/websocketService'

export default function Alerts() {
  const location = useLocation()
  const [filters, setFilters] = useState<AlertFilters>({})
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null)
  const [selectedAlerts, setSelectedAlerts] = useState<Set<number>>(new Set())
  const [selectedBlocked, setSelectedBlocked] = useState<BlockedAction | null>(null)
  const queryClient = useQueryClient()
  const [deepLinkAlertId, setDeepLinkAlertId] = useState<number | null>(null)

  useEffect(() => {
    const params = new URLSearchParams(location.search)
    const severity = params.get('severity') || undefined
    const start_date = params.get('start_date') || undefined
    const end_date = params.get('end_date') || undefined
    const alertIdParam = params.get('alert_id')
    const alert_id = alertIdParam ? Number(alertIdParam) : null

    setFilters((current) => ({ ...current, severity, start_date, end_date }))
    setDeepLinkAlertId(Number.isFinite(alert_id) ? alert_id : null)
  }, [location.search])

  const { data: alerts = [], isLoading, refetch } = useQuery({
    queryKey: ['alerts', filters],
    queryFn: () => alertsService.getAlerts(filters),
    refetchInterval: 5000,
  })

  const { data: blockedData, isLoading: isLoadingBlocked, refetch: refetchBlocked } = useQuery({
    queryKey: ['blocked-actions'],
    queryFn: () => alertsService.getBlockedActions(),
    refetchInterval: 10000,
  })

  const blockedActions = blockedData?.blocked_actions ?? []

  const acknowledgeMutation = useMutation({
    mutationFn: alertsService.acknowledgeAlert,
    onSuccess: (updatedAlert) => {
      queryClient.invalidateQueries({ queryKey: ['alerts'] })
      setSelectedAlert(updatedAlert)
    },
  })

  const resolveMutation = useMutation({
    mutationFn: alertsService.resolveAlert,
    onSuccess: (updatedAlert) => {
      queryClient.invalidateQueries({ queryKey: ['alerts'] })
      setSelectedAlert(updatedAlert)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: alertsService.deleteAlert,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alerts'] })
      setSelectedAlert(null)
    },
  })

  useEffect(() => {
    if (!deepLinkAlertId || isLoading) return
    let cancelled = false
    alertsService
      .getAlertById(deepLinkAlertId)
      .then((alert) => { if (!cancelled) setSelectedAlert(alert) })
      .catch(() => {})
    return () => { cancelled = true }
  }, [deepLinkAlertId, isLoading])

  const bulkAcknowledgeMutation = useMutation({
    mutationFn: alertsService.bulkAcknowledge,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alerts'] })
      setSelectedAlerts(new Set())
    },
  })

  const bulkResolveMutation = useMutation({
    mutationFn: alertsService.bulkResolve,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alerts'] })
      setSelectedAlerts(new Set())
    },
  })

  const bulkDeleteMutation = useMutation({
    mutationFn: alertsService.bulkDelete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alerts'] })
      setSelectedAlerts(new Set())
    },
  })

  useEffect(() => {
    const handleNewAlert = () => refetch()
    websocketService.on('alert', handleNewAlert)
    return () => websocketService.off('alert', handleNewAlert)
  }, [refetch])

  const filteredAlerts = alerts.filter((alert) => {
    if (!searchTerm) return true
    return (
      alert.rule_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      alert.message.toLowerCase().includes(searchTerm.toLowerCase()) ||
      alert.category.toLowerCase().includes(searchTerm.toLowerCase())
    )
  })

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-200'
      case 'high': return 'bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-200'
      case 'medium': return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-200'
      case 'low': return 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-200'
      default: return 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200'
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'new': return 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-200'
      case 'acknowledged': return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-200'
      case 'resolved': return 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-200'
      default: return 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200'
    }
  }

  const toggleSelectAlert = (id: number) => {
    const newSelected = new Set(selectedAlerts)
    if (newSelected.has(id)) newSelected.delete(id)
    else newSelected.add(id)
    setSelectedAlerts(newSelected)
  }

  const toggleSelectAll = () => {
    if (selectedAlerts.size === filteredAlerts.length) setSelectedAlerts(new Set())
    else setSelectedAlerts(new Set(filteredAlerts.map((a) => a.id)))
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Alerts</h2>
        <p className="text-muted-foreground">View and manage security alerts</p>
      </div>

      <Tabs defaultValue="alerts">
        <TabsList>
          <TabsTrigger value="alerts">
            Security Alerts
            {alerts.length > 0 && (
              <Badge className="ml-2 bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-200">
                {alerts.length}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="blocked">
            <ShieldOff className="h-4 w-4 mr-1" />
            Blocked Actions
            {blockedActions.length > 0 && (
              <Badge className="ml-2 bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-200">
                {blockedData?.total ?? blockedActions.length}
              </Badge>
            )}
          </TabsTrigger>
        </TabsList>

        {/* ── Security Alerts Tab ── */}
        <TabsContent value="alerts">
          <Card>
            <CardHeader>
              <CardTitle>Alert Management</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Filters */}
              <div className="flex flex-col sm:flex-row gap-4">
                <div className="flex-1 relative">
                  <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Search alerts..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="pl-10"
                  />
                </div>
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
                  </SelectContent>
                </Select>
                <Select
                  value={filters.status || 'all'}
                  onValueChange={(value) =>
                    setFilters({ ...filters, status: value === 'all' ? undefined : value })
                  }
                >
                  <SelectTrigger className="w-[180px]">
                    <SelectValue placeholder="Status" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Statuses</SelectItem>
                    <SelectItem value="new">New</SelectItem>
                    <SelectItem value="acknowledged">Acknowledged</SelectItem>
                    <SelectItem value="resolved">Resolved</SelectItem>
                  </SelectContent>
                </Select>
                <Button variant="outline" onClick={() => refetch()}>
                  <RefreshCw className="h-4 w-4" />
                </Button>
              </div>

              {/* Bulk Actions */}
              {selectedAlerts.size > 0 && (
                <div className="flex gap-2 p-3 bg-muted rounded-md">
                  <span className="text-sm font-medium my-auto">{selectedAlerts.size} selected</span>
                  <Button size="sm" variant="outline" onClick={() => bulkAcknowledgeMutation.mutate(Array.from(selectedAlerts))}>
                    <Check className="h-4 w-4 mr-1" /> Acknowledge
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => bulkResolveMutation.mutate(Array.from(selectedAlerts))}>
                    <Check className="h-4 w-4 mr-1" /> Resolve
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => bulkDeleteMutation.mutate(Array.from(selectedAlerts))}>
                    <Trash2 className="h-4 w-4 mr-1" /> Delete
                  </Button>
                </div>
              )}

              {/* Alerts Table */}
              {isLoading ? (
                <div className="text-center py-8 text-muted-foreground">Loading alerts...</div>
              ) : filteredAlerts.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">No alerts found</div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-12">
                        <input
                          type="checkbox"
                          checked={selectedAlerts.size === filteredAlerts.length}
                          onChange={toggleSelectAll}
                          className="rounded"
                        />
                      </TableHead>
                      <TableHead>Timestamp</TableHead>
                      <TableHead>Rule</TableHead>
                      <TableHead>Severity</TableHead>
                      <TableHead>Category</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Message</TableHead>
                      <TableHead>Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredAlerts.map((alert) => (
                      <TableRow key={alert.id}>
                        <TableCell>
                          <input
                            type="checkbox"
                            checked={selectedAlerts.has(alert.id)}
                            onChange={() => toggleSelectAlert(alert.id)}
                            className="rounded"
                          />
                        </TableCell>
                        <TableCell className="text-sm">
                          {format(new Date(alert.timestamp), 'MMM dd, HH:mm:ss')}
                        </TableCell>
                        <TableCell className="font-medium">{alert.rule_name}</TableCell>
                        <TableCell>
                          <Badge className={getSeverityColor(alert.severity)}>{alert.severity}</Badge>
                        </TableCell>
                        <TableCell>{alert.category}</TableCell>
                        <TableCell>
                          <Badge className={getStatusColor(alert.status)}>{alert.status}</Badge>
                        </TableCell>
                        <TableCell className="max-w-md truncate">{alert.message}</TableCell>
                        <TableCell>
                          <Button size="sm" variant="ghost" onClick={() => setSelectedAlert(alert)}>
                            View
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Blocked Actions Tab ── */}
        <TabsContent value="blocked">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                <ShieldOff className="h-5 w-5 text-orange-500" />
                Blocked Actions
              </CardTitle>
              <Button variant="outline" size="sm" onClick={() => refetchBlocked()}>
                <RefreshCw className="h-4 w-4" />
              </Button>
            </CardHeader>
            <CardContent>
              {isLoadingBlocked ? (
                <div className="text-center py-8 text-muted-foreground">Loading blocked actions...</div>
              ) : blockedActions.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">No blocked actions recorded</div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Timestamp</TableHead>
                      <TableHead>Action Type</TableHead>
                      <TableHead>Target (PID)</TableHead>
                      <TableHead>Rule</TableHead>
                      <TableHead>Reason</TableHead>
                      <TableHead>Platform</TableHead>
                      <TableHead>Details</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {blockedActions.map((item) => (
                      <TableRow key={item.id}>
                        <TableCell className="text-sm">
                          {format(new Date(item.timestamp), 'MMM dd, HH:mm:ss')}
                        </TableCell>
                        <TableCell>
                          <Badge className="bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-200">
                            {item.action_type}
                          </Badge>
                        </TableCell>
                        <TableCell className="font-mono text-sm">{item.target ?? '—'}</TableCell>
                        <TableCell className="text-sm">{item.rule_id ?? '—'}</TableCell>
                        <TableCell className="max-w-xs truncate text-sm">{item.reason ?? '—'}</TableCell>
                        <TableCell className="text-sm">{item.platform ?? '—'}</TableCell>
                        <TableCell>
                          <Button size="sm" variant="ghost" onClick={() => setSelectedBlocked(item)}>
                            View
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Alert Detail Dialog */}
      <Dialog open={!!selectedAlert} onOpenChange={() => setSelectedAlert(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{selectedAlert?.rule_name}</DialogTitle>
            <DialogDescription>
              Alert triggered on{' '}
              {selectedAlert && format(new Date(selectedAlert.timestamp), 'MMM dd, yyyy HH:mm:ss')}
            </DialogDescription>
          </DialogHeader>
          {selectedAlert && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Severity</p>
                  <Badge className={getSeverityColor(selectedAlert.severity)}>{selectedAlert.severity}</Badge>
                </div>
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Status</p>
                  <Badge className={getStatusColor(selectedAlert.status)}>{selectedAlert.status}</Badge>
                </div>
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Category</p>
                  <p className="text-sm">{selectedAlert.category}</p>
                </div>
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Platform</p>
                  <p className="text-sm">{selectedAlert.platform}</p>
                </div>
              </div>
              <div>
                <p className="text-sm font-medium text-muted-foreground">Message</p>
                <p className="text-sm mt-1">{selectedAlert.message}</p>
              </div>
              <div>
                <p className="text-sm font-medium text-muted-foreground">Rule ID</p>
                <p className="text-sm font-mono mt-1">{selectedAlert.rule_id}</p>
              </div>
              {selectedAlert.acknowledged_at && (
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Acknowledged At</p>
                  <p className="text-sm mt-1">
                    {format(new Date(selectedAlert.acknowledged_at), 'MMM dd, yyyy HH:mm:ss')}
                  </p>
                </div>
              )}
              {selectedAlert.resolved_at && (
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Resolved At</p>
                  <p className="text-sm mt-1">
                    {format(new Date(selectedAlert.resolved_at), 'MMM dd, yyyy HH:mm:ss')}
                  </p>
                </div>
              )}
            </div>
          )}
          <DialogFooter className="flex gap-2">
            {selectedAlert?.status === 'new' && (
              <Button onClick={() => acknowledgeMutation.mutate(selectedAlert.id)} disabled={acknowledgeMutation.isPending}>
                <Check className="h-4 w-4 mr-2" /> Acknowledge
              </Button>
            )}
            {selectedAlert?.status !== 'resolved' && (
              <Button onClick={() => resolveMutation.mutate(selectedAlert!.id)} disabled={resolveMutation.isPending}>
                <Check className="h-4 w-4 mr-2" /> Resolve
              </Button>
            )}
            {selectedAlert && (
              <Button variant="outline" onClick={() => deleteMutation.mutate(selectedAlert.id)} disabled={deleteMutation.isPending}>
                <Trash2 className="h-4 w-4 mr-2" /> Delete
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Blocked Action Detail Dialog */}
      <Dialog open={!!selectedBlocked} onOpenChange={() => setSelectedBlocked(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <ShieldOff className="h-5 w-5 text-orange-500" />
              Blocked Action Details
            </DialogTitle>
            <DialogDescription>
              {selectedBlocked && format(new Date(selectedBlocked.timestamp), 'MMM dd, yyyy HH:mm:ss')}
            </DialogDescription>
          </DialogHeader>
          {selectedBlocked && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Action Type</p>
                  <Badge className="bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-200 mt-1">
                    {selectedBlocked.action_type}
                  </Badge>
                </div>
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Platform</p>
                  <p className="text-sm mt-1">{selectedBlocked.platform ?? '—'}</p>
                </div>
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Target (PID)</p>
                  <p className="text-sm font-mono mt-1">{selectedBlocked.target ?? '—'}</p>
                </div>
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Rule ID</p>
                  <p className="text-sm font-mono mt-1">{selectedBlocked.rule_id ?? '—'}</p>
                </div>
              </div>
              <div>
                <p className="text-sm font-medium text-muted-foreground">Reason</p>
                <p className="text-sm mt-1">{selectedBlocked.reason ?? '—'}</p>
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setSelectedBlocked(null)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
