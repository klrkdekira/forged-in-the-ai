import { describe, expect, it } from 'vitest'

import type { JournalEntry } from '@/hooks/use-session-socket'

import { describeRollDecision, summarize } from './journal-summarize'

function entry(overrides: Partial<JournalEntry>): JournalEntry {
  return {
    sequence: 1,
    entity_type: 'character',
    entity_id: 'pc-2',
    event_type: 'companion_roll_decision',
    payload: {},
    occurred_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

describe('describeRollDecision', () => {
  it('describes a plain roll with no choices made', () => {
    expect(describeRollDecision({})).toBe('rolls as proposed')
  })

  it('describes pushing for bonus dice', () => {
    expect(describeRollDecision({ push_dice: true })).toBe('pushes for +1d')
  })

  it('describes accepting a Devil\'s Bargain', () => {
    expect(describeRollDecision({ devils_bargain: 'tick the Heat clock' })).toBe(
      "accepts a Devil's Bargain: tick the Heat clock",
    )
  })

  it('describes trading position for effect', () => {
    expect(describeRollDecision({ trade: 'worse_position_better_effect' })).toBe(
      'trades position for effect',
    )
  })

  it('describes being assisted by a teammate', () => {
    expect(describeRollDecision({ assist_character_id: 'pc-1' })).toBe('gets help from a teammate')
  })

  it('joins multiple choices', () => {
    expect(describeRollDecision({ push_dice: true, push_effect: true })).toBe(
      'pushes for +1d, pushes for +1 effect',
    )
  })
})

describe('summarize companion_roll_decision', () => {
  it('names the character and describes their decision', () => {
    const summary = summarize(entry({ payload: { name: 'Vex', push_dice: true } }))

    expect(summary).toBe('pc-2 pushes for +1d')
  })
})
