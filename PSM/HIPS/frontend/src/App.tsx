import { useEffect } from 'react'
import { Routes, Route } from 'react-router-dom'
import MainLayout from './components/layout/MainLayout'
import Dashboard from './pages/Dashboard'
import Alerts from './pages/Alerts'
import Logs from './pages/Logs'
import Rules from './pages/Rules'
import Monitoring from './pages/Monitoring'
import Settings from './pages/Settings'
import Reports from './pages/Reports'
import { websocketService } from './services/websocketService'

function App() {
  // Initialize WebSocket connection when app starts
  useEffect(() => {
    websocketService.connect()

    return () => {
      websocketService.disconnect()
    }
  }, [])

  return (
    <MainLayout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/alerts" element={<Alerts />} />
        <Route path="/logs" element={<Logs />} />
        <Route path="/rules" element={<Rules />} />
        <Route path="/monitoring" element={<Monitoring />} />
        <Route path="/reports" element={<Reports />} />
        <Route path="/settings" element={<Settings />} />
      </Routes>
    </MainLayout>
  )
}

export default App
