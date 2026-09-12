import { useCallback, useEffect, useState } from 'react'

const STORAGE_KEY = 'pantrypilot.theme'
const THEMES = ['system', 'light', 'dark']

// Founder visual-correction pass: the luxury redesign's dark navy/gold
// system IS the product's visual identity now, so a fresh visitor must
// see it regardless of their OS light/dark preference -- a "system"
// default silently showed the light theme to anyone on a light-mode
// OS/browser, which is what triggered this correction pass. "system"
// remains a real, selectable option in the cycle below (functionality
// preserved); it is simply no longer what an unconfigured browser gets.
function readStoredTheme() {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    return THEMES.includes(stored) ? stored : 'dark'
  } catch {
    // Private browsing / storage blocked -- fall back to the dark
    // default rather than throwing.
    return 'dark'
  }
}
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
