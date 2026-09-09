import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { useSavedRecipes } from './useSavedRecipes'

function card(overrides = {}) {
  return {
    recipe_id: 'recipeapi_io:1',
    provider: 'recipeapi_io',
    name: 'Chicken Fried Rice',
    image_url: 'https://example.test/img.jpg',
    source_url: 'https://example.test/recipe/1',
    ...overrides,
  }
}

describe('useSavedRecipes', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('starts with nothing saved', () => {
    const { result } = renderHook(() => useSavedRecipes())
    expect(result.current.saved).toEqual([])
    expect(result.current.isSaved('recipeapi_io:1')).toBe(false)
  })

  it('toggling an unsaved card saves only the minimal provider-grounded fields', () => {
    const { result } = renderHook(() => useSavedRecipes())
    act(() => result.current.toggleSaved(card()))
    expect(result.current.isSaved('recipeapi_io:1')).toBe(true)
    expect(result.current.saved[0]).toMatchObject({
      recipeId: 'recipeapi_io:1',
      provider: 'recipeapi_io',
      title: 'Chicken Fried Rice',
      imageUrl: 'https://example.test/img.jpg',
      sourceUrl: 'https://example.test/recipe/1',
    })
    expect(typeof result.current.saved[0].timestamp).toBe('number')
    // No generated/full recipe content -- PantryPilot never generates
    // recipes, so none of that exists to store either.
    expect(result.current.saved[0]).not.toHaveProperty('instructions')
    expect(result.current.saved[0]).not.toHaveProperty('ingredients')
  })

  it('toggling an already-saved card unsaves it', () => {
    const { result } = renderHook(() => useSavedRecipes())
    act(() => result.current.toggleSaved(card()))
    act(() => result.current.toggleSaved(card()))
    expect(result.current.isSaved('recipeapi_io:1')).toBe(false)
    expect(result.current.saved).toEqual([])
  })

  it('removeSaved removes a specific recipe by id', () => {
    const { result } = renderHook(() => useSavedRecipes())
    act(() => result.current.toggleSaved(card({ recipe_id: 'a' })))
    act(() => result.current.toggleSaved(card({ recipe_id: 'b' })))
    act(() => result.current.removeSaved('a'))
    expect(result.current.isSaved('a')).toBe(false)
    expect(result.current.isSaved('b')).toBe(true)
  })

  it('clearSaved empties both state and storage', () => {
    const { result } = renderHook(() => useSavedRecipes())
    act(() => result.current.toggleSaved(card()))
    act(() => result.current.clearSaved())
    expect(result.current.saved).toEqual([])

    const { result: second } = renderHook(() => useSavedRecipes())
    expect(second.current.saved).toEqual([])
  })

  it('persists across a remount', () => {
    const { result, unmount } = renderHook(() => useSavedRecipes())
    act(() => result.current.toggleSaved(card()))
    unmount()

    const { result: second } = renderHook(() => useSavedRecipes())
    expect(second.current.isSaved('recipeapi_io:1')).toBe(true)
  })
})
