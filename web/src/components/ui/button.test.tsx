import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Button } from './button'

describe('Button', () => {
  it('renders as a button with the default variant', () => {
    render(<Button>Roll the dice</Button>)
    const button = screen.getByRole('button', { name: 'Roll the dice' })
    expect(button).toBeInTheDocument()
    expect(button.className).toContain('bg-primary')
  })
})
