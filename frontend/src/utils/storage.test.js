import { beforeEach, describe, expect, it, vi } from 'vitest'
import { clearVersioned, readVersioned, writeVersioned } from './storage'

describe('versioned storage', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('round-trips data written at a given version', () => {
    writeVersioned('widgets', 1, [{ id: 'a' }])
    expect(readVersioned('widgets', 1, 'fallback')).toEqual([{ id: 'a' }])
  })

  it('returns the fallback when nothing has been stored yet', () => {
    expect(readVersioned('missing-key', 1, 'fallback')).toBe('fallback')
  })

  it('discards and falls back when the stored schema version does not match (ticket 5.1: "safely invalidate/migrate old data")', () => {
    writeVersioned('widgets', 1, [{ id: 'old-shape' }])
    expect(readVersioned('widgets', 2, 'fallback')).toBe('fallback')
  })

  it('discards malformed JSON without throwing', () => {
    window.localStorage.setItem('pantrypilot:widgets', 'not json{{{')
    expect(() => readVersioned('widgets', 1, 'fallback')).not.toThrow()
    expect(readVersioned('widgets', 1, 'fallback')).toBe('fallback')
  })

  it('clearVersioned removes only the namespaced key', () => {
    writeVersioned('widgets', 1, 'value')
    clearVersioned('widgets')
    expect(readVersioned('widgets', 1, 'fallback')).toBe('fallback')
  })

  it('degrades to the fallback instead of throwing when localStorage.getItem throws (private browsing)', () => {
    const spy = vi.spyOn(window.localStorage, 'getItem').mockImplementation(() => {
      throw new Error('storage disabled')
    })
    expect(() => readVersioned('widgets', 1, 'fallback')).not.toThrow()
    expect(readVersioned('widgets', 1, 'fallback')).toBe('fallback')
    spy.mockRestore()
  })

  it('degrades silently instead of throwing when localStorage.setItem throws (quota exceeded)', () => {
    const spy = vi.spyOn(window.localStorage, 'setItem').mockImplementation(() => {
      throw new Error('quota exceeded')
    })
    expect(() => writeVersioned('widgets', 1, 'value')).not.toThrow()
    spy.mockRestore()
  })
})
