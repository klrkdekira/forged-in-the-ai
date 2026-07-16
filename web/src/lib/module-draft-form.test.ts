import { describe, expect, it } from 'vitest'

import {
  EMPTY_DRAFT_FORM_VALUES,
  draftToFormValues,
  formValuesToDraft,
  type ModuleDraft,
} from './module-draft-form'

describe('draftToFormValues / formValuesToDraft', () => {
  it('round-trips a full draft through the form shape', () => {
    const draft: ModuleDraft = {
      playbooks: [
        {
          id: 'p1',
          name: 'Reaver',
          starting_action_dots: { prowl: 2, skirmish: 1 },
          special_ability_ids: ['a1'],
          xp_trigger: 'Address a challenge with violence.',
          item_ids: ['i1', 'i2'],
          contact_names: ['Ferra'],
        },
      ],
      crew_types: [
        {
          id: 'c1',
          name: 'Raiders',
          starting_upgrade_ids: ['u1'],
          special_ability_ids: ['a1'],
          claim_names: ['The Wharf'],
        },
      ],
      items: [{ id: 'i1', name: 'Cutlass', description: 'A curved blade.', load: 1, tags: ['weapon'] }],
      special_abilities: [
        { id: 'a1', name: 'Battleborn', description: 'You hit hard.', tags: ['combat'] },
      ],
      factions: [{ id: 'f1', name: 'The Raiders', description: 'Sea raiders.', tier_hint: 2 }],
      tables: [
        {
          name: 'Critical Injuries',
          columns: ['Roll', 'Result'],
          rows: [
            ['1', 'Lose a limb'],
            ['2', 'Blinded'],
          ],
        },
      ],
    }

    const roundTripped = formValuesToDraft(draftToFormValues(draft))

    expect(roundTripped).toEqual(draft)
  })

  it('treats an empty draft as empty form values', () => {
    const values = draftToFormValues({})

    expect(values).toEqual(EMPTY_DRAFT_FORM_VALUES)
  })

  it('parses blank optional fields back to null rather than empty strings', () => {
    const values = draftToFormValues({
      items: [{ id: 'i1', name: 'Rope', load: 1 }],
      factions: [{ id: 'f1', name: 'Nobody' }],
    })

    const draft = formValuesToDraft(values)

    expect(draft.items?.[0].description).toBeNull()
    expect(draft.factions?.[0].description).toBeNull()
    expect(draft.factions?.[0].tier_hint).toBeNull()
  })

  it('parses a "key:amount" comma list into a starting-dots dict', () => {
    const values = {
      ...EMPTY_DRAFT_FORM_VALUES,
      playbooks: [
        {
          id: 'p1',
          name: 'Test',
          starting_action_dots: 'prowl:2, hunt: 1',
          special_ability_ids: '',
          xp_trigger: 'x',
          item_ids: '',
          contact_names: '',
        },
      ],
    }

    const draft = formValuesToDraft(values)

    expect(draft.playbooks?.[0].starting_action_dots).toEqual({ prowl: 2, hunt: 1 })
  })

  it('parses newline-separated table rows into a list of comma-separated cells', () => {
    const values = {
      ...EMPTY_DRAFT_FORM_VALUES,
      tables: [{ name: 'T', columns: 'A, B', rows: '1, two\n3, four' }],
    }

    const draft = formValuesToDraft(values)

    expect(draft.tables?.[0].rows).toEqual([
      ['1', 'two'],
      ['3', 'four'],
    ])
  })
})
