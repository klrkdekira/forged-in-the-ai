import { useState } from 'react'

import { Circle, Group, Layer, Line, Stage, Text } from 'react-konva'

import type {
  CrewSnapshot,
  FactionStatusSnapshot,
  JournalEntry,
  NpcSnapshot,
  RelationshipSnapshot,
} from '@/hooks/use-session-socket'
import { summarize } from '@/lib/journal-summarize'
import { layoutInRing } from '@/lib/map-layout'
import { type GraphNode, buildRelationshipGraph } from '@/lib/relationship-graph'

const WIDTH = 260
const HEIGHT = 200

const NODE_COLOR: Record<GraphNode['kind'], string> = {
  character: '#2563eb',
  crew: '#2563eb',
  npc: '#6b7280',
  faction: '#a855f7',
}

interface Selection {
  kind: 'node' | 'edge'
  key: string
  label: string
  history: number[]
}

// FR-34: an interactive graph of PCs, NPCs, factions, and the crew -
// selecting an entity shows its details, selecting an edge shows the
// relationship's type/status and the linked journal entries that shaped
// it, in order. Same computed-layout approach as the district/claim maps
// (no stored node positions), with the character/crew placed at the
// centre and everything else in a ring around them.
export function RelationshipMap({
  character,
  crew,
  npcs,
  factionStatuses,
  relationships,
  journalEntries,
}: {
  character: { name: string }
  crew: CrewSnapshot
  npcs: Record<string, NpcSnapshot>
  factionStatuses: Record<string, FactionStatusSnapshot>
  relationships: Record<string, RelationshipSnapshot>
  journalEntries: JournalEntry[]
}) {
  const [selection, setSelection] = useState<Selection | null>(null)
  const { nodes, edges } = buildRelationshipGraph({
    character,
    crew,
    npcs,
    factionStatuses,
    relationships,
  })

  const characterKey = `character:${character.name}`
  const crewKey = `crew:${crew.name}`
  const outerNodes = nodes.filter((node) => node.key !== characterKey && node.key !== crewKey)
  const outerPoints = layoutInRing(outerNodes.length, { width: WIDTH, height: HEIGHT })

  const positionByKey = new Map<string, { x: number; y: number }>([
    [characterKey, { x: WIDTH / 2, y: HEIGHT / 2 - 12 }],
    [crewKey, { x: WIDTH / 2, y: HEIGHT / 2 + 12 }],
    ...outerNodes.map((node, index) => [node.key, outerPoints[index]] as const),
  ])

  const linkedEntries =
    selection && selection.history.length > 0
      ? journalEntries.filter((entry) => selection.history.includes(entry.sequence))
      : []

  return (
    <div className="flex flex-col gap-2">
      <Stage width={WIDTH} height={HEIGHT}>
        <Layer>
          {edges.map((edge) => {
            const from = positionByKey.get(edge.fromKey)
            const to = positionByKey.get(edge.toKey)
            if (!from || !to) return null
            return (
              <Line
                key={edge.key}
                points={[from.x, from.y, to.x, to.y]}
                stroke={selection?.key === edge.key ? '#171717' : '#d4d4d4'}
                strokeWidth={selection?.key === edge.key ? 2 : 1}
                onClick={() =>
                  setSelection({ kind: 'edge', key: edge.key, label: edge.label, history: edge.history })
                }
              />
            )
          })}
          {nodes.map((node) => {
            const point = positionByKey.get(node.key)
            if (!point) return null
            return (
              <Group
                key={node.key}
                x={point.x}
                y={point.y}
                onClick={() => setSelection({ kind: 'node', key: node.key, label: node.label, history: [] })}
              >
                <Circle radius={node.kind === 'character' || node.kind === 'crew' ? 8 : 6} fill={NODE_COLOR[node.kind]} />
                <Text text={node.label} fontSize={10} fill="#6b7280" x={10} y={-5} />
              </Group>
            )
          })}
        </Layer>
      </Stage>

      {selection ? (
        <div className="rounded-md border border-border/50 bg-muted/30 p-2 text-xs">
          <div className="flex items-center justify-between">
            <span className="font-medium text-foreground">{selection.label}</span>
            <button
              type="button"
              onClick={() => setSelection(null)}
              className="text-muted-foreground hover:text-foreground"
            >
              Close
            </button>
          </div>
          {selection.kind === 'edge' &&
            (linkedEntries.length > 0 ? (
              <ul className="mt-1 flex flex-col gap-0.5 text-muted-foreground">
                {linkedEntries.map((entry) => (
                  <li key={entry.sequence}>{summarize(entry)}</li>
                ))}
              </ul>
            ) : (
              <p className="mt-1 text-muted-foreground">Nothing linked yet.</p>
            ))}
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">
          Select an entity or a connection for details.
        </p>
      )}
    </div>
  )
}
