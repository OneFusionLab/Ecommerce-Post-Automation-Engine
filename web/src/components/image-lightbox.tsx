import { useEffect, useState } from 'react'
import { ChevronLeft, ChevronRight, X } from 'lucide-react'

/**
 * Clickable image thumbnails that open a full-size preview overlay.
 * - Click a thumbnail to open
 * - Exit via the X button, clicking the backdrop, or pressing Escape
 * - Arrow keys / buttons navigate between images
 */
export function ClickableImage({
  src,
  alt,
  className,
  imgClassName,
}: {
  src?: string | null
  alt: string
  className?: string
  imgClassName?: string
}) {
  const [open, setOpen] = useState(false)
  if (!src) return null
  return (
    <>
      <button
        type="button"
        className={`block cursor-zoom-in overflow-hidden bg-muted ${className ?? ''}`}
        onClick={() => setOpen(true)}
        aria-label={`Preview ${alt}`}
      >
        <img src={src} alt={alt} className={`h-full w-full object-cover ${imgClassName ?? ''}`} loading="lazy" />
      </button>
      {open && <Lightbox images={[{ url: src, alt }]} index={0} onClose={() => setOpen(false)} />}
    </>
  )
}

/**
 * A gallery of images; each opens as a single preview (no cross-navigation).
 */
export function ClickableImageGrid({
  images,
  className,
}: {
  images: Array<{ url?: string | null; alt?: string }>
  className?: string
}) {
  return (
    <div className={className}>
      {images.map((img, i) => (
        <ClickableImage
          key={`${img.url}-${i}`}
          src={img.url}
          alt={img.alt ?? `Image ${i + 1}`}
          className="h-full w-full"
        />
      ))}
    </div>
  )
}

/**
 * Full gallery with prev/next navigation across all images.
 */
export function ImageGallery({
  images,
  containerClassName,
}: {
  images: Array<{ url?: string | null; alt?: string }>
  containerClassName?: string
}) {
  const [index, setIndex] = useState<number | null>(null)
  if (images.length === 0) return null
  return (
    <>
      <div className={containerClassName}>
        {images.map((img, i) => (
          <button
            key={`${img.url}-${i}`}
            type="button"
            className="block cursor-zoom-in overflow-hidden rounded-lg border bg-muted"
            style={{ aspectRatio: '1 / 1' }}
            onClick={() => setIndex(i)}
            aria-label={`Preview ${img.alt ?? `Image ${i + 1}`}`}
          >
            {img.url && (
              <img
                src={img.url}
                alt={img.alt ?? `Image ${i + 1}`}
                className="h-full w-full object-cover"
                loading="lazy"
              />
            )}
          </button>
        ))}
      </div>
      {index !== null && (
        <Lightbox
          images={images.map((img) => ({ url: img.url, alt: img.alt }))}
          index={index}
          onClose={() => setIndex(null)}
          onNavigate={(next) =>
            setIndex((next + images.length) % images.length)
          }
        />
      )}
    </>
  )
}

function Lightbox({
  images,
  index,
  onClose,
  onNavigate,
}: {
  images: Array<{ url?: string | null; alt?: string }>
  index: number
  onClose: () => void
  onNavigate?: (nextIndex: number) => void
}) {
  const current = images[index]

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
      else if (e.key === 'ArrowLeft' && onNavigate) onNavigate(index - 1)
      else if (e.key === 'ArrowRight' && onNavigate) onNavigate(index + 1)
    }
    window.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
    }
  }, [index, onClose, onNavigate])

  if (!current) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/90 p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Image preview"
    >
      <button
        type="button"
        className="absolute right-4 top-4 z-10 flex h-10 w-10 items-center justify-center rounded-full bg-white/10 text-white transition-colors hover:bg-white/25"
        onClick={onClose}
        aria-label="Close preview"
      >
        <X className="h-6 w-6" />
      </button>

      {onNavigate && images.length > 1 && (
        <>
          <button
            type="button"
            className="absolute left-4 top-1/2 z-10 flex h-10 w-10 -translate-y-1/2 items-center justify-center rounded-full bg-white/10 text-white transition-colors hover:bg-white/25"
            onClick={(e) => {
              e.stopPropagation()
              onNavigate(index - 1)
            }}
            aria-label="Previous image"
          >
            <ChevronLeft className="h-6 w-6" />
          </button>
          <button
            type="button"
            className="absolute right-4 top-1/2 z-10 flex h-10 w-10 -translate-y-1/2 items-center justify-center rounded-full bg-white/10 text-white transition-colors hover:bg-white/25"
            onClick={(e) => {
              e.stopPropagation()
              onNavigate(index + 1)
            }}
            aria-label="Next image"
          >
            <ChevronRight className="h-6 w-6" />
          </button>
        </>
      )}

      <div className="max-h-full max-w-full" onClick={(e) => e.stopPropagation()}>
        {current.url ? (
          <img
            src={current.url}
            alt={current.alt ?? 'Image preview'}
            className="max-h-[85vh] max-w-full object-contain"
          />
        ) : (
          <p className="text-white">No image</p>
        )}
        {onNavigate && images.length > 1 && (
          <p className="mt-3 text-center text-sm text-white/70">
            {index + 1} / {images.length}
          </p>
        )}
      </div>
    </div>
  )
}
