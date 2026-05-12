import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { format } from 'date-fns'
import { Activity, Cpu, HardDrive, Network, RefreshCw, X, Ban } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { Button } from '../components/ui/button'
import { Badge } from '../components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/table'
import { monitoringService } from '../services/monitoringService'
import { websocketService } from '../services/websocketService'

export default function Monitoring() {
  const [autoRefresh, setAutoRefresh] = useState(true)
  const queryClient = useQueryClient()

  const { data: processes = [], isLoading: processesLoading, refetch: refetchProcesses } = useQuery({
    queryKey: ['processes'],
    queryFn: monitoringService.getProcesses,
    refetchInterval: autoRefresh ? 2000 : false,
  })

  const { data: connections = [], isLoading: connectionsLoading, refetch: refetchConnections } = useQuery({
    queryKey: ['connections'],
    queryFn: monitoringService.getNetworkConnections,
    refetchInterval: autoRefresh ? 3000 : false,
  })

  const { data: fsActivity = [], isLoading: fsLoading, refetch: refetchFsActivity } = useQuery({
    queryKey: ['fs-activity'],
    queryFn: () => monitoringService.getFileSystemActivity(50),
    refetchInterval: autoRefresh ? 2000 : false,
  })

  const { data: systemMetrics } = useQuery({
    queryKey: ['system-metrics'],
    queryFn: monitoringService.getSystemMetrics,
    refetchInterval: autoRefresh ? 1000 : false,
  })

  const killProcessMutation = useMutation({
    mutationFn: monitoringService.killProcess,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['processes'] })
    },
  })

  const blockConnectionMutation = useMutation({
    mutationFn: ({ ip, port }: { ip: string; port: number }) =>
      monitoringService.blockConnection(ip, port),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['connections'] })
    },
  })

  // WebSocket integration for real-time updates
  useEffect(() => {
    const handleProcessEvent = () => {
      refetchProcesses()
    }

    const handleNetworkEvent = () => {
      refetchConnections()
    }

    const handleFileEvent = () => {
      refetchFsActivity()
    }

    websocketService.on('process', handleProcessEvent)
    websocketService.on('network', handleNetworkEvent)
    websocketService.on('file', handleFileEvent)

    return () => {
      websocketService.off('process', handleProcessEvent)
      websocketService.off('network', handleNetworkEvent)
      websocketService.off('file', handleFileEvent)
    }
  }, [refetchProcesses, refetchConnections, refetchFsActivity])

  const handleKillProcess = (pid: number, name: string) => {
    if (confirm(`Are you sure you want to kill process "${name}" (PID: ${pid})?`)) {
      killProcessMutation.mutate(pid)
    }
  }

  const handleBlockConnection = (ip: string, port: number) => {
    if (confirm(`Are you sure you want to block connection to ${ip}:${port}?`)) {
      blockConnectionMutation.mutate({ ip, port })
    }
  }

  const formatUptime = (timestamp: number) => {
    const seconds = Math.floor(Date.now() / 1000 - timestamp)
    if (seconds < 60) return `${seconds}s`
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m`
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`
    return `${Math.floor(seconds / 86400)}d`
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Live Monitoring</h2>
          <p className="text-gray-500">Real-time system activity monitoring</p>
        </div>
        <div className="flex gap-2">
          <Button
            variant={autoRefresh ? 'default' : 'outline'}
            onClick={() => setAutoRefresh(!autoRefresh)}
          >
            <Activity className="h-4 w-4 mr-2" />
            {autoRefresh ? 'Auto-Refresh ON' : 'Auto-Refresh OFF'}
          </Button>
        </div>
      </div>

      {/* System Metrics */}
      {systemMetrics && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">CPU Usage</CardTitle>
              <Cpu className="h-4 w-4 text-gray-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{systemMetrics.cpu_percent.toFixed(1)}%</div>
              <div className="w-full bg-gray-200 rounded-full h-2 mt-2">
                <div
                  className="bg-blue-600 h-2 rounded-full transition-all"
                  style={{ width: `${systemMetrics.cpu_percent}%` }}
                />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Memory Usage</CardTitle>
              <HardDrive className="h-4 w-4 text-gray-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{systemMetrics.memory_percent.toFixed(1)}%</div>
              <div className="w-full bg-gray-200 rounded-full h-2 mt-2">
                <div
                  className="bg-green-600 h-2 rounded-full transition-all"
                  style={{ width: `${systemMetrics.memory_percent}%` }}
                />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Active Processes</CardTitle>
              <Activity className="h-4 w-4 text-gray-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{systemMetrics.process_count}</div>
              <p className="text-xs text-gray-500 mt-1">Running processes</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Network Connections</CardTitle>
              <Network className="h-4 w-4 text-gray-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{systemMetrics.network_connections}</div>
              <p className="text-xs text-gray-500 mt-1">Active connections</p>
            </CardContent>
          </Card>
        </div>
      )}

      <Tabs defaultValue="processes" className="space-y-4">
        <TabsList>
          <TabsTrigger value="processes">Processes</TabsTrigger>
          <TabsTrigger value="network">Network</TabsTrigger>
          <TabsTrigger value="filesystem">File System</TabsTrigger>
        </TabsList>

        {/* Processes Tab */}
        <TabsContent value="processes" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex justify-between items-center">
                <CardTitle>Running Processes</CardTitle>
                <Button variant="outline" size="sm" onClick={() => refetchProcesses()}>
                  <RefreshCw className="h-4 w-4" />
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {processesLoading ? (
                <div className="text-center py-8 text-gray-500">Loading processes...</div>
              ) : processes.length === 0 ? (
                <div className="text-center py-8 text-gray-500">No processes found</div>
              ) : (
                <div className="border rounded-md">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>PID</TableHead>
                        <TableHead>Name</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>CPU %</TableHead>
                        <TableHead>Memory %</TableHead>
                        <TableHead>Uptime</TableHead>
                        <TableHead>User</TableHead>
                        <TableHead>Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {processes.slice(0, 50).map((proc) => (
                        <TableRow key={proc.pid}>
                          <TableCell className="font-mono text-xs">{proc.pid}</TableCell>
                          <TableCell className="font-medium">{proc.name}</TableCell>
                          <TableCell>
                            <Badge variant="outline">{proc.status}</Badge>
                          </TableCell>
                          <TableCell>{proc.cpu_percent.toFixed(1)}%</TableCell>
                          <TableCell>{proc.memory_percent.toFixed(1)}%</TableCell>
                          <TableCell className="text-xs">
                            {formatUptime(proc.create_time)}
                          </TableCell>
                          <TableCell className="text-xs">
                            {proc.username || '—'}
                          </TableCell>
                          <TableCell>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => handleKillProcess(proc.pid, proc.name)}
                            >
                              <X className="h-4 w-4 text-red-600" />
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
              <p className="text-sm text-gray-500 mt-2">
                Showing top 50 of {processes.length} processes
              </p>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Network Tab */}
        <TabsContent value="network" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex justify-between items-center">
                <CardTitle>Active Network Connections</CardTitle>
                <Button variant="outline" size="sm" onClick={() => refetchConnections()}>
                  <RefreshCw className="h-4 w-4" />
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {connectionsLoading ? (
                <div className="text-center py-8 text-gray-500">Loading connections...</div>
              ) : connections.length === 0 ? (
                <div className="text-center py-8 text-gray-500">No connections found</div>
              ) : (
                <div className="border rounded-md">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Local Address</TableHead>
                        <TableHead>Remote Address</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>PID</TableHead>
                        <TableHead>Process</TableHead>
                        <TableHead>Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {connections.slice(0, 50).map((conn) => (
                        <TableRow key={`${conn.local_address}:${conn.local_port}-${conn.remote_address}:${conn.remote_port}-${conn.pid}`}>
                          <TableCell className="font-mono text-xs">
                            {conn.local_address}:{conn.local_port}
                          </TableCell>
                          <TableCell className="font-mono text-xs">
                            {conn.remote_address}:{conn.remote_port}
                          </TableCell>
                          <TableCell>
                            <Badge variant="outline">{conn.status}</Badge>
                          </TableCell>
                          <TableCell className="font-mono text-xs">{conn.pid}</TableCell>
                          <TableCell>{conn.process_name}</TableCell>
                          <TableCell>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() =>
                                handleBlockConnection(conn.remote_address, conn.remote_port)
                              }
                            >
                              <Ban className="h-4 w-4 text-red-600" />
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
              <p className="text-sm text-gray-500 mt-2">
                Showing top 50 of {connections.length} connections
              </p>
            </CardContent>
          </Card>
        </TabsContent>

        {/* File System Tab */}
        <TabsContent value="filesystem" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex justify-between items-center">
                <CardTitle>File System Activity</CardTitle>
                <Button variant="outline" size="sm" onClick={() => refetchFsActivity()}>
                  <RefreshCw className="h-4 w-4" />
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {fsLoading ? (
                <div className="text-center py-8 text-gray-500">Loading activity...</div>
              ) : fsActivity.length === 0 ? (
                <div className="text-center py-8 text-gray-500">No file system activity</div>
              ) : (
                <div className="border rounded-md">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Timestamp</TableHead>
                        <TableHead>Operation</TableHead>
                        <TableHead>Path</TableHead>
                        <TableHead>Process</TableHead>
                        <TableHead>PID</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {fsActivity.map((activity) => (
                        <TableRow key={`${activity.timestamp}-${activity.path}-${activity.process_pid}`}>
                          <TableCell className="text-xs">
                            {format(new Date(activity.timestamp), 'HH:mm:ss')}
                          </TableCell>
                          <TableCell>
                            <Badge variant="outline">{activity.operation}</Badge>
                          </TableCell>
                          <TableCell className="max-w-md truncate font-mono text-xs">
                            {activity.path}
                          </TableCell>
                          <TableCell>{activity.process_name}</TableCell>
                          <TableCell className="font-mono text-xs">
                            {activity.process_pid}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
              <p className="text-sm text-gray-500 mt-2">
                Showing recent {fsActivity.length} file system events
              </p>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
