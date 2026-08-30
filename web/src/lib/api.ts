/**
 * HTTP client for the Scrape-and-Publish backend.
 *
 * Requests go to `/api/...` which the Vite dev server proxies to the FastAPI
 * backend (see `vite.config.ts`). Override the target via `VITE_API_PROXY_TARGET`
 * or point `VITE_API_BASE_URL` at a deployed backend.
 */

import type { ScrapeRequestPayload } from '@/lib/url-adapter'
import type { Post, PostsCount, ScrapeResponse } from '@/lib/types'

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '/api'

export interface ApiError {
  message: string
  status?: number
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })

  if (!res.ok) {
    let message = `Request failed with status ${res.status}`
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') message = body.detail
      else if (body.detail && Array.isArray(body.detail) && body.detail[0]?.msg) {
        message = body.detail[0].msg
      }
    } catch {
      /* keep default message */
    }
    throw Object.assign(new Error(message), { status: res.status }) as ApiError
  }

  // 204 No Content (e.g. DELETE) has an empty body.
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

/** Scrape a URL and optionally publish the result as a WordPress post. */
export async function scrape(payload: ScrapeRequestPayload): Promise<ScrapeResponse> {
  return request<ScrapeResponse>('/scrape', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

/** List persisted posts, newest first. */
export async function listPosts(params?: {
  source?: string
  status?: string
  limit?: number
}): Promise<Post[]> {
  const q = new URLSearchParams()
  if (params?.source) q.set('source', params.source)
  if (params?.status) q.set('status', params.status)
  if (params?.limit) q.set('limit', String(params.limit))
  const qs = q.toString()
  return request<Post[]>(`/posts${qs ? `?${qs}` : ''}`)
}

/** Fetch a single persisted post by id. */
export async function getPost(id: number): Promise<Post> {
  return request<Post>(`/posts/${id}`)
}

/** Delete a persisted post. */
export async function deletePost(id: number): Promise<void> {
  return request<void>(`/posts/${id}`, { method: 'DELETE' })
}

/** Persist a scraped product directly as a post. */
export async function createPost(
  product: import('@/lib/types').ProductData,
  status?: string,
): Promise<Post> {
  const q = status ? `?status=${encodeURIComponent(status)}` : ''
  return request<Post>(`/posts${q}`, {
    method: 'POST',
    body: JSON.stringify(product),
  })
}

/** Get the total number of persisted posts. */
export async function countPosts(): Promise<number> {
  const res = await request<PostsCount>('/posts/count')
  return res.count
}

export interface FacebookLoginResponse {
  logged_in: boolean
  message: string
  cookies_saved: boolean
}

export interface FacebookStatusResponse {
  logged_in: boolean
  cookie_file: string | null
  cookie_count: number
}

/** Check whether a usable Facebook session exists. */
export async function facebookStatus(): Promise<FacebookStatusResponse> {
  return request<FacebookStatusResponse>('/scrape/facebook/status')
}

/** Kick off the interactive Facebook login (opens a browser, waits for user). */
export async function facebookLogin(timeout?: number): Promise<FacebookLoginResponse> {
  return request<FacebookLoginResponse>('/scrape/facebook/login', {
    method: 'POST',
    body: JSON.stringify({ timeout: timeout ?? 180 }),
  })
}

/** Ping the backend health endpoint (true when reachable). */
export async function isBackendHealthy(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/health`)
    return res.ok
  } catch {
    return false
  }
}
