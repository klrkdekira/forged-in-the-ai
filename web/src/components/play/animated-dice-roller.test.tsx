import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { AnimatedDiceRoller } from './animated-dice-roller'

describe('AnimatedDiceRoller', () => {
  it('only displays the supplied engine result and offers no client reroll', () => {
    render(
      <AnimatedDiceRoller
        open
        onOpenChange={vi.fn()}
        result={{
          dice: [6, 4],
          highest: 6,
          band: 'success',
          action: 'Prowl',
          position: 'risky',
          effect: 'standard',
        }}
      />,
    )

    expect(screen.getByText('Prowl')).toBeInTheDocument()
    expect(screen.getByText('2d Pool · Position: risky · Effect: standard')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /re-roll/i })).not.toBeInTheDocument()
  })
})
