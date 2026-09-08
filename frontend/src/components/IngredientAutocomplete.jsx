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
export function IngredientAutocomplete({ label, placeholder, items, onAdd, onRemove, helpText }) {
  const inputId = useId()
  const listboxId = useId()
  const [query, setQuery] = useState('')
  const [suggestions, setSuggestions] = useState([])
  const [open, setOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)
  const debouncedQuery = useDebouncedValue(query, 200)
  const containerRef = useRef(null)

  const existingCanonicalIds = useMemo(
    () => new Set(items.filter((item) => item.canonical_id).map((item) => item.canonical_id)),
    [items],
  )

  useEffect(() => {
    const trimmed = debouncedQuery.trim()
    if (!trimmed) {
      setSuggestions([])
      return
    }
    const controller = new AbortController()
    fetchIngredientSuggestions(trimmed, { signal: controller.signal })
      .then((results) => {
        setSuggestions(results.filter((r) => !existingCanonicalIds.has(r.canonical_id)))
        setActiveIndex(-1)
      })
      .catch((err) => {
        if (err.name !== 'AbortError') setSuggestions([])
      })
    return () => controller.abort()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedQuery])

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

  function addUnresolved() {
    const trimmed = query.trim()
    if (!trimmed) return
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
      setActiveIndex((prev) => Math.min(prev + 1, suggestions.length - 1))
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActiveIndex((prev) => Math.max(prev - 1, 0))
    } else if (event.key === 'Enter') {
      event.preventDefault()
      if (activeIndex >= 0 && suggestions[activeIndex]) {
        selectSuggestion(suggestions[activeIndex])
      } else if (suggestions.length === 0 && query.trim()) {
        addUnresolved()
      }
    } else if (event.key === 'Escape') {
      setOpen(false)
    }
  }

  const showEmptyState = open && query.trim().length > 0 && suggestions.length === 0
  const activeOptionId = activeIndex >= 0 ? `${listboxId}-option-${activeIndex}` : undefined

  return (
    <div className="autocomplete" ref={containerRef}>
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
        <ul className="autocomplete__listbox" role="listbox" id={listboxId}>
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
              onMouseEnter={() => setActiveIndex(index)}
            >
              {suggestion.display_name}
            </li>
          ))}
        </ul>
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
