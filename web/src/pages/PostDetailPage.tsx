import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  ArrowLeft,
  BadgeCheck,
  Clock,
  ExternalLink,
  Home,
  Loader2,
  MapPin,
  Phone,
  Trash2,
} from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ImageGallery } from '@/components/image-lightbox'
import { deletePost, getPost } from '@/lib/api'
import type { Post } from '@/lib/types'

const STATUS_STYLE: Record<string, string> = {
  published: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
  scraped: 'border-sky-500/40 bg-sky-500/10 text-sky-600 dark:text-sky-400',
  failed: 'border-destructive/40 bg-destructive/10 text-destructive',
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, { dateStyle: 'long' })
  } catch {
    return iso
  }
}

export function PostDetailPage({ onDelete }: { onDelete?: (id: number) => void }) {
  const { id } = useParams<{ id: string }>()
  const postId = Number(id)
  const navigate = useNavigate()

  const [post, setPost] = useState<Post | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const data = await getPost(postId)
        if (!cancelled) setPost(data)
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load post')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [postId])

  async function handleDelete() {
    if (!window.confirm('Delete this post?')) return
    try {
      await deletePost(postId)
      onDelete?.(postId)
      navigate('/posts')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete')
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center gap-2 py-16 text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin" />
        Loading post…
      </div>
    )
  }

  if (error || !post) {
    return (
      <div className="space-y-4 rounded-xl border p-8 text-center">
        <p className="text-sm text-destructive">{error ?? 'Post not found.'}</p>
        <Button asChild variant="outline">
          <Link to="/posts">
            <ArrowLeft className="h-4 w-4" />
            Back to posts
          </Link>
        </Button>
      </div>
    )
  }

  const seller = post.seller

  return (
    <article className="space-y-4">
      {/* Title block */}
      <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline" className="capitalize">
            {post.source}
          </Badge>
          <Badge variant="outline" className={STATUS_STYLE[post.status] ?? ''}>
            {post.status}
          </Badge>
          <span className="ml-auto inline-flex items-center gap-1 text-xs text-muted-foreground">
            <Clock className="h-3 w-3" />
            {formatDate(post.created_at)}
          </span>
        </div>
        <h1 className="text-2xl font-bold leading-tight">{post.title}</h1>
        {post.price && (
          <p className="text-xl font-semibold text-primary">
            {post.price}
            {post.currency ? ` (${post.currency})` : ''}
          </p>
        )}
      </div>

      {/* Images (click to preview, X / Esc to exit) */}
      {post.images.length > 0 && (
        <Card>
          <CardContent className="p-4">
            <ImageGallery
              images={post.images.map((img) => ({ url: img.url }))}
              containerClassName="grid grid-cols-2 gap-2 sm:grid-cols-4"
            />
          </CardContent>
        </Card>
      )}

      {/* Description */}
      {post.description && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Description</CardTitle>
          </CardHeader>
          <CardContent className="whitespace-pre-line text-sm text-muted-foreground">
            {post.description}
          </CardContent>
        </Card>
      )}

      {/* Seller */}
      {seller && (seller.name || seller.phone || seller.location || seller.badge) && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Seller</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-start gap-3">
              {seller.avatar_url && (
                <img
                  src={seller.avatar_url}
                  alt={seller.name ?? 'Seller'}
                  className="h-11 w-11 shrink-0 rounded-full border object-cover"
                />
              )}
              <div className="min-w-0 space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  {seller.name && <span className="text-sm font-semibold">{seller.name}</span>}
                  {seller.badge && <Badge variant="outline">{seller.badge}</Badge>}
                </div>
                {seller.location && (
                  <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <MapPin className="h-3 w-3" />
                    {seller.location}
                  </p>
                )}
                {seller.response_time && (
                  <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <Clock className="h-3 w-3" />
                    {seller.response_time}
                  </p>
                )}
                {seller.phone && (
                  <a
                    href={`tel:${seller.phone.replace(/\s+/g, '')}`}
                    className="flex items-center gap-1.5 text-xs font-medium text-primary hover:underline"
                  >
                    <Phone className="h-3 w-3" />
                    {seller.phone}
                  </a>
                )}
                {seller.profile_url && (
                  <a
                    href={seller.profile_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
                  >
                    <BadgeCheck className="h-3 w-3" />
                    View seller profile
                  </a>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Publish / source */}
      <Card>
        <CardContent className="flex flex-wrap items-center justify-between gap-2 p-4 text-sm">
          {post.wp_post_url ? (
            <a
              href={post.wp_post_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-primary hover:underline"
            >
              <ExternalLink className="h-4 w-4" />
              View on WordPress (post #{post.wp_post_id})
            </a>
          ) : (
            <span className="text-muted-foreground">Not published to WordPress</span>
          )}
          {post.source_url && (
            <a
              href={post.source_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-muted-foreground hover:text-foreground"
            >
              <ExternalLink className="h-4 w-4" />
              Original listing
            </a>
          )}
        </CardContent>
      </Card>

      {/* Actions */}
      <div className="flex justify-between">
        <Button asChild variant="outline" size="sm">
          <Link to="/posts">
            <ArrowLeft className="h-4 w-4" />
            Back
          </Link>
        </Button>
        <div className="flex gap-2">
          <Button asChild variant="outline" size="sm">
            <Link to="/">
              <Home className="h-4 w-4" />
              Home
            </Link>
          </Button>
          <Button variant="ghost" size="sm" onClick={handleDelete} className="text-destructive">
            <Trash2 className="h-4 w-4" />
            Delete
          </Button>
        </div>
      </div>
    </article>
  )
}
