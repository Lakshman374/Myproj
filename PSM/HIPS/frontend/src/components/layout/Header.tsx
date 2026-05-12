import { Shield, Moon, Sun } from 'lucide-react'
import { useDarkMode } from '../../hooks/useDarkMode'
import { Button } from '../ui/button'

export default function Header() {
  const { isDark, toggle } = useDarkMode()

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="flex h-16 items-center px-6">
        <div className="flex items-center space-x-2">
          <Shield className="h-6 w-6 text-primary" />
          <h1 className="text-xl font-bold">CHIPS</h1>
          <span className="text-sm text-muted-foreground">Intrusion Prevention System</span>
        </div>
        <div className="ml-auto flex items-center space-x-4">
          <div className="flex items-center space-x-2">
            <div className="h-2 w-2 rounded-full bg-green-500"></div>
            <span className="text-sm text-muted-foreground">Active</span>
          </div>

          {/* Dark Mode Toggle */}
          <Button
            id="dark-mode-toggle"
            variant="ghost"
            size="icon"
            onClick={toggle}
            aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
            title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {isDark ? (
              <Sun className="h-5 w-5 transition-transform duration-300 rotate-0 hover:rotate-12" />
            ) : (
              <Moon className="h-5 w-5 transition-transform duration-300 rotate-0 hover:-rotate-12" />
            )}
          </Button>
        </div>
      </div>
    </header>
  )
}
