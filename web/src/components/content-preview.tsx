import { BadgeCheck, Clock, ExternalLink, CheckCircle2, MapPin, Phone } from 'lucide-react'

import { ImageGallery } from '@/components/image-lightbox'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { ProductData, PublishResponse, SellerInfo } from '@/lib/types'

function SellerCard({ seller }: { seller: SellerInfo }) {
  const hasData =
    seller.name || seller.phone || seller.location || seller.response_time || seller.badge

  if (!hasData) return null

  return (
    <div className="flex items-start gap-3 rounded-lg border bg-muted/40 p-3">
      {seller.avatar_url && (
        <img
          src={seller.avatar_url}
          alt={seller.name ?? 'Seller'}
          className="h-11 w-11 shrink-0 rounded-full border object-cover"
          loading="lazy"
        />
      )}
      <div className="min-w-0 space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          {seller.name && <span className="text-sm font-semibold">{seller.name}</span>}
          {seller.badge && <Badge variant="outline">{seller.badge}</Badge>}
        </div>

        {seller.location && (
          <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <MapPin className="h-3 w-3 shrink-0" />
            {seller.location}
          </p>
        )}

        {seller.response_time && (
          <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Clock className="h-3 w-3 shrink-0" />
            {seller.response_time}
          </p>
        )}

        {seller.phone && (
          <a
            href={`tel:${seller.phone.replace(/\s+/g, '')}`}
            className="flex items-center gap-1.5 text-xs font-medium text-primary hover:underline"
          >
            <Phone className="h-3 w-3 shrink-0" />
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
  )
}

export function ContentPreview({
  product,
  publishDetail,
}: {
  product: ProductData
  publishDetail?: PublishResponse | null
}) {
  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-2">
          <CardTitle className="text-lg leading-snug">{product.title}</CardTitle>
          <Badge variant="outline" className="capitalize">
            {product.source}
          </Badge>
        </div>
        {product.price && (
          <p className="text-xl font-semibold text-primary">
            {product.price}
            {product.currency ? ` (${product.currency})` : ''}
          </p>
        )}
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Image gallery (click to preview, X / Esc to exit) */}
        {product.images.length > 0 && (
          <ImageGallery
            images={product.images.map((img) => ({ url: img.url }))}
            containerClassName="grid grid-cols-2 gap-2 sm:grid-cols-4"
          />
        )}

        {/* Description */}
        {product.description && (
          <div className="whitespace-pre-line text-sm text-muted-foreground">
            {product.description}
          </div>
        )}

        {/* Source link */}
        <a
          href={product.url}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
        >
          <ExternalLink className="h-3 w-3" />
          Original listing
        </a>

        {/* Seller */}
        <div className="pt-3">
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Seller
          </p>
          <SellerCard seller={product.seller} />
        </div>

        {/* Publish status */}
        {publishDetail && (
          <div
            className={`rounded-lg border p-3 text-sm ${
              publishDetail.success
                ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300'
                : 'border-destructive/40 bg-destructive/10 text-destructive'
            }`}
          >
            <div className="flex items-center gap-2 font-medium">
              {publishDetail.success && <CheckCircle2 className="h-4 w-4" />}
              {publishDetail.success
                ? `Published (${publishDetail.media_uploaded} media)`
                : 'Publish failed'}
            </div>
            {publishDetail.error && <p className="mt-1 text-xs">{publishDetail.error}</p>}
            {publishDetail.post_url && (
              <a
                href={publishDetail.post_url}
                target="_blank"
                rel="noreferrer"
                className="mt-1 inline-flex items-center gap-1 text-xs underline"
              >
                <ExternalLink className="h-3 w-3" />
                View post #{publishDetail.post_id}
              </a>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
