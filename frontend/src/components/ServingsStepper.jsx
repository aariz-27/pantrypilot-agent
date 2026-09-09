import { useId } from 'react'
import './ServingsStepper.css'

const MIN_SERVINGS = 1
const MAX_SERVINGS = 20

export function ServingsStepper({ value, onChange }) {
  const labelId = useId()

  return (
    <div>
      <span className="field-label" id={labelId}>
        Servings
      </span>
      <div className="servings-stepper" role="group" aria-labelledby={labelId}>
        <button
          type="button"
          className="servings-stepper__button"
          onClick={() => onChange(Math.max(MIN_SERVINGS, value - 1))}
          disabled={value <= MIN_SERVINGS}
          aria-label="Decrease servings"
        >
          −
        </button>
        <span className="servings-stepper__value" aria-live="polite">
          {value}
        </span>
        <button
          type="button"
          className="servings-stepper__button"
          onClick={() => onChange(Math.min(MAX_SERVINGS, value + 1))}
          disabled={value >= MAX_SERVINGS}
          aria-label="Increase servings"
        >
          +
        </button>
      </div>
    </div>
  )
}
