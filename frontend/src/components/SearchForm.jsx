import { useId, useState } from 'react'
import { IngredientAutocomplete } from './IngredientAutocomplete'
import { TimeSelector } from './TimeSelector'
import { ServingsStepper } from './ServingsStepper'
import { DifficultySelector } from './DifficultySelector'
import { CuisineSelect } from './CuisineSelect'
import './SearchForm.css'

export function SearchForm({ formState, onChange, onSubmit, submitting }) {
  const [showMore, setShowMore] = useState(false)
  const budgetId = useId()
  const strictId = useId()

  const hasRecognizedIngredient = formState.pantryItems.some((item) => !item.unresolved)
  const canSubmit = hasRecognizedIngredient && Boolean(formState.totalTimeMinutes) && !submitting

  function update(patch) {
    onChange({ ...formState, ...patch })
  }

  function handleSubmit(event) {
    event.preventDefault()
    if (canSubmit) onSubmit()
  }

  return (
    <form className="card search-form" onSubmit={handleSubmit} noValidate>
      <IngredientAutocomplete
        label="What ingredients do you have?"
        placeholder="Type an ingredient (e.g. rice, chicken, tomato...)"
        items={formState.pantryItems}
        onAdd={(item) => update({ pantryItems: [...formState.pantryItems, item] })}
        onRemove={(id) => update({ pantryItems: formState.pantryItems.filter((i) => i.id !== id) })}
        helpText="At least one recognized ingredient is required."
      />

      <div className="search-form__row">
        <TimeSelector value={formState.totalTimeMinutes} onChange={(v) => update({ totalTimeMinutes: v })} />
        <ServingsStepper value={formState.servings} onChange={(v) => update({ servings: v })} />
        <DifficultySelector
          allowHard={formState.allowHardDifficulty}
          onChange={(v) => update({ allowHardDifficulty: v })}
        />
        <CuisineSelect value={formState.cuisine} onChange={(v) => update({ cuisine: v })} />
      </div>

      <button
        type="button"
        className="search-form__more-toggle"
        onClick={() => setShowMore((prev) => !prev)}
        aria-expanded={showMore}
      >
        {showMore ? 'Fewer options ▲' : 'More options ▼'}
      </button>

      {showMore ? (
        <div className="search-form__more">
          <div>
            <label className="field-label" htmlFor={budgetId}>
              Additional grocery budget (AED)
            </label>
            <input
              id={budgetId}
              className="field-input"
              type="number"
              min={0}
              max={10000}
              inputMode="decimal"
              placeholder="Optional"
              value={formState.budgetAed ?? ''}
              onChange={(event) => {
                const parsed = Number(event.target.value)
                update({ budgetAed: event.target.value === '' ? null : Number.isFinite(parsed) ? parsed : null })
              }}
            />
          </div>

          <div>
            <div className={`search-form__checkbox-row${!formState.cuisine ? ' search-form__checkbox-row--locked' : ''}`}>
              <input
                id={strictId}
                type="checkbox"
                checked={formState.cuisineStrict}
                onChange={(event) => update({ cuisineStrict: event.target.checked })}
                disabled={!formState.cuisine}
              />
              <label htmlFor={strictId}>Strict cuisine match</label>
            </div>
            {!formState.cuisine ? <p className="field-help">Choose a cuisine first</p> : null}
          </div>

          <IngredientAutocomplete
            label="Exclude ingredients"
            placeholder="Type an ingredient to exclude..."
            items={formState.excludedItems}
            onAdd={(item) => update({ excludedItems: [...formState.excludedItems, item] })}
            onRemove={(id) => update({ excludedItems: formState.excludedItems.filter((i) => i.id !== id) })}
          />
        </div>
      ) : null}

      <button type="submit" className="btn btn-primary search-form__submit" disabled={!canSubmit}>
        {submitting ? 'Finding meals…' : 'Find meals'}
      </button>
    </form>
  )
}
