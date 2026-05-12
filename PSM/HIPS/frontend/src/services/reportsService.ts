import api from './api'
import { ReportFilters, ReportSummary } from '../types'

export const reportsService = {
  async getSummary(filters: ReportFilters = {}) {
    const { data } = await api.get<ReportSummary>('/reports/summary', { params: filters })
    return data
  },

  async exportPdf(filters: ReportFilters = {}) {
    const { data } = await api.get('/reports/export.pdf', {
      params: filters,
      responseType: 'blob',
    })
    return data as Blob
  },
}
