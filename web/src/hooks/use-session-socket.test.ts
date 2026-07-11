import { describe, expect, it } from 'vitest'

import { messagesFromLog, type JournalEntry } from './use-session-socket'

function entry(overrides: Partial<JournalEntry>): JournalEntry {
  return {
    sequence: 1,
    entity_type: 'session',
    entity_id: 'current',
    event_type: 'player_message',
    payload: {},
    occurred_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

describe('messagesFromLog', () => {
  it('rebuilds player, companion, and narration lines from the event log', () => {
    // FR-35: a player_message carrying a speaker is an AI companion's
    // line - after an undo it must rebuild under the companion's own
    // name, not as if the human typed it.
    const messages = messagesFromLog([
      entry({ sequence: 1, payload: { text: 'We move in.' } }),
      entry({ sequence: 2, event_type: 'narration', payload: { text: 'The door creaks.' } }),
      entry({
        sequence: 3,
        entity_type: 'character',
        entity_id: 'pc-2',
        payload: { text: 'Vex nods.', speaker: 'Vex' },
      }),
      entry({ sequence: 4, event_type: 'stress_marked', payload: { amount: 2 } }),
    ])

    expect(messages).toEqual([
      { kind: 'player', text: 'We move in.' },
      { kind: 'narration', text: 'The door creaks.', done: true },
      { kind: 'companion', name: 'Vex', text: 'Vex nods.' },
    ])
  })
})
