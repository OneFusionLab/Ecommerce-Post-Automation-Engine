import { useEffect, useState } from 'react'
import { Loader2, LogIn, UserCheck, UserX } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { facebookLogin, facebookStatus } from '@/lib/api'
import type { FacebookStatusResponse } from '@/lib/api'

export function FacebookLoginCard() {
  const [status, setStatus] = useState<FacebookStatusResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  async function refresh() {
    setLoading(true)
    try {
      setStatus(await facebookStatus())
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Could not check Facebook session')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    refresh()
  }, [])

  async function handleLogin() {
    setBusy(true)
    setMessage('Opening Facebook in your browser. Please log in there, then wait…')
    try {
      const res = await facebookLogin(180)
      setMessage(res.message)
      await refresh()
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setBusy(false)
    }
  }

  const loggedIn = status?.logged_in ?? false

  return (
    <Card>
      <CardContent className="flex flex-col gap-3 p-4">
        <div className="flex items-center gap-2">
          {busy || loading ? (
            <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
          ) : loggedIn ? (
            <UserCheck className="h-4 w-4 text-emerald-500" />
          ) : (
            <UserX className="h-4 w-4 text-muted-foreground" />
          )}
          <span className="text-sm font-medium">Facebook Marketplace</span>
          <span
            className={`ml-auto text-xs ${
              loggedIn ? 'text-emerald-600' : 'text-muted-foreground'
            }`}
          >
            {loggedIn ? 'Session active' : 'Not logged in'}
          </span>
        </div>

        <p className="text-xs text-muted-foreground">
          Marketplace requires a Facebook session to scrape. Log in once below —
          the browser will open for you to sign in, and the session is saved for
          reuse until it expires.
        </p>

        {!loggedIn && (
          <Button
            type="button"
            variant="secondary"
            size="sm"
            className="self-start"
            disabled={busy}
            onClick={handleLogin}
          >
            {busy ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <LogIn className="h-4 w-4" />
            )}
            {busy ? 'Waiting for login…' : 'Login with Facebook'}
          </Button>
        )}

        {message && <p className="text-xs text-muted-foreground">{message}</p>}
      </CardContent>
    </Card>
  )
}
