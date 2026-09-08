import { useId } from 'react'
import './DifficultySelector.css'

// Checkbox-based per the frozen product decision (post-review fix,
// 2026-09-08) -- replaces a prior dropdown implementation.
//
// Easy and Medium are always included and shown checked-but-disabled:
// the backend (UserConstraints.allow_hard_difficulty, evaluated in
// app.domain.constraint_evaluator) only ever gates Hard -- there is no
// mechanism to exclude Easy/Medium, and none is added here (no
// unnecessary backend business-rule change). The Hard checkbox is the
// one real, interactive control and maps 1:1 onto allow_hard_difficulty.
// Difficulty itself always comes from the grounded provider field
// (app.domain.models.Difficulty.from_raw) -- this control only filters
// already-grounded values, it never infers or assigns one.
export function DifficultySelector({ allowHard, onChange }) {
  const groupId = useId()
  const hardId = useId()

  return (
    <div>
      <span className="field-label" id={groupId}>
        Difficulty
      </span>
      <div className="difficulty-selector" role="group" aria-labelledby={groupId}>
        <label className="difficulty-selector__option difficulty-selector__option--locked">
          <input type="checkbox" checked readOnly disabled aria-label="Easy (always included)" />
          Easy
        </label>
        <label className="difficulty-selector__option difficulty-selector__option--locked">
          <input type="checkbox" checked readOnly disabled aria-label="Medium (always included)" />
          Medium
        </label>
        <label className="difficulty-selector__option">
          <input
            id={hardId}
            type="checkbox"
            checked={allowHard}
            onChange={(event) => onChange(event.target.checked)}
          />
          Hard
        </label>
      </div>
    </div>
  )
}
