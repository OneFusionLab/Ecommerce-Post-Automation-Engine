import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Clock, ExternalLink, Loader2, MapPin, Trash2 } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { deletePost, listPosts } from '@/lib/api'
import type { Post } from '@/lib/types'

const SOURCE_STYLE: Record<string, string> = {
  daraz: 'bg-violet-500/15 text-violet-600 dark:text-violet-400 border-violet-500/30',
  bikroy: 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30',
  facebook: 'bg-blue-500/15 text-blue-600 dark:text-blue-400 border-blue-500/30',
  generic: 'bg-slate-500/15 text-slate-600 dark:text-slate-300 border-slate-500/30',
}

const STATUS_STYLE: Record<string, string> = {
  published: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
  scraped: 'border-sky-500/40 bg-sky-500/10 text-sky-600 dark:text-sky-400',
  failed: 'border-destructive/40 bg-destructive/10 text-destructive',
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      dateStyle: 'medium',
      timeStyle: 'short',
    })
  } catch {
    return iso
  }
}

export function PostsPage({
  onDelete,
}: {
  onDelete?: (id: number) => void
}) {
  const [posts, setPosts] = useState<Post[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  async function load() {
    setLoading(true)
    setError(null)
    try {
      setPosts(await listPosts())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load posts')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function handleDelete(id: number) {
    if (!window.confirm('Delete this post?')) return
    try {
      await deletePost(id)
      setPosts((prev) => prev.filter((p) => p.id !== id))
      onDelete?.(id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete')
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">Posts</h1>
        <Button asChild variant="outline" size="sm">
          <Link to="/">+ New post</Link>
        </Button>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {loading && (
        <div className="flex items-center justify-center gap-2 py-12 text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading posts…
        </div>
      )}

      {!loading && posts.length === 0 && (
        <div className="rounded-xl border border-dashed p-10 text-center text-sm text-muted-foreground">
          No posts yet. Scrape a URL on the home page to create your first post.
        </div>
      )}

      <div className="space-y-3">
        {posts.map((post) => (
          <Card
            key={post.id}
            className="cursor-pointer transition-colors hover:border-ring"
            onClick={() => navigate(`/posts/${post.id}`)}
          >
            <CardContent className="flex items-start gap-4 p-4">
              {/* Thumbnail */}
              <div className="h-20 w-20 shrink-0 overflow-hidden rounded-lg border bg-muted">
                {post.images[0]?.url ? (
                  <img
                    src={post.images[0].url}
                    alt={post.title}
                    className="h-full w-full object-cover"
                    loading="lazy"
                  />
                ) : (
                  <div className="flex h-full w-full items-center justify-center text-muted-foreground">
                    <ExternalLink className="h-5 w-5" />
                  </div>
                )}
              </div>

              {/* Body */}
              <div className="min-w-0 flex-1 space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="font-semibold leading-snug">{post.title}</h2>
                  <Badge variant="outline" className={SOURCE_STYLE[post.source] ?? ''}>
                    {post.source}
                  </Badge>
                  <Badge variant="outline" className={STATUS_STYLE[post.status] ?? ''}>
                    {post.status}
                  </Badge>
                </div>

                {post.price && <p className="text-sm font-medium text-primary">{post.price}</p>}

                <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
                  {post.seller?.name && <span>{post.seller.name}</span>}
                  {post.seller?.location && (
                    <span className="inline-flex items-center gap-1">
                      <MapPin className="h-3 w-3" />
                      {post.seller.location}
                    </span>
                  )}
                  <span className="inline-flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    {formatDate(post.created_at)}
                  </span>
                </div>
              </div>

              {/* Delete */}
              <Button
                variant="ghost"
                size="icon"
                className="shrink-0 self-start text-muted-foreground hover:text-destructive"
                aria-label="Delete post"
                onClick={(e) => {
                  e.stopPropagation()
                  handleDelete(post.id)
                }}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
