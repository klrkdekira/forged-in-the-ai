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

// FR-31/FR-32: a chronological turn log; every entry expands to its full
// audit record (dice, position, effect, consequences for rolls; whatever
// payload the event carries for anything else). Filtering by type/phase/
// entity is v2 (TODO.md).
export function JournalPanel({ entries }: { entries: JournalEntry[] }) {
  return (
    <div className="flex h-full flex-col gap-2 overflow-auto rounded-lg border border-border/50 bg-background/50 p-4 text-sm">
      <span className="text-xs font-semibold text-muted-foreground">Journal</span>
      {entries.length === 0 ? (
        <p className="text-xs text-muted-foreground">Nothing recorded yet.</p>
      ) : (
        <ul className="flex flex-col gap-1">
          {entries.map((entry) => (
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
              </details>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
