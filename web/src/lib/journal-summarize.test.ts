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

describe('summarize dead-mechanics and faction events', () => {
  it('summarizes a trauma condition, flagging retirement', () => {
    expect(
      summarize(entry({ event_type: 'trauma_marked', payload: { condition: 'haunted', retired: false } })),
    ).toBe('pc-2 took trauma: haunted')
    expect(
      summarize(entry({ event_type: 'trauma_marked', payload: { condition: 'cold', retired: true } })),
    ).toBe('pc-2 took trauma: cold (retired)')
  })

  it('summarizes armor use and restoration', () => {
    expect(summarize(entry({ event_type: 'armor_used', payload: { armor_type: 'heavy' } }))).toBe(
      'pc-2 used heavy armor',
    )
    expect(summarize(entry({ event_type: 'armor_restored', payload: {} }))).toBe(
      'pc-2 restored their armor',
    )
  })

  it('summarizes stash changes and load level', () => {
    expect(summarize(entry({ event_type: 'stash_adjusted', payload: { amount: 3 } }))).toBe(
      'pc-2 stashed 3 stash',
    )
    expect(summarize(entry({ event_type: 'stash_adjusted', payload: { amount: -2 } }))).toBe(
      'pc-2 removed 2 stash',
    )
    expect(summarize(entry({ event_type: 'load_level_set', payload: { level: 'light' } }))).toBe(
      'pc-2 set load to light',
    )
  })

  it('summarizes crew development, turf, and claims', () => {
    expect(
      summarize(entry({ event_type: 'crew_developed', payload: { tier: 1, hold: 'weak' } })),
    ).toBe('Crew developed: Tier 1, weak hold')
    expect(summarize(entry({ event_type: 'crew_turf_adjusted', payload: { amount: 1 } }))).toBe(
      'Crew turf +1',
    )
    expect(
      summarize(
        entry({
          event_type: 'claim_controlled_set',
          payload: { claim_id: 'docks', controlled: true, name: 'The Docks', is_turf: true },
        }),
      ),
    ).toBe('Claim seized: The Docks (turf)')
  })

  it('summarizes a faction joining canon', () => {
    expect(
      summarize(
        entry({ event_type: 'canon_faction_added', payload: { name: 'The Red Circle', tier: 2 } }),
      ),
    ).toBe('Faction introduced: The Red Circle (Tier 2)')
  })
})
