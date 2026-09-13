import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { fetchIngredientSuggestions } from '../services/api'
import { useDebouncedValue } from '../hooks/useDebouncedValue'
import { IngredientChipList } from './IngredientChip'
import './IngredientAutocomplete.css'

// Trusted, taxonomy-backed ingredient entry (ticket section 6-7).
// Selecting a suggestion adds a resolved chip; an unmatched free-text
// entry may still be added as an explicitly-marked "unrecognized" chip
// via "Use ... anyway" -- it is never silently promoted into the
// canonical taxonomy or pricing tables (that promotion only happens,
// if at all, deterministically server-side and is out of this
// component's authority entirely).
export function IngredientAutocomplete({ label, placeholder, items, onAdd, onRemove, helpText, variant = 'default' }) {
  const inputId = useId()
  const listboxId = useId()
  const [query, setQuery] = useState('')
  const [suggestions, setSuggestions] = useState([])
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)
  const debouncedQuery = useDebouncedValue(query, 200)
  const containerRef = useRef(null)
  const listboxRef = useRef(null)
  const requestSeqRef = useRef(0)
  const movedByKeyboardRef = useRef(false)

  const existingCanonicalIds = useMemo(
    () => new Set(items.filter((item) => item.canonical_id).map((item) => item.canonical_id)),
    [items],
  )
  // 2026-09-13 unified ingredient resolution ticket (section 4):
  // normalized-duplicate prevention for free-text entries, mirroring
  // existingCanonicalIds above for resolved ones.
  const existingUnresolvedLabels = useMemo(
    () => new Set(items.filter((item) => item.unresolved).map((item) => item.label.trim().toLowerCase())),
    [items],
  )

  useEffect(() => {
    const trimmed = debouncedQuery.trim()
    if (!trimmed) {
      setSuggestions([])
      setLoading(false)
      return
    }
    // Post-review fix (2026-09-08): a real-browser test found "No
    // exact match found" flashing for a well-covered term ("rice")
    // before its suggestions ever arrived. Root cause was that
    // suggestions.length === 0 was treated as "confirmed no match"
    // even while the debounced fetch was still pending -- under any
    // real network latency this briefly (or, on a slow connection,
    // not-so-briefly) showed the wrong empty state before the real
    // results replaced it. `loading` now distinguishes "still
    // resolving" from "resolved, genuinely nothing found," and a
    // request-sequence guard ignores a stale response/abort so an
    // in-flight newer request's loading state is never clobbered by an
    // older superseded one settling later.
    const seq = ++requestSeqRef.current
    setLoading(true)
    const controller = new AbortController()
    fetchIngredientSuggestions(trimmed, { signal: controller.signal })
      .then((results) => {
        if (requestSeqRef.current !== seq) return
        setSuggestions(results.filter((r) => !existingCanonicalIds.has(r.canonical_id)))
        setActiveIndex(-1)
      })
      .catch((err) => {
        if (requestSeqRef.current !== seq) return
        if (err.name !== 'AbortError') setSuggestions([])
      })
      .finally(() => {
        if (requestSeqRef.current === seq) setLoading(false)
      })
    return () => controller.abort()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedQuery])

  useEffect(() => {
    // Post-review fix (2026-09-08): ArrowDown/ArrowUp updated
    // activeIndex but never scrolled the listbox, so the highlighted
    // option could move outside the visible area. Only keyboard-driven
    // moves scroll. activeIndex is now ONLY ever set by ArrowDown/
    // ArrowUp (2026-09-13 hotfix: mouse hover used to also set it via
    // onMouseEnter, which meant Enter could "select" whatever
    // suggestion the cursor merely happened to be resting over --
    // never an explicit choice. Hover highlighting is pure CSS
    // (:hover in IngredientAutocomplete.css) now, so this guard is
    // belt-and-suspenders, not load-bearing, but kept for clarity.
    if (!movedByKeyboardRef.current) return
    movedByKeyboardRef.current = false
    if (activeIndex < 0 || !listboxRef.current) return
    // Positional lookup, not an id-based querySelector: useId() values
    // contain ':' characters that are not valid unescaped in a CSS id
    // selector. Options render in the same order as `suggestions`, so
    // the child at `activeIndex` is always the active option.
    const option = listboxRef.current.children[activeIndex]
    if (option && typeof option.scrollIntoView === 'function') {
      option.scrollIntoView({ block: 'nearest' })
    }
  }, [activeIndex])

  useEffect(() => {
    function handleClickOutside(event) {
      if (containerRef.current && !containerRef.current.contains(event.target)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  function selectSuggestion(suggestion) {
    if (existingCanonicalIds.has(suggestion.canonical_id)) return
    onAdd({
      id: suggestion.canonical_id,
      label: suggestion.display_name,
      canonical_id: suggestion.canonical_id,
      unresolved: false,
    })
    setQuery('')
    setSuggestions([])
    setOpen(false)
    setActiveIndex(-1)
  }

  // 2026-09-13 unified ingredient resolution ticket (section 4):
  // autocomplete is advisory, not mandatory -- the backend now performs
  // its own local/provider-catalogue/typo-corrected grounding on
  // whatever raw text is submitted (app.agent.ingredient_resolution),
  // so this component's only job is to let the user commit what they
  // actually typed, whether or not a matching suggestion exists.
  const MAX_INGREDIENT_LENGTH = 80 // matches RecommendRequest's own per-ingredient bound

  function addUnresolved() {
    const trimmed = query.trim()
    if (!trimmed) return
    if (trimmed.length > MAX_INGREDIENT_LENGTH) return
    if (existingUnresolvedLabels.has(trimmed.toLowerCase())) {
      // Already added -- just clear the input rather than silently
      // duplicating or showing an error for a harmless repeat.
      setQuery('')
      setSuggestions([])
      setOpen(false)
      setActiveIndex(-1)
      return
    }
    onAdd({ id: `unresolved:${trimmed.toLowerCase()}`, label: trimmed, canonical_id: null, unresolved: true })
    setQuery('')
    setSuggestions([])
    setOpen(false)
    setActiveIndex(-1)
  }

  function handleKeyDown(event) {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setOpen(true)
      movedByKeyboardRef.current = true
      setActiveIndex((prev) => Math.min(prev + 1, suggestions.length - 1))
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      movedByKeyboardRef.current = true
      setActiveIndex((prev) => Math.max(prev - 1, 0))
    } else if (event.key === 'Enter') {
      // This input lives inside SearchForm's <form> -- Enter must
      // always be prevented here regardless of outcome, or an empty/
      // pending Enter would fall through to submitting the whole
      // search form early (pre-existing behavior, preserved exactly).
      event.preventDefault()
      // A highlighted suggestion always wins (explicit selection).
      // Otherwise -- whether or not any suggestions are currently
      // showing -- Enter commits the raw typed text. Previously this
      // only worked when suggestions.length was exactly 0, so a query
      // like "chicken" (which DOES have suggestions -- specific cuts
      // -- but no exact generic match) could never be committed at
      // all; the user was stuck unable to add it without picking one
      // of the more specific cuts, which is exactly the silent
      // over-narrowing ticket section 12 forbids.
      if (activeIndex >= 0 && suggestions[activeIndex]) {
        selectSuggestion(suggestions[activeIndex])
      } else if (!isPending && query.trim()) {
        addUnresolved()
      }
    } else if (event.key === ',' && !isPending && query.trim() && activeIndex < 0) {
      // Comma commits free text too (ticket section 4), but only when
      // no suggestion is highlighted and there is real text to commit
      // -- otherwise a comma is just a normal character (e.g. typed
      // mid-word) and must not be swallowed.
      event.preventDefault()
      addUnresolved()
    } else if (event.key === 'Escape') {
      setOpen(false)
    }
  }

  // True from the moment the user stops matching the last-fetched
  // query (still inside the debounce window) through to the fetch
  // actually resolving -- see the effect above for why this exists.
  const isPending = query.trim() !== debouncedQuery.trim() || loading
  const showEmptyState = open && query.trim().length > 0 && !isPending && suggestions.length === 0
  const activeOptionId = activeIndex >= 0 ? `${listboxId}-option-${activeIndex}` : undefined

  return (
    <div className={`autocomplete${variant === 'primary' ? ' autocomplete--primary' : ''}`} ref={containerRef}>
      <label className="field-label" htmlFor={inputId}>
        {label}
      </label>
      <div className="autocomplete__input-wrap">
        <span className="autocomplete__icon" aria-hidden="true">
          🔍
        </span>
        <input
          id={inputId}
          className="field-input autocomplete__input"
          type="text"
          role="combobox"
          aria-expanded={open}
          aria-controls={listboxId}
          aria-activedescendant={activeOptionId}
          aria-autocomplete="list"
          autoComplete="off"
          placeholder={placeholder}
          value={query}
          onChange={(event) => {
            setQuery(event.target.value)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={handleKeyDown}
        />
      </div>
      {helpText ? <p className="field-help">{helpText}</p> : null}

      {open && suggestions.length > 0 ? (
        <ul className="autocomplete__listbox" role="listbox" id={listboxId} ref={listboxRef}>
          {suggestions.map((suggestion, index) => (
            <li
              key={suggestion.canonical_id}
              id={`${listboxId}-option-${index}`}
              role="option"
              aria-selected={index === activeIndex}
              className="autocomplete__option"
              onMouseDown={(event) => {
                event.preventDefault()
                selectSuggestion(suggestion)
              }}
            >
              {suggestion.display_name}
            </li>
          ))}
        </ul>
      ) : null}

      {open && isPending && query.trim().length > 0 && suggestions.length === 0 ? (
        <div className="autocomplete__listbox autocomplete__empty" aria-live="polite">
          <p className="autocomplete__empty-title">Searching…</p>
        </div>
      ) : null}

      {showEmptyState ? (
        <div className="autocomplete__listbox autocomplete__empty">
          <p className="autocomplete__empty-title">No exact match found</p>
          <button type="button" className="autocomplete__empty-action" onClick={addUnresolved}>
            Use &ldquo;{query.trim()}&rdquo; anyway
          </button>
        </div>
      ) : null}

      <IngredientChipList items={items} onRemove={onRemove} />
    </div>
  )
}
