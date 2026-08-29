/**
 * URL Adapter for the Scrape-and-Publish pipeline.
 *
 * A framework-agnostic module that normalizes and validates a raw user URL
 * and turns it into a well-formed scrape request that the FastAPI backend
 * (`[POST] /scrape`) accepts.
 *
 * The source detection logic mirrors the backend (`BaseScraper.detect`):
 *   - hostname contains "daraz"  -> "daraz"
 *   - hostname contains "bikroy" -> "bikroy"
 *   - anything else               -> "generic"
 *
 * Keeping this logic here (and mirrored in the Flutter client later) lets us
 * give instant client-side feedback before hitting the network.
 */

export type ScrapeSource = 'daraz' | 'bikroy' | 'generic'

export interface NormalizedUrl {
  /** Fully-qualified, prepend-scheme URL (canonical form). */
  url: string
  /** Detected source adapter key. */
  source: ScrapeSource
  /** Detected hostname. */
  hostname: string
  /** True if the input had no scheme (e.g. was `daraz.com.bd/products/x`). */
  schemeWasInferred: boolean
}

export interface ScrapeRequestPayload {
  url: string
  source?: ScrapeSource
  publish?: boolean
}

export type UrlAdapterResult =
  | { ok: true; data: NormalizedUrl }
  | { ok: false; error: string }

const DEFAULT_SCHEME = 'https://'

/** Rough sanity check — a valid http(s) URL. */
const URL_PATTERN = /^https?:\/\/[^\s]+\.[^\s]{2,}/i

/**
 * Detect the scraper source from a hostname. Mirrors the backend registry.
 */
export function detectSource(hostname: string): ScrapeSource {
  const host = hostname.toLowerCase()
  if (host.includes('daraz')) return 'daraz'
  if (host.includes('bikroy')) return 'bikroy'
  return 'generic'
}

/**
 * Normalize a raw user input into a canonical, validated URL.
 *
 * Handles the common mistakes: surrounding whitespace, missing scheme,
 * and lowercase host normalization. Returns an error object when the input
 * cannot be turned into a plausible URL, so the UI can show inline feedback.
 */
export function normalizeUrl(rawInput: string): UrlAdapterResult {
  const trimmed = rawInput.trim()

  if (!trimmed) {
    return { ok: false, error: 'Please enter a URL.' }
  }

  let candidate = trimmed
  let schemeWasInferred = false

  if (!/^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(candidate)) {
    // No scheme on front — assume https.
    candidate = DEFAULT_SCHEME + candidate
    schemeWasInferred = true
  }

  let parsed: URL
  try {
    parsed = new URL(candidate)
  } catch {
    return { ok: false, error: 'That does not look like a valid URL.' }
  }

  if (parsed.protocol !== 'https:' && parsed.protocol !== 'http:') {
    return { ok: false, error: 'Only http(s) URLs are supported.' }
  }
  if (!parsed.hostname.includes('.')) {
    return { ok: false, error: 'The URL hostname looks incomplete (e.g. missing .com).' }
  }

  const normalized = parsed.toString()
  if (!URL_PATTERN.test(normalized)) {
    return { ok: false, error: 'That does not look like a valid URL.' }
  }

  return {
    ok: true,
    data: {
      url: normalized,
      source: detectSource(parsed.hostname),
      hostname: parsed.hostname,
      schemeWasInferred,
    },
  }
}

/**
 * Build the exact payload the FastAPI `[POST] /scrape` endpoint expects.
 * Source is omitted so the backend re-detects it (keeps single source of truth),
 * unless an explicit `source` override is supplied.
 */
export function buildScrapeRequest(
  normalized: NormalizedUrl,
  opts: { source?: ScrapeSource; publish?: boolean } = {},
): ScrapeRequestPayload {
  const payload: ScrapeRequestPayload = { url: normalized.url }
  if (opts.source && opts.source !== normalized.source) {
    payload.source = opts.source
  }
  if (opts.publish) {
    payload.publish = true
  }
  return payload
}
