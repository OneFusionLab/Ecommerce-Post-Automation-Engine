import { useState, type FormEvent } from 'react'
import { Loader2, Link2, Send } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { normalizeUrl, type NormalizedUrl, type ScrapeSource } from '@/lib/url-adapter'

const SOURCE_BADGE: Record<ScrapeSource, string> = {
  daraz: 'bg-violet-500/15 text-violet-600 dark:text-violet-400 border-violet-500/30',
  bikroy: 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30',
  generic: 'bg-slate-500/15 text-slate-600 dark:text-slate-300 border-slate-500/30',
}

interface UrlFormProps {
  loading: boolean
  onSubmit: (normalized: NormalizedUrl) => void
}

export function UrlForm({ loading, onSubmit }: UrlFormProps) {
  const [raw, setRaw] = useState('')
  const [detected, setDetected] = useState<NormalizedUrl | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Re-run the adapter on every keystroke for instant client-side feedback.
  function handleChange(value: string) {
    setRaw(value)
    const result = normalizeUrl(value)
    if (result.ok) {
      setDetected(result.data)
      setError(null)
    } else {
      setDetected(null)
      setError(result.error)
    }
  }

  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const result = normalizeUrl(raw)
    if (!result.ok) {
      setError(result.error)
      return
    }
    setDetected(result.data)
    onSubmit(result.data)
  }

  return (
    <form
      className="space-y-3"
      onSubmit={submit}
      onKeyDown={(e) => {
        if (e.key === 'Enter') e.preventDefault()
      }}
    >
      <div className="flex flex-col gap-2 sm:flex-row">
        <div className="relative flex-1">
          <Link2 className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={raw}
            onChange={(e) => handleChange(e.target.value)}
            placeholder="Paste a product URL (Daraz, Bikroy or any page)…"
            className="pl-9"
            aria-invalid={!!error}
            disabled={loading}
          />
        </div>
        <div className="flex gap-2">
          <Button type="submit" disabled={loading || !!error || !raw.trim()}>
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
            Publish
          </Button>
        </div>
      </div>

      {/* Live adapter feedback */}
      {error && <p className="text-sm text-destructive">{error}</p>}

      {detected && !error && (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
          {detected.schemeWasInferred && (
            <span className="text-muted-foreground">
              Added <code className="text-xs">https://</code>
            </span>
          )}
          <Badge variant="outline" className={SOURCE_BADGE[detected.source]}>
            {detected.source} adapter
          </Badge>
          <span className="text-xs text-muted-foreground">{detected.hostname}</span>
        </div>
      )}
    </form>
  )
}
