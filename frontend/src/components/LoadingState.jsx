import { useEffect, useState } from 'react'
import './LoadingState.css'

// Generic, user-facing UX status labels only -- never the LLM's actual
// reasoning, raw prompts, tool payloads, or system prompt (ticket
// section 15 / docs/AGENTS.md). Since /api/recommend is a single
// request/response call (no streaming progress channel in this
// ticket's scope), steps advance on a fixed local timer purely to keep
// the wait from feeling like a blank screen -- they never claim to
// reflect the backend's actual real-time internal state.
const STEPS = [
  'Finding recipes…',
  'Checking what you already have…',
  'Estimating grocery cost…',
  'Ranking your best matches…',
]

const STEP_INTERVAL_MS = 1400

export function LoadingState() {
  const [activeStep, setActiveStep] = useState(0)

  useEffect(() => {
    const timer = setInterval(() => {
      setActiveStep((prev) => Math.min(prev + 1, STEPS.length - 1))
    }, STEP_INTERVAL_MS)
    return () => clearInterval(timer)
  }, [])

  return (
    <div className="loading-state" role="status" aria-live="polite">
      <div className="loading-state__spinner" aria-hidden="true" />
      <p className="loading-state__title">Finding the best recipes for you…</p>
      <ul className="loading-state__steps">
        {STEPS.map((step, index) => {
          const state = index < activeStep ? 'done' : index === activeStep ? 'active' : 'pending'
          return (
            <li key={step} className={`loading-state__step loading-state__step--${state}`}>
              <span aria-hidden="true">{state === 'done' ? '✓' : state === 'active' ? '●' : '○'}</span>
              {step}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
