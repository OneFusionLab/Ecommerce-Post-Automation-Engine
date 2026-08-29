import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { ContentPreview } from '@/components/content-preview'
import { UrlForm } from '@/components/url-form'
import { listPosts, scrape } from '@/lib/api'
import type { Post, ProductData } from '@/lib/types'
import type { NormalizedUrl } from '@/lib/url-adapter'

export function HomePage({
  postCount,
  onPostChange,
}: {
  postCount: number
  onPostChange: () => void
}) {
  const [loading, setLoading] = useState(false)
  const [product, setProduct] = useState<ProductData | null>(null)
  const [recentPosts, setRecentPosts] = useState<Post[]>([])

  const loadRecent = useCallback(async () => {
    try {
      setRecentPosts((await listPosts({ limit: 3 })) ?? [])
    } catch {
      /* ignore recent-posts fetch errors */
    }
  }, [])

  useEffect(() => {
    loadRecent()
  }, [loadRecent, postCount])

  async function handleSubmit(normalized: NormalizedUrl) {
    setLoading(true)
    setProduct(null)
    try {
      const result = await scrape({ url: normalized.url, publish: false })
      setProduct(result.product)
      onPostChange()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Scraping failed'
      setProduct(null)
      alert(message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-bold tracking-tight">
          Turn a product link into a post
        </h1>
        <p className="text-sm text-muted-foreground">
          Paste a Daraz or Bikroy product URL. The engine extracts the data,
          downloads the images and persists it as a post.
        </p>
      </div>

      <UrlForm loading={loading} onSubmit={handleSubmit} />

      {product && !loading && <ContentPreview product={product} />}
      {!product && !loading && (
        <div className="rounded-xl border border-dashed p-10 text-center text-sm text-muted-foreground">
          Extracted content will appear here.
        </div>
      )}
      {loading && (
        <div className="space-y-3">
          <div className="h-40 animate-pulse rounded-xl bg-muted" />
          <div className="h-24 animate-pulse rounded-xl bg-muted" />
        </div>
      )}

      {recentPosts.length > 0 && postCount > 0 && (
        <div className="space-y-2 pt-2">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-medium text-muted-foreground">Recent posts</h2>
            <ButtonLink to="/posts">View all ({postCount})</ButtonLink>
          </div>
          <div className="grid gap-2 sm:grid-cols-3">
            {recentPosts.map((post) => (
              <Link
                key={post.id}
                to={`/posts/${post.id}`}
                className="group rounded-xl border p-3 transition-colors hover:border-ring"
              >
                <div className="mb-2 h-20 w-full overflow-hidden rounded-lg bg-muted">
                  {post.images[0]?.url ? (
                    <img
                      src={post.images[0].url}
                      alt={post.title}
                      className="h-full w-full object-cover"
                    />
                  ) : null}
                </div>
                <p className="line-clamp-2 text-sm font-medium group-hover:underline">
                  {post.title}
                </p>
                {post.price && (
                  <p className="mt-1 text-xs text-primary">{post.price}</p>
                )}
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function ButtonLink({ to, children }: { to: string; children: React.ReactNode }) {
  return (
    <Link to={to} className="text-xs text-primary hover:underline">
      {children}
    </Link>
  )
}
