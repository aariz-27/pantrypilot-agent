import { useId } from 'react'

// Default filter is Easy+Medium (ticket section 10); the user may
// explicitly opt into Hard. This maps 1:1 to UserConstraints.
// allow_hard_difficulty server-side -- difficulty itself always comes
// from the grounded provider field, never inferred here.
export function DifficultySelector({ allowHard, onChange }) {
  const id = useId()
  return (
    <div>
      <label className="field-label" htmlFor={id}>
        Difficulty
      </label>
      <select
        id={id}
        className="field-select"
        value={allowHard ? 'all' : 'easy_medium'}
        onChange={(event) => onChange(event.target.value === 'all')}
      >
        <option value="easy_medium">Easy, Medium</option>
        <option value="all">Easy, Medium, Hard</option>
      </select>
    </div>
  )
}
