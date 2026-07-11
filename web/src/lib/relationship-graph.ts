export interface GraphNode {
  key: string
  label: string
  kind: 'character' | 'crew' | 'npc' | 'faction'
}

export interface GraphEdge {
  key: string
  fromKey: string
  toKey: string
  label: string
  history: number[]
}

interface FactionStatusLike {
  faction_id: string
  status: number
  history: number[]
}

interface RelationshipLike {
  subject_type: string
  subject_id: string
  object_type: string
  object_id: string
  kind: string
  status: string | null
  history: number[]
}

const KNOWN_KINDS = new Set(['character', 'crew', 'npc', 'faction'])

function nodeKind(type: string): GraphNode['kind'] {
  return KNOWN_KINDS.has(type) ? (type as GraphNode['kind']) : 'npc'
}

// FR-34: an interactive graph of PCs, NPCs, factions, and the crew -
// assembled from two independent sources (FactionStatus's crew<->faction
// edges, and generic Relationship edges between any two entities) into
// one node/edge set the map can render, kept separate from the Konva
// rendering itself so the graph assembly is plain, testable data.
export function buildRelationshipGraph({
  character,
  crew,
  npcs,
  factionStatuses,
  relationships,
}: {
  character: { name: string }
  crew: { name: string }
  npcs: Record<string, { name: string }>
  factionStatuses: Record<string, FactionStatusLike>
  relationships: Record<string, RelationshipLike>
}): { nodes: GraphNode[]; edges: GraphEdge[] } {
  const characterKey = `character:${character.name}`
  const crewKey = `crew:${crew.name}`
  const nodesByKey = new Map<string, GraphNode>()
  nodesByKey.set(characterKey, { key: characterKey, label: character.name, kind: 'character' })
  nodesByKey.set(crewKey, { key: crewKey, label: crew.name, kind: 'crew' })

  for (const [id, npc] of Object.entries(npcs)) {
    nodesByKey.set(`npc:${id}`, { key: `npc:${id}`, label: npc.name, kind: 'npc' })
  }

  const edges: GraphEdge[] = []

  for (const status of Object.values(factionStatuses)) {
    const factionKey = `faction:${status.faction_id}`
    if (!nodesByKey.has(factionKey)) {
      nodesByKey.set(factionKey, { key: factionKey, label: status.faction_id, kind: 'faction' })
    }
    edges.push({
      key: `faction-status:${status.faction_id}`,
      fromKey: crewKey,
      toKey: factionKey,
      label: `${status.status >= 0 ? '+' : ''}${status.status}`,
      history: status.history,
    })
  }

  for (const [key, relationship] of Object.entries(relationships)) {
    const fromKey = `${relationship.subject_type}:${relationship.subject_id}`
    const toKey = `${relationship.object_type}:${relationship.object_id}`
    if (!nodesByKey.has(fromKey)) {
      nodesByKey.set(fromKey, {
        key: fromKey,
        label: relationship.subject_id,
        kind: nodeKind(relationship.subject_type),
      })
    }
    if (!nodesByKey.has(toKey)) {
      nodesByKey.set(toKey, {
        key: toKey,
        label: relationship.object_id,
        kind: nodeKind(relationship.object_type),
      })
    }
    edges.push({
      key,
      fromKey,
      toKey,
      label: relationship.status ? `${relationship.kind} (${relationship.status})` : relationship.kind,
      history: relationship.history,
    })
  }

  return { nodes: Array.from(nodesByKey.values()), edges }
}
