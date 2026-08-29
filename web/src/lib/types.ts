/**
 * TypeScript mirrors of the FastAPI response models
 * (see `src/scrape_engine/models/schemas.py`).
 */

export interface ImageData {
  url: string | null
  local_path: string | null
  width: number | null
  height: number | null
  size_bytes: number | null
  format: string | null
}

export interface SellerInfo {
  name: string | null
  phone: string | null
  location: string | null
  profile_url: string | null
  avatar_url: string | null
  badge: string | null
  member_since: string | null
  response_time: string | null
}

export interface ProductData {
  title: string
  source: string
  url: string
  price: string | null
  currency: string | null
  description: string | null
  images: ImageData[]
  seller: SellerInfo
  meta: Record<string, unknown>
}

export interface PublishResponse {
  success: boolean
  post_id: number | null
  post_url: string | null
  status: string | null
  error: string | null
  media_uploaded: number
}

export interface ScrapeResponse {
  product: ProductData
  published: boolean
  publish_detail: PublishResponse | null
}

export interface Post {
  id: number
  title: string
  slug: string
  source: string
  source_url: string
  price: string | null
  currency: string | null
  description: string | null
  images: Array<{ url: string | null } & Record<string, unknown>>
  seller: SellerInfo
  content_html: string | null
  status: string
  wp_post_id: number | null
  wp_post_url: string | null
  created_at: string
  updated_at: string
  published: boolean
}

export interface PostsCount {
  count: number
}
