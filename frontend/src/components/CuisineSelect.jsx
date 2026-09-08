import { useId } from 'react'

const CUISINES = [
  'Any cuisine',
  'Asian',
  'Italian',
  'Indian',
  'Pakistani',
  'Mexican',
  'Mediterranean',
  'American',
  'Chinese',
  'French',
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
