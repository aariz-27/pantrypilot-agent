import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { useTheme } from './useTheme'

describe('useTheme', () => {
  beforeEach(() => {
    window.localStorage.clear()
    document.documentElement.removeAttribute('data-theme')
  })

  // Founder visual-correction pass: the dark navy/gold luxury theme is
  // now the product's default identity, not the OS preference -- a
  // "system" default was silently showing the light theme to anyone on
  // a light-mode browser, which is exactly what this correction pass
  // fixes. "system" is still a real, reachable option below.
  it('defaults to dark theme with data-theme="dark"', () => {
    const { result } = renderHook(() => useTheme())
    expect(result.current.theme).toBe('dark')
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
  })

  it('cycles dark -> system -> light -> dark', () => {
    const { result } = renderHook(() => useTheme())
    act(() => result.current.cycleTheme())
    expect(result.current.theme).toBe('system')
    expect(document.documentElement.getAttribute('data-theme')).toBeNull()

    act(() => result.current.cycleTheme())
    expect(result.current.theme).toBe('light')
    expect(document.documentElement.getAttribute('data-theme')).toBe('light')

    act(() => result.current.cycleTheme())
    expect(result.current.theme).toBe('dark')
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
  })

  it('persists an explicit choice to localStorage and restores it on next mount', () => {
    // Explicitly chooses 'light' (not the new 'dark' default) so this
    // test actually proves persistence, rather than merely matching
    // the default by coincidence.
    const { result, unmount } = renderHook(() => useTheme())
    act(() => result.current.setTheme('light'))
    expect(window.localStorage.getItem('pantrypilot.theme')).toBe('light')
    unmount()

    const { result: secondMount } = renderHook(() => useTheme())
    expect(secondMount.current.theme).toBe('light')
  })

  it('falls back to the dark default for a corrupted stored value', () => {
    window.localStorage.setItem('pantrypilot.theme', 'not-a-real-theme')
    const { result } = renderHook(() => useTheme())
    expect(result.current.theme).toBe('dark')
  })
})
