import type { components } from '@/api/schema'

export type ModuleDraft = components['schemas']['ModuleDraft']

export interface PlaybookFormValues {
  id: string
  name: string
  starting_action_dots: string
  special_ability_ids: string
  xp_trigger: string
  item_ids: string
  contact_names: string
}

export interface CrewTypeFormValues {
  id: string
  name: string
  starting_upgrade_ids: string
  special_ability_ids: string
  claim_names: string
}

export interface ItemFormValues {
  id: string
  name: string
  description: string
  load: string
  tags: string
}

export interface SpecialAbilityFormValues {
  id: string
  name: string
  description: string
  tags: string
}

export interface FactionFormValues {
  id: string
  name: string
  description: string
  tier_hint: string
}

export interface TableFormValues {
  name: string
  columns: string
  rows: string
}

export interface DraftFormValues {
  playbooks: PlaybookFormValues[]
  crew_types: CrewTypeFormValues[]
  items: ItemFormValues[]
  special_abilities: SpecialAbilityFormValues[]
  factions: FactionFormValues[]
  tables: TableFormValues[]
}

export const EMPTY_DRAFT_FORM_VALUES: DraftFormValues = {
  playbooks: [],
  crew_types: [],
  items: [],
  special_abilities: [],
  factions: [],
  tables: [],
}

// FR-22: the draft's own shapes (nested lists, a dict, a table's rows as
// list-of-lists) don't map onto simple text inputs directly, so the form
// edits flat comma/newline-separated strings instead and these functions
// convert both ways - ADR-0006's "Zod for form UX only", the server's
// ModuleDraft schema is still what actually validates on submit.
function parseList(value: string): string[] {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}

function joinList(value: string[] | undefined): string {
  return (value ?? []).join(', ')
}

function parseDots(value: string): Record<string, number> {
  const dots: Record<string, number> = {}
  for (const pair of parseList(value)) {
    const [key, amount] = pair.split(':').map((part) => part.trim())
    if (key) dots[key] = Number(amount) || 0
  }
  return dots
}

function joinDots(value: Record<string, number> | undefined): string {
  return Object.entries(value ?? {})
    .map(([key, amount]) => `${key}:${amount}`)
    .join(', ')
}

function parseRows(value: string): string[][] {
  return value
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => parseList(line))
}

function joinRows(value: string[][] | undefined): string {
  return (value ?? []).map((row) => row.join(', ')).join('\n')
}

export function draftToFormValues(draft: ModuleDraft): DraftFormValues {
  return {
    playbooks: (draft.playbooks ?? []).map((playbook) => ({
      id: playbook.id,
      name: playbook.name,
      starting_action_dots: joinDots(playbook.starting_action_dots),
      special_ability_ids: joinList(playbook.special_ability_ids),
      xp_trigger: playbook.xp_trigger,
      item_ids: joinList(playbook.item_ids),
      contact_names: joinList(playbook.contact_names),
    })),
    crew_types: (draft.crew_types ?? []).map((crewType) => ({
      id: crewType.id,
      name: crewType.name,
      starting_upgrade_ids: joinList(crewType.starting_upgrade_ids),
      special_ability_ids: joinList(crewType.special_ability_ids),
      claim_names: joinList(crewType.claim_names),
    })),
    items: (draft.items ?? []).map((item) => ({
      id: item.id,
      name: item.name,
      description: item.description ?? '',
      load: String(item.load ?? 1),
      tags: joinList(item.tags),
    })),
    special_abilities: (draft.special_abilities ?? []).map((ability) => ({
      id: ability.id,
      name: ability.name,
      description: ability.description,
      tags: joinList(ability.tags),
    })),
    factions: (draft.factions ?? []).map((faction) => ({
      id: faction.id,
      name: faction.name,
      description: faction.description ?? '',
      tier_hint: faction.tier_hint == null ? '' : String(faction.tier_hint),
    })),
    tables: (draft.tables ?? []).map((table) => ({
      name: table.name,
      columns: joinList(table.columns),
      rows: joinRows(table.rows),
    })),
  }
}

export function formValuesToDraft(values: DraftFormValues): ModuleDraft {
  return {
    playbooks: values.playbooks.map((playbook) => ({
      id: playbook.id,
      name: playbook.name,
      starting_action_dots: parseDots(playbook.starting_action_dots),
      special_ability_ids: parseList(playbook.special_ability_ids),
      xp_trigger: playbook.xp_trigger,
      item_ids: parseList(playbook.item_ids),
      contact_names: parseList(playbook.contact_names),
    })),
    crew_types: values.crew_types.map((crewType) => ({
      id: crewType.id,
      name: crewType.name,
      starting_upgrade_ids: parseList(crewType.starting_upgrade_ids),
      special_ability_ids: parseList(crewType.special_ability_ids),
      claim_names: parseList(crewType.claim_names),
    })),
    items: values.items.map((item) => ({
      id: item.id,
      name: item.name,
      description: item.description || null,
      load: Number(item.load) || 0,
      tags: parseList(item.tags),
    })),
    special_abilities: values.special_abilities.map((ability) => ({
      id: ability.id,
      name: ability.name,
      description: ability.description,
      tags: parseList(ability.tags),
    })),
    factions: values.factions.map((faction) => ({
      id: faction.id,
      name: faction.name,
      description: faction.description || null,
      tier_hint: faction.tier_hint.trim() === '' ? null : Number(faction.tier_hint),
    })),
    tables: values.tables.map((table) => ({
      name: table.name,
      columns: parseList(table.columns),
      rows: parseRows(table.rows),
    })),
  }
}
