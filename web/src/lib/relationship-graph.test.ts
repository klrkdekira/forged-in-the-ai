import { describe, expect, it } from 'vitest'

import { buildRelationshipGraph } from './relationship-graph'

const CHARACTER = { name: 'Scoundrel' }
const CREW = { name: 'The Fifth Foxglove' }

describe('buildRelationshipGraph', () => {
  it('always includes the character and crew nodes', () => {
    const { nodes } = buildRelationshipGraph({
      character: CHARACTER,
      crew: CREW,
      npcs: {},
      factionStatuses: {},
      relationships: {},
    })

    expect(nodes).toEqual([
      { key: 'character:Scoundrel', label: 'Scoundrel', kind: 'character' },
      { key: 'crew:The Fifth Foxglove', label: 'The Fifth Foxglove', kind: 'crew' },
    ])
  })

  it('turns a faction status into a crew-to-faction edge', () => {
    const { nodes, edges } = buildRelationshipGraph({
      character: CHARACTER,
      crew: CREW,
      npcs: {},
      factionStatuses: { f1: { faction_id: 'f1', status: -2, history: [3] } },
      relationships: {},
    })

    expect(nodes).toContainEqual({ key: 'faction:f1', label: 'f1', kind: 'faction' })
    expect(edges).toContainEqual({
      key: 'faction-status:f1',
      fromKey: 'crew:The Fifth Foxglove',
      toKey: 'faction:f1',
      label: '-2',
      history: [3],
    })
  })

  it('turns a relationship into an edge and adds any missing endpoint nodes', () => {
    const { nodes, edges } = buildRelationshipGraph({
      character: CHARACTER,
      crew: CREW,
      npcs: { n1: { name: 'Vex' } },
      factionStatuses: {},
      relationships: {
        'character:Scoundrel:npc:n1': {
          subject_type: 'character',
          subject_id: 'Scoundrel',
          object_type: 'npc',
          object_id: 'n1',
          kind: 'rival',
          status: 'betrayed the crew',
          history: [4],
        },
      },
    })

    expect(nodes).toContainEqual({ key: 'npc:n1', label: 'Vex', kind: 'npc' })
    expect(edges).toContainEqual({
      key: 'character:Scoundrel:npc:n1',
      fromKey: 'character:Scoundrel',
      toKey: 'npc:n1',
      label: 'rival (betrayed the crew)',
      history: [4],
    })
  })

  it('falls back to the npc node style for an unrecognised entity type', () => {
    const { nodes } = buildRelationshipGraph({
      character: CHARACTER,
      crew: CREW,
      npcs: {},
      factionStatuses: {},
      relationships: {
        'npc:n1:score:s1': {
          subject_type: 'npc',
          subject_id: 'n1',
          object_type: 'score',
          object_id: 's1',
          kind: 'ally',
          status: null,
          history: [],
        },
      },
    })

    expect(nodes).toContainEqual({ key: 'score:s1', label: 's1', kind: 'npc' })
  })
})
