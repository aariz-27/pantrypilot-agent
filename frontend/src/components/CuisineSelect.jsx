import { useId } from 'react'

// 2026-09-13 cuisine-alignment fix: exactly RecipeAPI.io's documented
// strict-cuisine filter enum (11 values), plus the "Any cuisine"
// sentinel. Must match backend/app/recipe/provider.py's
// SUPPORTED_STRICT_CUISINES exactly -- see that module's docstring for
// why non-strict cuisines (e.g. Indian/Pakistani, routed to the
// separate local-curated provider) are a different, untouched concern.
// A strict search for a cuisine outside this list previously reached
// RecipeAPI.io anyway and silently returned zero results every time.
const CUISINES = [
  'Any cuisine',
  'American',
  'Chinese',
  'French',
  'Greek',
  'Italian',
  'Japanese',
  'Mexican',
  'Portuguese',
  'Spanish',
  'Thai',
  'Turkish',
]

export function CuisineSelect({ value, onChange }) {
  const id = useId()
  return (
    <div>
      <label className="field-label" htmlFor={id}>
        Cuisine
      </label>
      <select
        id={id}
        className="field-select"
        value={value ?? 'Any cuisine'}
        onChange={(event) => onChange(event.target.value === 'Any cuisine' ? null : event.target.value)}
      >
        {CUISINES.map((c) => (
          <option key={c} value={c}>
            {c}
          </option>
        ))}
      </select>
    </div>
  )
}
