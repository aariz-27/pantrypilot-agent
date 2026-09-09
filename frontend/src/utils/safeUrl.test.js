import { describe, expect, it } from 'vitest'
import { safeHttpUrl } from './safeUrl'

describe('safeHttpUrl', () => {
  it('allows http and https URLs', () => {
    expect(safeHttpUrl('https://example.test/recipe/1')).toBe('https://example.test/recipe/1')
    expect(safeHttpUrl('http://example.test/img.jpg')).toBe('http://example.test/img.jpg')
  })

  it('rejects javascript: URLs (untrusted provider data must never execute)', () => {
    expect(safeHttpUrl('javascript:alert(1)')).toBeNull()
  })

  it('rejects data: and other non-http schemes', () => {
    expect(safeHttpUrl('data:text/html,<script>alert(1)</script>')).toBeNull()
    expect(safeHttpUrl('vbscript:msgbox(1)')).toBeNull()
  })

  it('rejects null, undefined, and non-string input', () => {
    expect(safeHttpUrl(null)).toBeNull()
    expect(safeHttpUrl(undefined)).toBeNull()
    expect(safeHttpUrl(42)).toBeNull()
  })

  it('treats a relative-looking string as safe (never a script scheme, worst case a dead link)', () => {
    // Relative-reference resolution is intentionally permissive here --
    // the security property this guards is "never javascript:/data:/
    // vbscript:", not "always a well-formed absolute URL".
    expect(safeHttpUrl('not-a-real-path')).toBe('not-a-real-path')
  })
})
