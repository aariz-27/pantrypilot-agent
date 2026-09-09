import { RecipeCard } from './RecipeCard'
import './RecipeGrid.css'

export function RecipeGrid({ cards, onOpen, isSaved }) {
  if (!cards.length) return null
  return (
    <div className="recipe-grid">
      {cards.map((card) => (
        <RecipeCard key={card.recipe_id} card={card} onOpen={onOpen} saved={isSaved ? isSaved(card.recipe_id) : false} />
      ))}
    </div>
  )
}
