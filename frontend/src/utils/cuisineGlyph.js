// Decorative-only category glyph for premium no-image fallbacks
// (RecipeCard, RecipeDetail). Never claims to depict the actual
// recipe -- purely a generic cuisine/category marker, and falls back
// to a neutral plate icon for anything unrecognized so it is never
// wrong, only generic.
const CUISINE_GLYPH = {
  italian: '🍝',
  indian: '🍛',
  pakistani: '🍛',
  mexican: '🌮',
  mediterranean: '🥗',
  american: '🍔',
  chinese: '🥡',
  french: '🥖',
  asian: '🍜',
}

export function cuisineGlyph(cuisine) {
  if (typeof cuisine !== 'string') return '🍽️'
  return CUISINE_GLYPH[cuisine.trim().toLowerCase()] ?? '🍽️'
}
