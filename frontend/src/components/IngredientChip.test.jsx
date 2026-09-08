import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { IngredientChipList } from './IngredientChip'

describe('IngredientChipList', () => {
  it('renders nothing when there are no items', () => {
    const { container } = render(<IngredientChipList items={[]} onRemove={vi.fn()} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders a chip per item and marks unresolved ones distinctly', () => {
    render(
      <IngredientChipList
        items={[
          { id: 'rice', label: 'Rice', unresolved: false },
          { id: 'unresolved:kohlrabi', label: 'kohlrabi', unresolved: true },
        ]}
        onRemove={vi.fn()}
      />,
    )
    expect(screen.getByText('Rice')).toBeInTheDocument()
    expect(screen.getByText('kohlrabi')).toBeInTheDocument()
    expect(screen.getByText('(unrecognized)')).toBeInTheDocument()
  })

  it('calls onRemove with the item id when the remove button is clicked', async () => {
    const onRemove = vi.fn()
    render(<IngredientChipList items={[{ id: 'rice', label: 'Rice', unresolved: false }]} onRemove={onRemove} />)
    await userEvent.click(screen.getByRole('button', { name: 'Remove Rice' }))
    expect(onRemove).toHaveBeenCalledWith('rice')
  })
})
