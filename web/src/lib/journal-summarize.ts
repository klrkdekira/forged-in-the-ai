import type { JournalEntry } from '@/hooks/use-session-socket'

// FR-16/FR-35: the same push/bargain/trade-off/assist choice a human makes
// in the roll negotiation dialog, but decided by PlayerAgent for an
// AI-controlled companion - shared between the journal's one-line summary
// and the chat's live status line so the two never describe it differently.
export function describeRollDecision(decision: {
  push_dice?: boolean
  push_effect?: boolean
  devils_bargain?: string | null
  trade?: string | null
  assist_character_id?: string | null
}): string {
  const parts: string[] = []
  if (decision.push_dice) parts.push('pushes for +1d')
  if (decision.push_effect) parts.push('pushes for +1 effect')
  if (decision.devils_bargain) parts.push(`accepts a Devil's Bargain: ${decision.devils_bargain}`)
  if (decision.trade === 'worse_position_better_effect') parts.push('trades position for effect')
  if (decision.trade === 'better_position_worse_effect') parts.push('trades effect for position')
  if (decision.assist_character_id) parts.push('gets help from a teammate')
  return parts.length > 0 ? parts.join(', ') : 'rolls as proposed'
}

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
    case 'trauma_marked':
      return `${entry.entity_id} took trauma: ${p.condition}` + (p.retired ? ' (retired)' : '')
    case 'armor_used':
      return `${entry.entity_id} used ${p.armor_type} armor`
    case 'armor_restored':
      return `${entry.entity_id} restored their armor`
    case 'stash_adjusted':
      return `${entry.entity_id} ${Number(p.amount) >= 0 ? 'stashed' : 'removed'} ${Math.abs(Number(p.amount))} stash`
    case 'load_level_set':
      return `${entry.entity_id} set load to ${p.level}`
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
    case 'canon_faction_added':
      return `Faction introduced: ${p.name} (Tier ${p.tier})`
    case 'canon_set':
      return `Setting created: ${p.setting_name}`
    case 'session_zero_configured':
      return 'Session zero: lines/veils/tone agreed'
    case 'relationship_updated':
      return `${p.subject_id} -> ${p.object_id}: ${p.kind}` + (p.status ? ` (${p.status})` : '')
    case 'x_card_invoked':
      return 'X-card invoked'
    case 'engagement_roll':
      return `Engagement roll (${p.band}) -> ${p.position}`
    case 'payoff':
      return `Payoff: ${p.rep} rep, ${p.coin} coin` + (p.quiet ? ' (quiet)' : '')
    case 'heat_added':
      return `${entry.entity_id} heat ${Number(p.amount) >= 0 ? '+' : ''}${p.amount}`
    case 'entanglement_roll':
      return `Entanglement: ${p.entanglement}`
    case 'asset_acquired':
      return `Asset acquired (${p.band}, quality ${p.quality})`
    case 'vice_indulged':
      return (
        `${entry.entity_id} indulged their vice (cleared ${p.stress_cleared} stress)` +
        (p.overindulged ? ', overindulged' : '')
      )
    case 'downtime_activity_rolled':
      return p.activity === 'craft'
        ? `${entry.entity_id} crafted (${p.band}, quality ${p.quality})`
        : `${entry.entity_id} rolled ${p.activity} (${p.band}, ${p.amount} ticks)`
    case 'flashback_taken':
      return `${entry.entity_id} took a flashback (${p.stress_cost} stress)`
    case 'action_advanced':
      return `${entry.entity_id} advanced ${p.action} to ${p.new_rating}`
    case 'special_ability_advanced':
      return `${entry.entity_id} gained special ability: ${p.ability_id}`
    case 'crew_special_ability_advanced':
      return `Crew gained special ability: ${p.ability_id}`
    case 'crew_upgrades_advanced':
      return `Crew upgrades marked: ${(p.upgrade_ids as string[]).join(', ')}`
    case 'crew_developed':
      return `Crew developed: Tier ${p.tier}, ${p.hold} hold`
    case 'crew_turf_adjusted':
      return `Crew turf ${Number(p.amount) >= 0 ? '+' : ''}${p.amount}`
    case 'claim_controlled_set':
      return `Claim ${p.controlled ? 'seized' : 'lost'}: ${p.name}` + (p.is_turf ? ' (turf)' : '')
    case 'companion_roll_decision':
      return `${entry.entity_id} ${describeRollDecision(p)}`
    default:
      return `${entry.event_type} (${entry.entity_type}:${entry.entity_id})`
  }
}
