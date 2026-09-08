import { useId, useState } from 'react'
import './TimeSelector.css'

const PRESETS = [15, 30, 45, 60, 90]

// Total time = prep + cook, enforced deterministically server-side
// (ticket section 8). This control only picks the target minutes;
// PantryPilot's backend remains the sole authority on the calculation.
export function TimeSelector({ value, onChange }) {
  const inputId = useId()
  const [customMode, setCustomMode] = useState(value !== null && !PRESETS.includes(value))

  return (
    <div>
      <span className="field-label" id={`${inputId}-label`}>
        Total time
      </span>
      <div className="time-selector__options" role="group" aria-labelledby={`${inputId}-label`}>
        {PRESETS.map((minutes) => (
          <button
            key={minutes}
            type="button"
            className="time-selector__option"
            aria-pressed={!customMode && value === minutes}
            onClick={() => {
              setCustomMode(false)
              onChange(minutes)
            }}
          >
            {minutes} min
          </button>
        ))}
        <button
          type="button"
          className="time-selector__option"
          aria-pressed={customMode}
          onClick={() => setCustomMode(true)}
        >
          Custom
        </button>
      </div>
      {customMode ? (
        <div className="time-selector__custom">
          <label className="visually-hidden" htmlFor={inputId}>
            Custom total time in minutes
          </label>
          <input
            id={inputId}
            className="field-input"
            type="number"
            min={1}
            max={600}
            inputMode="numeric"
            value={value ?? ''}
            onChange={(event) => {
              const parsed = Number(event.target.value)
              onChange(Number.isFinite(parsed) && parsed > 0 ? parsed : null)
            }}
            placeholder="Minutes"
          />
        </div>
      ) : null}
    </div>
  )
}
