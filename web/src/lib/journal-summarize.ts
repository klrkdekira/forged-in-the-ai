import type { JournalEntry } from '@/hooks/use-session-socket'

// FR-32: a one-line human-readable summary per event type; anything not
// listed falls back to a generic "<event_type> (<entity>)" line. Kept
// separate from the payload itself - the raw payload is always available
// in the expanded audit record below, this is just the collapsed label.
// Shared with relationship-map.tsx (FR-34's edge detail reuses it for the
// linked journal entries), so it lives outside journal-panel.tsx rather
// than being exported alongside a component.
export function summarize(entry: JournalEntry): string {
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
    case 'canon_location_added':
      return `Location discovered: ${p.location}`
    case 'canon_set':
      return `Setting created: ${p.setting_name}`
    case 'session_zero_configured':
      return 'Session zero: lines/veils/tone agreed'
    case 'relationship_updated':
      return `${p.subject_id} -> ${p.object_id}: ${p.kind}` + (p.status ? ` (${p.status})` : '')
    case 'x_card_invoked':
      return 'X-card invoked'
    default:
      return `${entry.event_type} (${entry.entity_type}:${entry.entity_id})`
  }
}
