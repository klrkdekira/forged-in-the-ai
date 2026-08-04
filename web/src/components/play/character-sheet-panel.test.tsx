import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { CharacterSnapshot } from '@/hooks/use-session-socket'

import { CharacterSheetPanel } from './character-sheet-panel'

describe('CharacterSheetPanel server snapshot contract', () => {
  it('renders trauma choice and server-shaped armour fields', () => {
    const character = {
      name: 'Scoundrel',
      playbook: 'Test Playbook',
      trauma: { conditions: [] },
      trauma_pending: true,
      stress: { marked: 0 },
      harm: { entries: [] },
      armor: {
        has_armor: true,
        has_heavy_armor: false,
        has_special_armor: false,
        armor_used: true,
        heavy_armor_used: false,
        special_armor_used: false,
      },
      healing_clock: { name: 'Healing', kind: 'healing', segments: 4, filled: 1 },
      coin: 0,
      load: 0,
      items: [],
      playbook_xp: { marked: 0, segments: 8 },
      attribute_xp: {
        insight: { marked: 0, segments: 6 },
        prowess: { marked: 0, segments: 6 },
        resolve: { marked: 0, segments: 6 },
      },
    } as CharacterSnapshot

    render(<CharacterSheetPanel characterId="pc-1" character={character} onOperate={vi.fn()} />)

    expect(screen.getByText('Stress Overflow! Pick Trauma:')).toBeInTheDocument()
    expect(screen.getByText('Healing')).toBeInTheDocument()
    expect(screen.getByText('Armor')).toBeInTheDocument()
  })
})
