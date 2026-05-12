import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Save, RotateCcw, Download, Trash2 } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card'
import { Button } from '../components/ui/button'
import { Input } from '../components/ui/input'
import { Label } from '../components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select'
import { Badge } from '../components/ui/badge'
import { settingsService, SystemSettings } from '../services/settingsService'

export default function Settings() {
  const [settings, setSettings] = useState<SystemSettings | null>(null)
  const [hasChanges, setHasChanges] = useState(false)
  const [watchedPathsRaw, setWatchedPathsRaw] = useState('')
  const [excludedProcessesRaw, setExcludedProcessesRaw] = useState('')
  const queryClient = useQueryClient()

  const { data: currentSettings, isLoading } = useQuery({
    queryKey: ['settings'],
    queryFn: settingsService.getSettings,
  })

  const { data: systemStatus } = useQuery({
    queryKey: ['system-status'],
    queryFn: settingsService.getSystemStatus,
    refetchInterval: 5000,
    refetchIntervalInBackground: false,
  })

  const { data: dbInfo } = useQuery({
    queryKey: ['db-info'],
    queryFn: settingsService.getDatabaseInfo,
    refetchInterval: 10000,
    refetchIntervalInBackground: false,
  })

  useEffect(() => {
    if (currentSettings) {
      setSettings(currentSettings)
      setWatchedPathsRaw(currentSettings.monitoring.watched_paths.join(', '))
      setExcludedProcessesRaw(currentSettings.monitoring.excluded_processes.join(', '))
    }
  }, [currentSettings])

  const updateMutation = useMutation({
    mutationFn: settingsService.updateSettings,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] })
      setHasChanges(false)
    },
    onError: () => {
      alert('Failed to save settings. Please try again.')
    },
  })

  const resetMutation = useMutation({
    mutationFn: settingsService.resetSettings,
    onSuccess: (data) => {
      setSettings(data)
      queryClient.invalidateQueries({ queryKey: ['settings'] })
      setHasChanges(false)
    },
    onError: () => {
      alert('Failed to reset settings. Please try again.')
    },
  })

  const cleanupMutation = useMutation({
    mutationFn: settingsService.cleanupDatabase,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['db-info'] })
    },
    onError: () => {
      alert('Database cleanup failed. Please try again.')
    },
  })

  const backupMutation = useMutation({
    mutationFn: settingsService.backupDatabase,
    onSuccess: (blob) => {
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `hips-backup-${Date.now()}.db`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    },
    onError: () => {
      alert('Database backup failed. Please try again.')
    },
  })

  const handleSave = () => {
    if (settings) {
      updateMutation.mutate(settings)
    }
  }

  const handleReset = () => {
    if (confirm('Are you sure you want to reset all settings to defaults?')) {
      resetMutation.mutate()
    }
  }

  const handleCleanup = () => {
    if (confirm('This will delete old records from the database. Continue?')) {
      cleanupMutation.mutate()
    }
  }

  const handleBackup = () => {
    backupMutation.mutate()
  }

  const updateSetting = (path: string[], value: any) => {
    if (!settings) return

    const newSettings = { ...settings }
    let current: any = newSettings

    for (let i = 0; i < path.length - 1; i++) {
      current = current[path[i]]
    }

    current[path[path.length - 1]] = value
    setSettings(newSettings)
    setHasChanges(true)
  }

  if (isLoading || !settings) {
    return (
      <div className="space-y-6">
        <h2 className="text-3xl font-bold tracking-tight">Settings</h2>
        <div className="text-center py-8 text-gray-500">Loading settings...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Settings</h2>
          <p className="text-muted-foreground">Configure CHIPS system settings</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleReset} disabled={resetMutation.isPending}>
            <RotateCcw className="h-4 w-4 mr-2" />
            Reset to Defaults
          </Button>
          <Button onClick={handleSave} disabled={!hasChanges || updateMutation.isPending}>
            <Save className="h-4 w-4 mr-2" />
            Save Changes
          </Button>
        </div>
      </div>

      {/* System Status Card */}
      {systemStatus && (
        <Card>
          <CardHeader>
            <CardTitle>System Status</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Service Status</p>
                <Badge className="mt-1 bg-green-100 text-green-800">
                  {systemStatus.status || 'Running'}
                </Badge>
              </div>
              <div>
                <p className="text-sm font-medium text-muted-foreground">Uptime</p>
                <p className="text-sm mt-1">{systemStatus.uptime || 'N/A'}</p>
              </div>
              <div>
                <p className="text-sm font-medium text-muted-foreground">Version</p>
                <p className="text-sm mt-1">{systemStatus.version || '1.0.0'}</p>
              </div>
              <div>
                <p className="text-sm font-medium text-muted-foreground">Platform</p>
                <p className="text-sm mt-1">{systemStatus.platform || 'Linux'}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      <Tabs defaultValue="monitoring" className="space-y-4">
        <TabsList>
          <TabsTrigger value="monitoring">Monitoring</TabsTrigger>
          <TabsTrigger value="alerts">Alerts</TabsTrigger>
          <TabsTrigger value="database">Database</TabsTrigger>
          <TabsTrigger value="logging">Logging</TabsTrigger>
        </TabsList>

        {/* Monitoring Settings */}
        <TabsContent value="monitoring" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Monitoring Configuration</CardTitle>
              <CardDescription>
                Configure monitoring intervals and watched resources
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <Label htmlFor="process-interval">Process Monitor Interval (seconds)</Label>
                  <Input
                    id="process-interval"
                    type="number"
                    value={settings.monitoring.process_interval}
                    onChange={(e) =>
                      updateSetting(
                        ['monitoring', 'process_interval'],
                        parseInt(e.target.value)
                      )
                    }
                  />
                </div>
                <div>
                  <Label htmlFor="fs-interval">Filesystem Monitor Interval (seconds)</Label>
                  <Input
                    id="fs-interval"
                    type="number"
                    value={settings.monitoring.filesystem_interval}
                    onChange={(e) =>
                      updateSetting(
                        ['monitoring', 'filesystem_interval'],
                        parseInt(e.target.value)
                      )
                    }
                  />
                </div>
                <div>
                  <Label htmlFor="network-interval">Network Monitor Interval (seconds)</Label>
                  <Input
                    id="network-interval"
                    type="number"
                    value={settings.monitoring.network_interval}
                    onChange={(e) =>
                      updateSetting(
                        ['monitoring', 'network_interval'],
                        parseInt(e.target.value)
                      )
                    }
                  />
                </div>
              </div>

              <div>
                <Label htmlFor="watched-paths">Watched Paths (comma-separated)</Label>
                <Input
                  id="watched-paths"
                  value={watchedPathsRaw}
                  onChange={(e) => setWatchedPathsRaw(e.target.value)}
                  onBlur={(e) =>
                    updateSetting(
                      ['monitoring', 'watched_paths'],
                      e.target.value.split(',').map((p) => p.trim()).filter(Boolean)
                    )
                  }
                  placeholder="C:\Users, C:\Windows\System32"
                />
              </div>

              <div>
                <Label htmlFor="excluded-processes">Excluded Processes (comma-separated)</Label>
                <Input
                  id="excluded-processes"
                  value={excludedProcessesRaw}
                  onChange={(e) => setExcludedProcessesRaw(e.target.value)}
                  onBlur={(e) =>
                    updateSetting(
                      ['monitoring', 'excluded_processes'],
                      e.target.value.split(',').map((p) => p.trim()).filter(Boolean)
                    )
                  }
                  placeholder="svchost.exe, lsass.exe"
                />
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Alert Settings */}
        <TabsContent value="alerts" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Alert Configuration</CardTitle>
              <CardDescription>
                Configure alert thresholds and notification settings
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="max-alerts">Maximum Alerts per Hour</Label>
                  <Input
                    id="max-alerts"
                    type="number"
                    value={settings.alerts.max_per_hour}
                    onChange={(e) =>
                      updateSetting(['alerts', 'max_per_hour'], parseInt(e.target.value))
                    }
                  />
                </div>
                <div>
                  <Label htmlFor="alert-retention">Alert Retention (days)</Label>
                  <Input
                    id="alert-retention"
                    type="number"
                    value={settings.alerts.retention_days}
                    onChange={(e) =>
                      updateSetting(['alerts', 'retention_days'], parseInt(e.target.value))
                    }
                  />
                </div>
              </div>

              <div>
                <Label htmlFor="email-notifications">Email Notifications</Label>
                <Select
                  value={settings.alerts.email_notifications ? 'enabled' : 'disabled'}
                  onValueChange={(value) =>
                    updateSetting(['alerts', 'email_notifications'], value === 'enabled')
                  }
                >
                  <SelectTrigger id="email-notifications">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="enabled">Enabled</SelectItem>
                    <SelectItem value="disabled">Disabled</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label htmlFor="webhook-url">Webhook URL (optional)</Label>
                <Input
                  id="webhook-url"
                  type="url"
                  value={settings.alerts.webhook_url || ''}
                  onChange={(e) => updateSetting(['alerts', 'webhook_url'], e.target.value)}
                  placeholder="https://hooks.example.com/webhook"
                />
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Database Settings */}
        <TabsContent value="database" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Database Configuration</CardTitle>
              <CardDescription>Manage database settings and maintenance</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="db-retention">Data Retention (days)</Label>
                  <Input
                    id="db-retention"
                    type="number"
                    value={settings.database.retention_days}
                    onChange={(e) =>
                      updateSetting(['database', 'retention_days'], parseInt(e.target.value))
                    }
                  />
                </div>
                <div>
                  <Label htmlFor="db-max-size">Max Database Size (MB)</Label>
                  <Input
                    id="db-max-size"
                    type="number"
                    value={settings.database.max_size_mb}
                    onChange={(e) =>
                      updateSetting(['database', 'max_size_mb'], parseInt(e.target.value))
                    }
                  />
                </div>
              </div>

              <div>
                <Label htmlFor="auto-cleanup">Automatic Cleanup</Label>
                <Select
                  value={settings.database.auto_cleanup ? 'enabled' : 'disabled'}
                  onValueChange={(value) =>
                    updateSetting(['database', 'auto_cleanup'], value === 'enabled')
                  }
                >
                  <SelectTrigger id="auto-cleanup">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="enabled">Enabled</SelectItem>
                    <SelectItem value="disabled">Disabled</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {dbInfo && (
                <div className="border rounded-lg p-4 bg-muted">
                  <h4 className="font-medium mb-3">Database Information</h4>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div>
                      <span className="text-muted-foreground">Size:</span>{' '}
                      <span className="font-mono">{dbInfo.size || 'N/A'}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Records:</span>{' '}
                      <span className="font-mono">{dbInfo.records || 'N/A'}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Last Cleanup:</span>{' '}
                      <span className="font-mono">{dbInfo.last_cleanup || 'Never'}</span>
                    </div>
                  </div>
                </div>
              )}

              <div className="flex gap-2">
                <Button
                  variant="outline"
                  onClick={handleCleanup}
                  disabled={cleanupMutation.isPending}
                >
                  <Trash2 className="h-4 w-4 mr-2" />
                  Cleanup Old Data
                </Button>
                <Button
                  variant="outline"
                  onClick={handleBackup}
                  disabled={backupMutation.isPending}
                >
                  <Download className="h-4 w-4 mr-2" />
                  Backup Database
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Logging Settings */}
        <TabsContent value="logging" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Logging Configuration</CardTitle>
              <CardDescription>Configure logging levels and file management</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div>
                <Label htmlFor="log-level">Log Level</Label>
                <Select
                  value={settings.logging.level}
                  onValueChange={(value: any) => updateSetting(['logging', 'level'], value)}
                >
                  <SelectTrigger id="log-level">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="DEBUG">DEBUG</SelectItem>
                    <SelectItem value="INFO">INFO</SelectItem>
                    <SelectItem value="WARNING">WARNING</SelectItem>
                    <SelectItem value="ERROR">ERROR</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="log-file-size">Max Log File Size (MB)</Label>
                  <Input
                    id="log-file-size"
                    type="number"
                    value={settings.logging.max_file_size_mb}
                    onChange={(e) =>
                      updateSetting(['logging', 'max_file_size_mb'], parseInt(e.target.value))
                    }
                  />
                </div>
                <div>
                  <Label htmlFor="backup-count">Backup File Count</Label>
                  <Input
                    id="backup-count"
                    type="number"
                    value={settings.logging.backup_count}
                    onChange={(e) =>
                      updateSetting(['logging', 'backup_count'], parseInt(e.target.value))
                    }
                  />
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {hasChanges && (
        <div className="fixed bottom-4 right-4 bg-card border shadow-lg rounded-lg p-4 flex items-center gap-4">
          <p className="text-sm font-medium">You have unsaved changes</p>
          <Button onClick={handleSave} disabled={updateMutation.isPending}>
            Save Now
          </Button>
        </div>
      )}
    </div>
  )
}
