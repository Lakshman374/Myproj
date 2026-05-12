import api from './api'
import { Rule } from '../types'

export const rulesService = {
  async getRules() {
    const { data } = await api.get<Rule[]>('/rules')
    return data
  },

  async getRuleById(id: string) {
    const { data } = await api.get<Rule>(`/rules/${id}`)
    return data
  },

  async createRule(rule: Partial<Rule>) {
    const { data } = await api.post<Rule>('/rules', { rule })
    return data
  },

  async updateRule(id: string, rule: Partial<Rule>) {
    const { data } = await api.put<Rule>(`/rules/${id}`, { rule: { ...rule, id } })
    return data
  },

  async deleteRule(id: string) {
    await api.delete(`/rules/${id}`)
  },

  async toggleRule(id: string, enabled: boolean) {
    const { data } = await api.put<Rule>(`/rules/${id}/toggle`)
    return data
  },

  async validateRule(rule: Partial<Rule>) {
    const { data } = await api.post('/rules/validate', rule)
    return data
  },

  async importRules(file: File) {
    const formData = new FormData()
    formData.append('file', file)
    const { data } = await api.post('/rules/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data
  },

  async exportRules() {
    const response = await api.get('/rules/export', {
      responseType: 'arraybuffer',
    })
    return new Blob([response.data], { type: 'application/x-yaml' })
  },
}
