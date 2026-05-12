import { useState, useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { Badge } from '../components/ui/badge'
import { dashboardService } from '../services/dashboardService'
import { AlertTriangle, Shield, Activity, Clock } from 'lucide-react'
import { format } from 'date-fns'
import { LineChart, Line, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts'
import { websocketService } from '../services/websocketService'

export default function Dashboard() {
  const [liveLogs, setLiveLogs] = useState<any[]>([])
  const [plotData, setPlotData] = useState<{ time: string, events: number, alerts: number }[]>([])
  const [eventTypeStats, setEventTypeStats] = useState<Record<string, number>>({})
  const currentCounts = useRef({ events: 0, alerts: 0 })

  const { data: metrics } = useQuery({
    queryKey: ['dashboard-metrics'],
    queryFn: () => dashboardService.getMetrics(),
    refetchInterval: 5000,
  })

  const { data: recentAlerts } = useQuery({
    queryKey: ['recent-alerts'],
    queryFn: () => dashboardService.getRecentAlerts(5),
    refetchInterval: 3000,
  })

  const { data: recentLogs } = useQuery({
    queryKey: ['recent-logs'],
    queryFn: () => dashboardService.getRecentLogs(10),
    refetchInterval: 3000,
  })

  useEffect(() => {
    if (recentLogs) {
      setLiveLogs(recentLogs.slice(0, 10))
    }
  }, [recentLogs])

  useEffect(() => {
    // Generate initial flat line for the plot
    const initialData = Array.from({ length: 30 }).map((_, i) => {
      const d = new Date()
      d.setSeconds(d.getSeconds() - (30 - i))
      return { time: format(d, 'HH:mm:ss'), events: 0, alerts: 0 }
    })
    setPlotData(initialData)

    const interval = setInterval(() => {
      setPlotData((prev) => {
        const now = format(new Date(), 'HH:mm:ss')
        const events = currentCounts.current.events;
        const alerts = currentCounts.current.alerts;
        
        currentCounts.current = { events: 0, alerts: 0 }
        
        const newData = [...prev, { time: now, events, alerts }]
        return newData.length > 30 ? newData.slice(newData.length - 30) : newData
      })
    }, 1000)

    const handleActivity = (data: any) => {
      currentCounts.current.events += 1;
      
      const typeStr = data.event_type || 'activity';
      const mapKey = typeStr.split('_')[0].toUpperCase();
      setEventTypeStats(prev => ({
        ...prev,
        [mapKey]: (prev[mapKey] || 0) + 1
      }))

      setLiveLogs(prev => {
        const logEntry = {
          id: data.id || Date.now() + Math.random(),
          event_type: data.event_type || 'activity',
          process_name: data.process?.name || data.process_name,
          file_path: data.file_path || data.path,
          timestamp: data.timestamp || new Date().toISOString()
        }
        const newLogs = [logEntry, ...prev]
        return newLogs.slice(0, 10)
      })
    }

    const handleAlert = (data: any) => {
      currentCounts.current.alerts += 1;
    }

    websocketService.on('activity', handleActivity)
    websocketService.on('alert', handleAlert)

    return () => {
      clearInterval(interval)
      websocketService.off('activity', handleActivity)
      websocketService.off('alert', handleAlert)
    }
  }, [])

  const getSeverityBadge = (severity: string) => {
    const variants: Record<string, any> = {
      critical: 'destructive',
      high: 'warning',
      medium: 'info',
      low: 'secondary',
    }
    return <Badge variant={variants[severity] || 'default'}>{severity}</Badge>
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Dashboard</h2>
        <p className="text-muted-foreground">
          Real-time overview of system protection status
        </p>
      </div>

      {/* Metrics Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Alerts</CardTitle>
            <AlertTriangle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{metrics?.total_alerts || 0}</div>
            <p className="text-xs text-muted-foreground">
              {metrics?.new_alerts || 0} new
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Critical Alerts</CardTitle>
            <Shield className="h-4 w-4 text-destructive" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-destructive">
              {metrics?.critical_alerts || 0}
            </div>
            <p className="text-xs text-muted-foreground">Requires attention</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Blocked Actions</CardTitle>
            <Shield className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-500">
              {metrics?.blocked_actions || 0}
            </div>
            <p className="text-xs text-muted-foreground">Threats stopped</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Events (24h)</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{metrics?.events_last_24h || 0}</div>
            <p className="text-xs text-muted-foreground">
              {metrics?.events_last_hour || 0} in last hour
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Live Plots */}
      <div className="grid gap-4 md:grid-cols-3 lg:grid-cols-3">
        <Card className="col-span-2">
          <CardHeader>
            <CardTitle>Real-Time Activity Trends</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[300px] w-full mt-4">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={plotData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                  <defs>
                    <linearGradient id="colorEvents" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#8884d8" stopOpacity={0.8}/>
                      <stop offset="95%" stopColor="#8884d8" stopOpacity={0}/>
                    </linearGradient>
                    <linearGradient id="colorAlerts" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#dc2626" stopOpacity={0.8}/>
                      <stop offset="95%" stopColor="#dc2626" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="time" textAnchor="end" tick={{ fontSize: 12 }} />
                  <YAxis allowDecimals={false} />
                  <Tooltip />
                  <Area 
                      type="monotone" 
                      dataKey="events" 
                      stroke="#8884d8" 
                      fillOpacity={1} 
                      fill="url(#colorEvents)"
                      name="System Events"
                      isAnimationActive={false}
                  />
                  <Area 
                      type="monotone" 
                      dataKey="alerts" 
                      stroke="#dc2626" 
                      fillOpacity={1} 
                      fill="url(#colorAlerts)"
                      name="Alerts / Predictions"
                      isAnimationActive={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        <Card className="col-span-1">
          <CardHeader>
            <CardTitle>Event Composition</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[300px] w-full mt-4 relative">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={Object.entries(eventTypeStats).map(([name, value]) => ({ name, value }))}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={80}
                    paddingAngle={5}
                    dataKey="value"
                    isAnimationActive={false}
                  >
                    {Object.entries(eventTypeStats).map((entry, index) => {
                      const colors = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#a855f7', '#ec4899'];
                      return <Cell key={`cell-${index}`} fill={colors[index % colors.length]} />
                    })}
                  </Pie>
                  <Tooltip />
                  <Legend verticalAlign="bottom" height={36}/>
                </PieChart>
              </ResponsiveContainer>
              {Object.keys(eventTypeStats).length === 0 && (
                <div className="absolute inset-0 flex items-center justify-center text-muted-foreground text-sm z-10 pointer-events-none pb-8">
                  Waiting for events...
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {/* Recent Alerts */}
        <Card>
          <CardHeader>
            <CardTitle>Recent Alerts (Live)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4 max-h-[400px] overflow-y-auto pr-2">
              {recentAlerts && recentAlerts.length > 0 ? (
                recentAlerts.map((alert: any) => (
                  <div
                    key={alert.id}
                    className="flex items-start justify-between border-b pb-4 last:border-0 last:pb-0"
                  >
                    <div className="space-y-1">
                      <p className="font-medium">{alert.rule_name}</p>
                      <p className="text-sm text-muted-foreground">{alert.message}</p>
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <Clock className="h-3 w-3" />
                        {format(new Date(alert.timestamp), 'PPpp')}
                      </div>
                    </div>
                    <div className="flex flex-col items-end gap-2">
                      {getSeverityBadge(alert.severity)}
                      <Badge variant="outline">{alert.category}</Badge>
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-sm text-muted-foreground text-center py-4">
                  No recent alerts
                </p>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Recent Activity */}
        <Card>
          <CardHeader>
            <CardTitle>Real-Time Activity Logs</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 max-h-[400px] overflow-y-auto pr-2">
              {liveLogs.length > 0 ? (
                liveLogs.map((log) => (
                  <div
                    key={log.id}
                    className="flex items-center justify-between text-sm border-b pb-2 last:border-0 last:pb-0"
                  >
                    <div className="flex items-center gap-2">
                      <Badge variant="outline" className="font-mono text-xs max-w-[120px] truncate">
                        {log.event_type}
                      </Badge>
                      <span className="text-muted-foreground max-w-[200px] truncate">
                        {log.process_name || log.file_path || 'System event'}
                      </span>
                    </div>
                    <span className="text-xs text-muted-foreground flex-shrink-0">
                      {format(new Date(log.timestamp), 'HH:mm:ss')}
                    </span>
                  </div>
                ))
              ) : (
                <p className="text-sm text-muted-foreground text-center py-4">
                  No recent activity
                </p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
