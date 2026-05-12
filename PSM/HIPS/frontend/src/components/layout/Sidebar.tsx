import { Link, useLocation } from 'react-router-dom'
import { Home, AlertTriangle, FileText, Shield, Activity, Settings, FileSearch } from 'lucide-react'
import { cn } from '@/utils/cn'

const navigation = [
  { name: 'Dashboard', href: '/', icon: Home },
  { name: 'Alerts', href: '/alerts', icon: AlertTriangle },
  { name: 'Activity Logs', href: '/logs', icon: FileText },
  { name: 'Rules', href: '/rules', icon: Shield },
  { name: 'Monitoring', href: '/monitoring', icon: Activity },
  { name: 'Reports', href: '/reports', icon: FileSearch },
  { name: 'Settings', href: '/settings', icon: Settings },
]

export default function Sidebar() {
  const location = useLocation()

  return (
    <aside className="fixed left-0 top-16 h-[calc(100vh-4rem)] w-64 border-r bg-background">
      <nav className="space-y-1 p-4">
        {navigation.map((item) => {
          const isActive = location.pathname === item.href
          const Icon = item.icon

          return (
            <Link
              key={item.name}
              to={item.href}
              className={cn(
                'flex items-center space-x-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
              )}
            >
              <Icon className="h-5 w-5" />
              <span>{item.name}</span>
            </Link>
          )
        })}
      </nav>
    </aside>
  )
}
