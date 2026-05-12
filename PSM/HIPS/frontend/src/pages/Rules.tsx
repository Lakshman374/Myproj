import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Edit, Trash2, Download, Upload, Power, PowerOff, RefreshCw } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { Button } from '../components/ui/button'
import { Badge } from '../components/ui/badge'
import { Input } from '../components/ui/input'
import { Label } from '../components/ui/label'
import { Textarea } from '../components/ui/textarea'
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
import { rulesService } from '../services/rulesService'
import { Rule } from '../types'

export default function Rules() {
  const [selectedRule, setSelectedRule] = useState<Rule | null>(null)
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false)
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false)
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false)
  const [notification, setNotification] = useState<{ type: 'success' | 'error'; message: string } | null>(null)
  const [conditionsJson, setConditionsJson] = useState('{}')
  const [actionsJson, setActionsJson] = useState('[]')
  const [formData, setFormData] = useState<Partial<Rule>>({
    name: '',
    description: '',
    severity: 'medium',
    category: '',
    enabled: true,
    conditions: {},
    actions: [],
  })
  const queryClient = useQueryClient()

  const { data: rules = [], isLoading, refetch } = useQuery({
    queryKey: ['rules'],
    queryFn: rulesService.getRules,
  })

  const createMutation = useMutation({
    mutationFn: rulesService.createRule,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rules'] })
      setIsCreateDialogOpen(false)
      resetForm()
      showNotification('success', 'Rule created successfully.')
    },
    onError: (error: any) => {
      const detail = error?.response?.data?.detail
      if (error?.response?.status === 409) {
        showNotification('error', 'A rule with this ID already exists. Use a different Rule ID.')
      } else if (error?.response?.status === 422) {
        showNotification('error', 'Invalid rule data. Please check the Conditions and Actions JSON.')
      } else {
        showNotification('error', `Failed to create rule: ${detail || 'An unexpected error occurred.'}`)
      }
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, rule }: { id: string; rule: Partial<Rule> }) =>
      rulesService.updateRule(id, rule),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rules'] })
      setIsEditDialogOpen(false)
      setSelectedRule(null)
      resetForm()
      showNotification('success', 'Rule updated successfully.')
    },
    onError: (error: any) => {
      const detail = error?.response?.data?.detail
      if (error?.response?.status === 422) {
        showNotification('error', 'Invalid rule data. Please check the Conditions and Actions JSON.')
      } else if (error?.response?.status === 404) {
        showNotification('error', 'Rule not found. It may have been deleted.')
      } else {
        showNotification('error', `Failed to update rule: ${detail || 'An unexpected error occurred.'}`)
      }
    },
  })

  const deleteMutation = useMutation({
    mutationFn: rulesService.deleteRule,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rules'] })
      setIsDeleteDialogOpen(false)
      setSelectedRule(null)
    },
  })

  const toggleMutation = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      rulesService.toggleRule(id, enabled),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rules'] })
    },
  })

  const resetForm = () => {
    setFormData({
      name: '',
      description: '',
      severity: 'medium',
      category: '',
      enabled: true,
      conditions: {},
      actions: [],
    })
    setConditionsJson('{}')
    setActionsJson('[]')
  }

  const handleEdit = (rule: Rule) => {
    setSelectedRule(rule)
    setFormData({
      name: rule.name,
      description: rule.description,
      severity: rule.severity,
      category: rule.category,
      enabled: rule.enabled,
      conditions: rule.conditions,
      actions: rule.actions,
    })
    setConditionsJson(JSON.stringify(rule.conditions, null, 2))
    setActionsJson(JSON.stringify(rule.actions, null, 2))
    setIsEditDialogOpen(true)
  }

  const handleDelete = (rule: Rule) => {
    setSelectedRule(rule)
    setIsDeleteDialogOpen(true)
  }

  const handleCreate = () => {
    if (!formData.id?.trim()) {
      showNotification('error', 'Rule ID is required.')
      return
    }
    if (!formData.name?.trim()) {
      showNotification('error', 'Rule Name is required.')
      return
    }
    if (!formData.category?.trim()) {
      showNotification('error', 'Category is required.')
      return
    }
    if (!formData.conditions || !(formData.conditions as any).event_type) {
      showNotification('error', 'Conditions JSON must include "event_type".')
      return
    }
    if (!Array.isArray(formData.actions) || formData.actions.length === 0) {
      showNotification('error', 'Actions JSON must be a non-empty array e.g. [{"type": "log"}].')
      return
    }
    createMutation.mutate(formData)
  }

  const handleUpdate = () => {
    if (!selectedRule) return
    if (!formData.name?.trim()) {
      showNotification('error', 'Rule Name is required.')
      return
    }
    if (!formData.conditions || !(formData.conditions as any).event_type) {
      showNotification('error', 'Conditions JSON must include "event_type".')
      return
    }
    if (!Array.isArray(formData.actions) || formData.actions.length === 0) {
      showNotification('error', 'Actions JSON must be a non-empty array e.g. [{"type": "log"}].')
      return
    }
    updateMutation.mutate({ id: selectedRule.id, rule: formData })
  }

  const handleConfirmDelete = () => {
    if (selectedRule) {
      deleteMutation.mutate(selectedRule.id)
    }
  }

  const handleToggle = (rule: Rule) => {
    toggleMutation.mutate({ id: rule.id, enabled: !rule.enabled })
  }

  const handleExport = async () => {
    try {
      const blob = await rulesService.exportRules()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `hips-rules-${Date.now()}.yaml`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (error) {
      console.error('Error exporting rules:', error)
    }
  }

  const showNotification = (type: 'success' | 'error', message: string) => {
    setNotification({ type, message })
    setTimeout(() => setNotification(null), 4000)
  }

  const handleImport = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return

    const allowed = ['.yaml', '.yml']
    const ext = file.name.slice(file.name.lastIndexOf('.')).toLowerCase()
    if (!allowed.includes(ext)) {
      showNotification('error', `Invalid file type "${ext}". Only .yaml and .yml rule files can be imported.`)
      return
    }

    try {
      await rulesService.importRules(file)
      queryClient.invalidateQueries({ queryKey: ['rules'] })
      showNotification('success', `Rule imported successfully from "${file.name}".`)
    } catch (error: any) {
      const detail = error?.response?.data?.detail
      if (error?.response?.status === 409) {
        showNotification('error', 'Import failed: A rule with this ID already exists. Delete it first or use a different ID.')
      } else if (error?.response?.status === 400) {
        showNotification('error', `Import failed: Invalid rule file. ${detail || 'Please check the YAML format.'}`)
      } else {
        showNotification('error', `Import failed: ${detail || 'An unexpected error occurred.'}`)
      }
    }
  }

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical':
        return 'bg-red-100 text-red-800'
      case 'high':
        return 'bg-orange-100 text-orange-800'
      case 'medium':
        return 'bg-yellow-100 text-yellow-800'
      case 'low':
        return 'bg-blue-100 text-blue-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }

  return (
    <div className="space-y-6">
      {notification && (
        <div className={`flex items-center justify-between rounded-md px-4 py-3 text-sm font-medium ${
          notification.type === 'success'
            ? 'bg-green-100 text-green-800 border border-green-200'
            : 'bg-red-100 text-red-800 border border-red-200'
        }`}>
          <span>{notification.message}</span>
          <button onClick={() => setNotification(null)} className="ml-4 text-lg leading-none opacity-60 hover:opacity-100">&times;</button>
        </div>
      )}
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Rules</h2>
          <p className="text-gray-500">Manage detection rules and policies</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => refetch()}>
            <RefreshCw className="h-4 w-4" />
          </Button>
          <Button variant="outline" onClick={handleExport}>
            <Download className="h-4 w-4 mr-2" />
            Export
          </Button>
          <Button variant="outline" onClick={() => document.getElementById('import-file')?.click()}>
            <Upload className="h-4 w-4 mr-2" />
            Import
          </Button>
          <input
            id="import-file"
            type="file"
            accept=".yaml,.yml,.json"
            className="hidden"
            onChange={handleImport}
          />
          <Button onClick={() => setIsCreateDialogOpen(true)}>
            <Plus className="h-4 w-4 mr-2" />
            New Rule
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Detection Rules</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="text-center py-8 text-gray-500">Loading rules...</div>
          ) : rules.length === 0 ? (
            <div className="text-center py-8 text-gray-500">No rules found</div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Status</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>Severity</TableHead>
                  <TableHead>Description</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rules.map((rule) => (
                  <TableRow key={rule.id}>
                    <TableCell>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleToggle(rule)}
                        className="p-0 h-8 w-8"
                      >
                        {rule.enabled ? (
                          <Power className="h-4 w-4 text-green-600" />
                        ) : (
                          <PowerOff className="h-4 w-4 text-gray-400" />
                        )}
                      </Button>
                    </TableCell>
                    <TableCell className="font-medium">{rule.name}</TableCell>
                    <TableCell>{rule.category}</TableCell>
                    <TableCell>
                      <Badge className={getSeverityColor(rule.severity)}>
                        {rule.severity}
                      </Badge>
                    </TableCell>
                    <TableCell className="max-w-md truncate">{rule.description}</TableCell>
                    <TableCell>
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => handleEdit(rule)}
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => handleDelete(rule)}
                        >
                          <Trash2 className="h-4 w-4 text-red-600" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Create Rule Dialog */}
      <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] flex flex-col">
          <DialogHeader>
            <DialogTitle>Create New Rule</DialogTitle>
            <DialogDescription>Define a new detection rule</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 overflow-y-auto pr-1">
            <div>
              <Label htmlFor="rule-id">Rule ID</Label>
              <Input
                id="rule-id"
                value={formData.id ?? ''}
                onChange={(e) => setFormData({ ...formData, id: e.target.value })}
                placeholder="e.g., suspicious-process-execution"
              />
            </div>
            <div>
              <Label htmlFor="name">Rule Name</Label>
              <Input
                id="name"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="e.g., Suspicious Process Execution"
              />
            </div>
            <div>
              <Label htmlFor="category">Category</Label>
              <Input
                id="category"
                value={formData.category}
                onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                placeholder="e.g., process, file, network"
              />
            </div>
            <div>
              <Label htmlFor="severity">Severity</Label>
              <Select
                value={formData.severity}
                onValueChange={(value: any) => setFormData({ ...formData, severity: value })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="low">Low</SelectItem>
                  <SelectItem value="medium">Medium</SelectItem>
                  <SelectItem value="high">High</SelectItem>
                  <SelectItem value="critical">Critical</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="Describe what this rule detects..."
                rows={3}
              />
            </div>
            <div>
              <Label htmlFor="conditions">Conditions (JSON)</Label>
              <Textarea
                id="conditions"
                value={conditionsJson}
                onChange={(e) => {
                  setConditionsJson(e.target.value)
                  try { setFormData({ ...formData, conditions: JSON.parse(e.target.value) }) } catch {}
                }}
                placeholder='{"event_type": "process_create", "platform": ["windows"]}'
                rows={6}
                className="font-mono text-xs"
              />
            </div>
            <div>
              <Label htmlFor="actions">Actions (JSON)</Label>
              <Textarea
                id="actions"
                value={actionsJson}
                onChange={(e) => {
                  setActionsJson(e.target.value)
                  try { setFormData({ ...formData, actions: JSON.parse(e.target.value) }) } catch {}
                }}
                placeholder='[{"type": "log"}]'
                rows={4}
                className="font-mono text-xs"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsCreateDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreate} disabled={createMutation.isPending}>
              Create Rule
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Rule Dialog */}
      <Dialog open={isEditDialogOpen} onOpenChange={setIsEditDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] flex flex-col">
          <DialogHeader>
            <DialogTitle>Edit Rule</DialogTitle>
            <DialogDescription>Modify rule settings</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 overflow-y-auto pr-1">
            <div>
              <Label htmlFor="edit-name">Rule Name</Label>
              <Input
                id="edit-name"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              />
            </div>
            <div>
              <Label htmlFor="edit-category">Category</Label>
              <Input
                id="edit-category"
                value={formData.category}
                onChange={(e) => setFormData({ ...formData, category: e.target.value })}
              />
            </div>
            <div>
              <Label htmlFor="edit-severity">Severity</Label>
              <Select
                value={formData.severity}
                onValueChange={(value: any) => setFormData({ ...formData, severity: value })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="low">Low</SelectItem>
                  <SelectItem value="medium">Medium</SelectItem>
                  <SelectItem value="high">High</SelectItem>
                  <SelectItem value="critical">Critical</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label htmlFor="edit-description">Description</Label>
              <Textarea
                id="edit-description"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                rows={3}
              />
            </div>
            <div>
              <Label htmlFor="edit-conditions">Conditions (JSON)</Label>
              <Textarea
                id="edit-conditions"
                value={conditionsJson}
                onChange={(e) => {
                  setConditionsJson(e.target.value)
                  try { setFormData({ ...formData, conditions: JSON.parse(e.target.value) }) } catch {}
                }}
                rows={6}
                className="font-mono text-xs"
              />
            </div>
            <div>
              <Label htmlFor="edit-actions">Actions (JSON)</Label>
              <Textarea
                id="edit-actions"
                value={actionsJson}
                onChange={(e) => {
                  setActionsJson(e.target.value)
                  try { setFormData({ ...formData, actions: JSON.parse(e.target.value) }) } catch {}
                }}
                rows={4}
                className="font-mono text-xs"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsEditDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleUpdate} disabled={updateMutation.isPending}>
              Update Rule
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={isDeleteDialogOpen} onOpenChange={setIsDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Rule</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete the rule "{selectedRule?.name}"? This action cannot
              be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsDeleteDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleConfirmDelete}
              disabled={deleteMutation.isPending}
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
