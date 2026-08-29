import { describe, expect, it } from 'vitest'

import { buildScrapeRequest, detectSource, normalizeUrl } from './url-adapter'

describe('detectSource', () => {
  it('detects daraz hosts', () => {
    expect(detectSource('www.daraz.com.bd')).toBe('daraz')
    expect(detectSource('www.daraz.lk')).toBe('daraz')
  })

  it('detects bikroy hosts', () => {
    expect(detectSource('bikroy.com')).toBe('bikroy')
  })

  it('falls back to generic', () => {
    expect(detectSource('example.com')).toBe('generic')
    expect(detectSource('medium.com')).toBe('generic')
  })
})

describe('normalizeUrl', () => {
  it('rejects empty / whitespace input', () => {
    expect(normalizeUrl('').ok).toBe(false)
    expect(normalizeUrl('   ').ok).toBe(false)
  })

  it('prepends https:// when scheme is missing', () => {
    const r = normalizeUrl('daraz.com.bd/products/x')
    expect(r.ok).toBe(true)
    if (r.ok) {
      expect(r.data.url).toBe('https://daraz.com.bd/products/x')
      expect(r.data.schemeWasInferred).toBe(true)
      expect(r.data.source).toBe('daraz')
    }
  })

  it('keeps an explicit scheme', () => {
    const r = normalizeUrl('http://bikroy.com/en/ads/1')
    expect(r.ok).toBe(true)
    if (r.ok) {
      expect(r.data.url).toBe('http://bikroy.com/en/ads/1')
      expect(r.data.schemeWasInferred).toBe(false)
    }
  })

  it('trims surrounding whitespace', () => {
    const r = normalizeUrl('  bikroy.com/en/ads/2  ')
    expect(r.ok).toBe(true)
    if (r.ok) expect(r.data.hostname).toBe('bikroy.com')
  })

  it('rejects non-http(s) schemes', () => {
    const r = normalizeUrl('ftp://example.com/file')
    expect(r.ok).toBe(false)
  })

  it('rejects garbage strings', () => {
    expect(normalizeUrl('not a url at all').ok).toBe(false)
    expect(normalizeUrl('https://').ok).toBe(false)
  })

  it('rejects hostnames without a TLD-ish dot', () => {
    expect(normalizeUrl('https://localhost').ok).toBe(false)
  })
})

describe('buildScrapeRequest', () => {
  it('omits source when it matches the detected one', () => {
    const norm = { url: 'https://daraz.com.bd/p', source: 'daraz' as const, hostname: 'x', schemeWasInferred: false }
    expect(buildScrapeRequest(norm)).toEqual({ url: 'https://daraz.com.bd/p' })
  })

  it('includes explicit source override when it differs', () => {
    // Normalizer detected 'generic', but the caller wants to force 'daraz'.
    const norm = { url: 'https://medium.com/p', source: 'generic' as const, hostname: 'x', schemeWasInferred: false }
    expect(buildScrapeRequest(norm, { source: 'daraz' })).toEqual({
      url: 'https://medium.com/p',
      source: 'daraz',
    })
  })

  it('adds publish flag', () => {
    const norm = { url: 'https://x.com/p', source: 'generic' as const, hostname: 'x', schemeWasInferred: false }
    expect(buildScrapeRequest(norm, { publish: true })).toEqual({
      url: 'https://x.com/p',
      publish: true,
    })
  })
})
