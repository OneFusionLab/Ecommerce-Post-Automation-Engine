import { NavLink, useLocation } from 'react-router-dom'
import { type ReactNode } from 'react'
import { ArrowLeft, Home, Layers, Scissors } from 'lucide-react'

import { useTheme } from '@/components/theme-provider'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

function ThemeToggle() {
  const { theme, setTheme } = useTheme()
  const isDark = theme === 'dark'
  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label="Toggle theme"
      onClick={() => setTheme(isDark ? 'light' : 'dark')}
    >
      {isDark ? '☀' : '☾'}
    </Button>
  )
}

export function Layout({
  children,
  postCount,
}: {
  children: ReactNode
  postCount?: number
}) {
  const location = useLocation()
  const onDetailPage = /^\/posts\/\d+/.test(location.pathname)

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-10 border-b bg-background/95 backdrop-blur">
        <div className="mx-auto flex max-w-3xl items-center justify-between gap-2 px-4 py-3">
          <div className="flex items-center gap-2 font-semibold">
            <Scissors className="h-5 w-5" />
            <span>Post Automation Engine</span>
          </div>

          <nav className="flex items-center gap-1">
            <Button asChild variant="ghost" size="sm">
              <NavLink to="/" end>
                <Home className="h-4 w-4" />
                Home
              </NavLink>
            </Button>
            <Button asChild variant="ghost" size="sm">
              <NavLink
                to="/posts"
                className={({ isActive }) => cn(isActive && 'bg-accent')}
              >
                <Layers className="h-4 w-4" />
                Posts{postCount !== undefined ? ` (${postCount})` : ''}
              </NavLink>
            </Button>
            <ThemeToggle />
          </nav>
        </div>
      </header>

      {onDetailPage && (
        <div className="mx-auto max-w-3xl px-4 pt-4">
          <Button asChild variant="outline" size="sm">
            <NavLink to="/posts">
              <ArrowLeft className="h-4 w-4" />
              Back to posts
            </NavLink>
          </Button>
        </div>
      )}

      <main className="mx-auto max-w-3xl space-y-4 px-4 py-6">{children}</main>
    </div>
  )
}
