import { useCallback, useEffect, useState } from 'react'

const STORAGE_KEY = 'pantrypilot.theme'
const THEMES = ['system', 'light', 'dark']

function readStoredTheme() {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    return THEMES.includes(stored) ? stored : 'system'
  } catch {
    // Private browsing / storage blocked -- fall back to system default
    // rather than throwing.
    return 'system'
  }
}

// Default is system theme (ticket section 4); an explicit user choice
// is remembered locally and wins over the OS preference until changed.
export function useTheme() {
  const [theme, setThemeState] = useState(readStoredTheme)

  useEffect(() => {
    const root = document.documentElement
    if (theme === 'system') {
      root.removeAttribute('data-theme')
    } else {
      root.setAttribute('data-theme', theme)
    }
  }, [theme])

  const setTheme = useCallback((next) => {
    setThemeState(next)
    try {
      window.localStorage.setItem(STORAGE_KEY, next)
    } catch {
      // Ignore storage failures -- theme still applies for this session.
    }
  }, [])

  const cycleTheme = useCallback(() => {
    setTheme(theme === 'system' ? 'light' : theme === 'light' ? 'dark' : 'system')
  }, [theme, setTheme])

  return { theme, setTheme, cycleTheme }
}
