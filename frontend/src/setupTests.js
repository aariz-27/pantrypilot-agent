import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'

// Module F introduced localStorage-backed persistence (pantry, form
// prefs, history, saved recipes). jsdom's localStorage is shared
// across all tests in a file/run, so without this a value written by
// one test (e.g. an added pantry ingredient) would silently leak into
// the next test's initial render.
afterEach(() => {
  window.localStorage.clear()
})
