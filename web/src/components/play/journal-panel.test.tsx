import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { JournalEntry } from '@/hooks/use-session-socket'

import { JournalPanel } from './journal-panel'

const ENTRIES: JournalEntry[] = [
  {
    sequence: 1,
    entity_type: 'session',
    entity_id: 'current',
    event_type: 'player_message',
    payload: { text: 'I pick the lock.' },
    occurred_at: '2026-01-01T00:00:00Z',
  },
  {
    sequence: 2,
    entity_type: 'character',
    entity_id: 'Scoundrel',
    event_type: 'stress_marked',
    payload: { amount: 2, triggered_trauma: false },
    occurred_at: '2026-01-01T00:00:01Z',
  },
  {
    sequence: 3,
    entity_type: 'session',
    entity_id: 'current',
    event_type: 'phase_transitioned',
    payload: { phase: 'score' },
    occurred_at: '2026-01-01T00:00:02Z',
  },
  {
    sequence: 4,
    entity_type: 'character',
    entity_id: 'Scoundrel',
    event_type: 'coin_adjusted',
    payload: { amount: 5 },
    occurred_at: '2026-01-01T00:00:03Z',
  },
  {
    sequence: 5,
    entity_type: 'crew',
    entity_id: 'The Fifth Foxglove',
    event_type: 'payoff',
    payload: { rep: 2, coin: 4, target_tier: 1, quiet: false },
    occurred_at: '2026-01-01T00:00:04Z',
  },
]

describe('JournalPanel', () => {
  it('renders every entry with no filters applied', () => {
    render(<JournalPanel entries={ENTRIES} campaignId="c1" onUndo={vi.fn()} />)
    expect(screen.getByText('Player: I pick the lock.')).toBeInTheDocument()
    expect(screen.getByText('Scoundrel marked 2 stress')).toBeInTheDocument()
    expect(screen.getByText('Phase → score')).toBeInTheDocument()
    expect(screen.getByText(/gained 5 coin/)).toBeInTheDocument()
    expect(screen.getByText('Payoff: 2 rep, 4 coin')).toBeInTheDocument()
  })

  it('filters by type category', async () => {
    const user = userEvent.setup()
    render(<JournalPanel entries={ENTRIES} campaignId="c1" onUndo={vi.fn()} />)

    await user.click(screen.getByRole('button', { name: 'Narration' }))

    expect(screen.getByText('Player: I pick the lock.')).toBeInTheDocument()
    expect(screen.queryByText('Scoundrel marked 2 stress')).not.toBeInTheDocument()
  })

  it('filters to the downtime category, now that it has content', async () => {
    // FR-32/TODO.md: the downtime bucket used to be permanently empty
    // because no GM tool produced a downtime-shaped event.
    const user = userEvent.setup()
    render(<JournalPanel entries={ENTRIES} campaignId="c1" onUndo={vi.fn()} />)

    await user.click(screen.getByRole('button', { name: 'Downtime' }))

    expect(screen.getByText('Payoff: 2 rep, 4 coin')).toBeInTheDocument()
    expect(screen.queryByText('Player: I pick the lock.')).not.toBeInTheDocument()
    expect(screen.queryByText('Scoundrel marked 2 stress')).not.toBeInTheDocument()
  })

  it('filters by the phase active when each entry happened', async () => {
    const user = userEvent.setup()
    render(<JournalPanel entries={ENTRIES} campaignId="c1" onUndo={vi.fn()} />)

    await user.selectOptions(screen.getByDisplayValue('All phases'), 'score')

    // the coin adjustment happened after the phase_transitioned event
    expect(screen.getByText(/gained 5 coin/)).toBeInTheDocument()
    // the player message and stress mark happened during free_play
    expect(screen.queryByText('Player: I pick the lock.')).not.toBeInTheDocument()
    expect(screen.queryByText('Scoundrel marked 2 stress')).not.toBeInTheDocument()
    // the transition itself is tagged with the phase it entered
    expect(screen.getByText('Phase → score')).toBeInTheDocument()
  })

  it('filters by entity type', async () => {
    const user = userEvent.setup()
    render(<JournalPanel entries={ENTRIES} campaignId="c1" onUndo={vi.fn()} />)

    await user.selectOptions(screen.getByDisplayValue('All entities'), 'character')

    expect(screen.getByText('Scoundrel marked 2 stress')).toBeInTheDocument()
    expect(screen.getByText(/gained 5 coin/)).toBeInTheDocument()
    expect(screen.queryByText('Player: I pick the lock.')).not.toBeInTheDocument()
  })

  it('confirms before sending an undo', async () => {
    const user = userEvent.setup()
    const onUndo = vi.fn()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    render(<JournalPanel entries={ENTRIES} campaignId="c1" onUndo={onUndo} />)

    await user.click(screen.getByText('Player: I pick the lock.'))
    await user.click(screen.getAllByRole('button', { name: 'Undo to here' })[0])

    expect(window.confirm).toHaveBeenCalled()
    expect(onUndo).toHaveBeenCalledWith(1)
  })
})
