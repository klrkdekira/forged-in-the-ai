import { useMemo, useState } from 'react'

import type { JournalEntry } from '@/hooks/use-session-socket'

// FR-32: a one-line human-readable summary per event type; anything not
// listed falls back to a generic "<event_type> (<entity>)" line. Kept
// separate from the payload itself - the raw payload is always available
// in the expanded audit record below, this is just the collapsed label.
function summarize(entry: JournalEntry): string {
  const p = entry.payload
  switch (entry.event_type) {
    case 'player_message':
      return `Player: ${p.text}`
    case 'narration':
      return `GM: ${p.text}`
    case 'action_roll':
      return `${entry.entity_id} rolled ${p.action} (${p.band})`
    case 'fortune_roll':
      return `Fortune roll (${p.band})`
    case 'resistance_roll':
      return `${entry.entity_id} resisted (${p.stress_delta} stress)`
    case 'stress_marked':
      return `${entry.entity_id} marked ${p.amount} stress`
    case 'harm_marked':
      return `${entry.entity_id} took harm: ${p.name} (L${p.level})`
    case 'harm_healed':
      return `${entry.entity_id} healed one level of harm`
    case 'xp_marked':
      return `${entry.entity_id} marked XP (${p.track})`
    case 'coin_adjusted':
      return `${entry.entity_id} ${Number(p.amount) >= 0 ? 'gained' : 'spent'} ${Math.abs(Number(p.amount))} coin`
    case 'item_carried_set':
      return `${entry.entity_id} ${p.carried ? 'picked up' : 'stowed'} ${p.item_id}`
    case 'clock_created':
      return `Clock created: ${p.name}`
    case 'clock_ticked':
      return `${entry.entity_id} clock ticked by ${p.amount}`
    case 'phase_transitioned':
      return `Phase → ${p.phase}`
    case 'npc_created':
      return `NPC introduced: ${p.name}`
    case 'faction_status_changed':
      return `Faction ${entry.entity_id} status ${Number(p.delta) >= 0 ? '+' : ''}${p.delta}`
    case 'canon_fact_added':
      return `Canon: ${p.fact}`
    case 'x_card_invoked':
      return 'X-card invoked'
    default:
      return `${entry.event_type} (${entry.entity_type}:${entry.entity_id})`
  }
}

// FR-32: "type (narration / rolls / consequences / downtime)". Downtime
// activities have no GM tool wired up yet (TODO.md), so that bucket is
// reserved but always empty for now - the filter option still exists,
// ready for when one lands. "Other" isn't in the spec's four names, but a
// filterable journal needs an honest catch-all rather than silently
// hiding entries no one category fits (npc/canon/phase/safety-tool notes).
const TYPE_CATEGORIES = {
  narration: ['player_message', 'narration'],
  rolls: ['action_roll', 'fortune_roll', 'resistance_roll'],
  consequences: ['stress_marked', 'harm_marked', 'harm_healed', 'faction_status_changed', 'clock_ticked'],
  downtime: [] as string[],
} as const
type TypeCategory = keyof typeof TYPE_CATEGORIES | 'other'

function categoryOf(eventType: string): TypeCategory {
  for (const [category, eventTypes] of Object.entries(TYPE_CATEGORIES)) {
    if ((eventTypes as readonly string[]).includes(eventType)) return category as TypeCategory
  }
  return 'other'
}

// Tags each entry with the campaign phase active when it happened, by
// walking the log in order and tracking phase_transitioned events -
// entries don't carry their own phase, only transitions do.
function phaseAtEachSequence(entries: JournalEntry[]): Map<number, string> {
  let phase = 'free_play'
  const bySequence = new Map<number, string>()
  for (const entry of [...entries].sort((a, b) => a.sequence - b.sequence)) {
    if (entry.event_type === 'phase_transitioned') phase = String(entry.payload.phase)
    bySequence.set(entry.sequence, phase)
  }
  return bySequence
}

const TYPE_FILTER_LABELS: Record<'all' | TypeCategory, string> = {
  all: 'All',
  narration: 'Narration',
  rolls: 'Rolls',
  consequences: 'Consequences',
  downtime: 'Downtime',
  other: 'Other',
}

export function JournalPanel({
  entries,
  campaignId,
  onUndo,
}: {
  entries: JournalEntry[]
  campaignId: string
  onUndo: (sequence: number) => void
}) {
  const [typeFilter, setTypeFilter] = useState<'all' | TypeCategory>('all')
  const [phaseFilter, setPhaseFilter] = useState('all')
  const [entityFilter, setEntityFilter] = useState('all')

  const phaseBySequence = useMemo(() => phaseAtEachSequence(entries), [entries])
  const phases = useMemo(
    () => Array.from(new Set(phaseBySequence.values())),
    [phaseBySequence],
  )
  const entityTypes = useMemo(
    () => Array.from(new Set(entries.map((entry) => entry.entity_type))).sort(),
    [entries],
  )

  const visibleEntries = entries.filter((entry) => {
    if (typeFilter !== 'all' && categoryOf(entry.event_type) !== typeFilter) return false
    if (phaseFilter !== 'all' && phaseBySequence.get(entry.sequence) !== phaseFilter) return false
    if (entityFilter !== 'all' && entry.entity_type !== entityFilter) return false
    return true
  })

  function handleUndo(entry: JournalEntry) {
    // FR-19: irreversible (event log truncation, not a soft flag) - the
    // table needs to know that before agreeing, not after.
    const confirmed = window.confirm(
      `Undo to just after "${summarize(entry)}"? Everything after this point will be permanently erased.`,
    )
    if (confirmed) onUndo(entry.sequence)
  }

  return (
    <div className="flex h-full flex-col gap-2 overflow-auto rounded-lg border border-border/50 bg-background/50 p-4 text-sm">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-muted-foreground">Journal</span>
        {/* FR-20: "the story so far" as a downloadable markdown file,
            built server-side from the same narration/player_message
            events the journal is already rendering here. */}
        <a
          href={`/api/campaigns/${campaignId}/recap`}
          download
          className="text-xs text-muted-foreground underline underline-offset-2 hover:text-foreground"
        >
          Export recap
        </a>
      </div>

      <div className="flex flex-wrap items-center gap-1 text-[0.7rem]">
        {(Object.keys(TYPE_FILTER_LABELS) as Array<'all' | TypeCategory>).map((category) => (
          <button
            key={category}
            type="button"
            onClick={() => setTypeFilter(category)}
            className={`rounded-full px-2 py-0.5 ${
              typeFilter === category
                ? 'bg-primary/10 text-primary'
                : 'text-muted-foreground hover:bg-muted/40'
            }`}
          >
            {TYPE_FILTER_LABELS[category]}
          </button>
        ))}
      </div>

      <div className="flex gap-2 text-[0.7rem]">
        <select
          value={phaseFilter}
          onChange={(event) => setPhaseFilter(event.target.value)}
          className="rounded-md border border-border/50 bg-background/50 px-1 py-0.5 text-muted-foreground"
        >
          <option value="all">All phases</option>
          {phases.map((phase) => (
            <option key={phase} value={phase}>
              {phase}
            </option>
          ))}
        </select>
        <select
          value={entityFilter}
          onChange={(event) => setEntityFilter(event.target.value)}
          className="rounded-md border border-border/50 bg-background/50 px-1 py-0.5 text-muted-foreground"
        >
          <option value="all">All entities</option>
          {entityTypes.map((entityType) => (
            <option key={entityType} value={entityType}>
              {entityType}
            </option>
          ))}
        </select>
      </div>

      {entries.length === 0 ? (
        <p className="text-xs text-muted-foreground">Nothing recorded yet.</p>
      ) : visibleEntries.length === 0 ? (
        <p className="text-xs text-muted-foreground">Nothing matches these filters.</p>
      ) : (
        <ul className="flex flex-col gap-1">
          {visibleEntries.map((entry) => (
            <li key={entry.sequence}>
              <details className="group rounded-md border border-transparent open:border-border/50 open:bg-muted/30">
                <summary className="flex cursor-pointer items-baseline gap-2 rounded-md px-1 py-0.5 text-xs hover:bg-muted/40">
                  <span className="text-muted-foreground">
                    {new Date(entry.occurred_at).toLocaleTimeString()}
                  </span>
                  <span>{summarize(entry)}</span>
                </summary>
                <pre className="overflow-auto px-1 pb-1 text-[0.7rem] whitespace-pre-wrap text-muted-foreground">
                  {JSON.stringify(entry.payload, null, 2)}
                </pre>
                <button
                  type="button"
                  onClick={() => handleUndo(entry)}
                  className="px-1 pb-1 text-[0.7rem] text-muted-foreground underline underline-offset-2 hover:text-destructive"
                >
                  Undo to here
                </button>
              </details>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
