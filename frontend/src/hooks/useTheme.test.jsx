import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { useTheme } from './useTheme'

describe('useTheme', () => {
  beforeEach(() => {
    window.localStorage.clear()
    document.documentElement.removeAttribute('data-theme')
  })

  it('defaults to system theme with no data-theme attribute', () => {
    const { result } = renderHook(() => useTheme())
    expect(result.current.theme).toBe('system')
    expect(document.documentElement.getAttribute('data-theme')).toBeNull()
  })

  it('cycles system -> light -> dark -> system', () => {
    const { result } = renderHook(() => useTheme())
    act(() => result.current.cycleTheme())
    expect(result.current.theme).toBe('light')
    expect(document.documentElement.getAttribute('data-theme')).toBe('light')

    act(() => result.current.cycleTheme())
    expect(result.current.theme).toBe('dark')
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')

    act(() => result.current.cycleTheme())
    expect(result.current.theme).toBe('system')
    expect(document.documentElement.getAttribute('data-theme')).toBeNull()
  })

  it('persists an explicit choice to localStorage and restores it on next mount', () => {
    const { result, unmount } = renderHook(() => useTheme())
    act(() => result.current.setTheme('dark'))
    expect(window.localStorage.getItem('pantrypilot.theme')).toBe('dark')
    unmount()

    const { result: secondMount } = renderHook(() => useTheme())
    expect(secondMount.current.theme).toBe('dark')
  })

  it('falls back to system for a corrupted stored value', () => {
    window.localStorage.setItem('pantrypilot.theme', 'not-a-real-theme')
    const { result } = renderHook(() => useTheme())
    expect(result.current.theme).toBe('system')
  })
})
