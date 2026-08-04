import { useState } from 'react'

import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  type Control,
  type UseFormRegister,
  useFieldArray,
  useForm,
} from 'react-hook-form'
import { z } from 'zod'

import { apiClient } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  type DraftFormValues,
  draftToFormValues,
  formValuesToDraft,
  type ModuleDraft,
} from '@/lib/module-draft-form'
import { apiErrorMessage } from '@/lib/api-error'

// FR-21/FR-22/FR-23: upload a rulebook, extract a best-effort draft, let
// the owner review and edit it (the server's ModuleDraft/ContentPack
// schemas are still the real validator, ADR-0006 - this form is UX only),
// then finalize and save it as a private module that joins the GM's
// retrieval corpus. A standalone page, not tied to any one campaign: a
// module is authored once and reused across campaigns.

const metadataSchema = z.object({
  id: z.string().min(1, 'Required'),
  name: z.string().min(1, 'Required'),
  description: z.string().min(1, 'Required'),
  version: z.string().min(1, 'Required'),
})

type Metadata = z.infer<typeof metadataSchema>

type Phase = 'upload' | 'extracting' | 'reviewing' | 'saved'

export function IngestionPage() {
  const [phase, setPhase] = useState<Phase>('upload')
  const [filename, setFilename] = useState('')
  const [sourceText, setSourceText] = useState('')
  const [draft, setDraft] = useState<ModuleDraft | null>(null)
  const [truncated, setTruncated] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const savedModules = useQuery({
    queryKey: ['ingestion-modules'],
    queryFn: async () => {
      const { data, error: fetchError } = await apiClient.GET('/api/ingestion/modules')
      if (fetchError) throw fetchError
      return data
    },
  })

  const extractText = useMutation({
    mutationFn: async (file: File) => {
      const body = new FormData()
      body.append('file', file)
      const { data, error: extractError } = await apiClient.POST('/api/ingestion/extract-text', {
        // openapi-fetch passes a FormData body straight to fetch (browser
        // sets the multipart Content-Type/boundary); the generated type
        // only describes the JSON shape the server ultimately sees.
        body: body as unknown as { file: string },
      })
      if (extractError) throw extractError
      return data
    },
    onSuccess: (data) => {
      setFilename(data.filename)
      setSourceText(data.text)
      setError(null)
    },
    onError: (mutationError) =>
      setError(apiErrorMessage(mutationError, 'Could not extract text from that file.')),
  })

  const extractDraft = useMutation({
    mutationFn: async (text: string) => {
      const { data, error: extractError } = await apiClient.POST('/api/ingestion/extract-module', {
        body: { text },
      })
      if (extractError) throw extractError
      return data
    },
    onSuccess: (data) => {
      setDraft(data.draft)
      setTruncated(data.truncated)
      setPhase('reviewing')
      setError(null)
    },
    onError: (mutationError) =>
      setError(
        apiErrorMessage(mutationError, 'Could not extract a draft - is an LLM backend configured?'),
      ),
  })

  function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (!file) return
    setPhase('extracting')
    extractText.mutate(file, {
      onSuccess: (data) => extractDraft.mutate(data.text),
      onError: () => setPhase('upload'),
    })
  }

  function startOver() {
    setPhase('upload')
    setFilename('')
    setSourceText('')
    setDraft(null)
    setTruncated(false)
    setError(null)
  }

  return (
    <div className="flex flex-col gap-6 pb-12">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">Ingest a rulebook</h1>
        <p className="text-sm text-muted-foreground">
          Upload a third-party Forged in the Dark hack (PDF, markdown, or plain text) to draft a
          private content pack from it. Nothing here is committed or shared - it stays in your own
          user data (NOTICE.md, C6).
        </p>
      </div>

      {(phase === 'upload' || phase === 'extracting') && (
        <div className="flex flex-col gap-2 rounded-lg border border-border/50 bg-background/50 p-4">
          <Label htmlFor="rulebook-file">Rulebook file</Label>
          <input
            id="rulebook-file"
            type="file"
            accept=".pdf,.md,.markdown,.txt"
            onChange={handleFileChange}
            disabled={phase === 'extracting'}
            className="text-sm"
          />
          {phase === 'extracting' && (
            <p className="text-xs text-muted-foreground">Extracting a draft…</p>
          )}
          {error && <p className="text-xs text-destructive">{error}</p>}
        </div>
      )}

      {phase === 'reviewing' && draft && (
        <DraftReviewForm
          filename={filename}
          sourceText={sourceText}
          draft={draft}
          truncated={truncated}
          onCancel={startOver}
          onSaved={() => {
            queryClient.invalidateQueries({ queryKey: ['ingestion-modules'] })
            setPhase('saved')
          }}
        />
      )}

      {phase === 'saved' && (
        <div className="flex flex-col gap-3 rounded-lg border border-border/50 bg-background/50 p-4">
          <p className="text-sm text-foreground">Module saved as private user data.</p>
          <Button type="button" variant="outline" className="self-start" onClick={startOver}>
            Ingest another
          </Button>
        </div>
      )}

      <div className="flex flex-col gap-2">
        <h2 className="text-sm font-semibold text-foreground">Saved modules</h2>
        {savedModules.isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
        {savedModules.data?.length === 0 && (
          <p className="text-sm text-muted-foreground">None yet.</p>
        )}
        {savedModules.data?.map((module) => (
          <div key={module.id} className="rounded-lg border border-border/50 p-3 text-sm">
            <div className="font-medium text-foreground">
              {module.name} <span className="text-xs text-muted-foreground">v{module.version}</span>
            </div>
            <p className="text-xs text-muted-foreground">{module.description}</p>
          </div>
        ))}
      </div>
    </div>
  )
}

function DraftReviewForm({
  filename,
  sourceText,
  draft,
  truncated,
  onCancel,
  onSaved,
}: {
  filename: string
  sourceText: string
  draft: ModuleDraft
  truncated: boolean
  onCancel: () => void
  onSaved: () => void
}) {
  const [error, setError] = useState<string | null>(null)
  const {
    register: registerMetadata,
    handleSubmit: handleMetadataSubmit,
    formState: { errors: metadataErrors },
  } = useForm<Metadata>({
    resolver: zodResolver(metadataSchema),
    defaultValues: {
      id: filename.replace(/\.[^.]+$/, '').toLowerCase().replace(/[^a-z0-9]+/g, '-'),
      name: filename,
      description: `Ingested from ${filename}`,
      version: '0.1.0',
    },
  })
  const { control, register, getValues } = useForm<DraftFormValues>({
    defaultValues: draftToFormValues(draft),
  })

  const finalizeAndSave = useMutation({
    mutationFn: async (metadata: Metadata) => {
      const draft = formValuesToDraft(getValues())
      const { data: pack, error: finalizeError } = await apiClient.POST(
        '/api/ingestion/finalize-module',
        { body: { ...metadata, draft } },
      )
      if (finalizeError) throw finalizeError
      const { error: saveError } = await apiClient.POST('/api/ingestion/modules', {
        body: { pack, source_text: sourceText },
      })
      if (saveError) throw saveError
    },
    onSuccess: onSaved,
    onError: (mutationError) =>
      setError(
        apiErrorMessage(mutationError, 'Could not save the module - check the fields above for issues.'),
      ),
  })

  return (
    <form
      onSubmit={handleMetadataSubmit((metadata) => finalizeAndSave.mutate(metadata))}
      className="flex flex-col gap-4"
    >
      {truncated && (
        <p className="rounded-lg bg-accent/40 px-3 py-2 text-xs text-muted-foreground">
          The source text was too long and had to be truncated before extraction - review closely,
          later sections of the book may be missing from this draft.
        </p>
      )}

      <div className="grid grid-cols-2 gap-3 rounded-lg border border-border/50 p-4">
        <div className="flex flex-col gap-1">
          <Label htmlFor="module-id">Module id</Label>
          <Input id="module-id" {...registerMetadata('id')} />
          {metadataErrors.id && (
            <span className="text-xs text-destructive">{metadataErrors.id.message}</span>
          )}
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="module-name">Name</Label>
          <Input id="module-name" {...registerMetadata('name')} />
          {metadataErrors.name && (
            <span className="text-xs text-destructive">{metadataErrors.name.message}</span>
          )}
        </div>
        <div className="flex flex-col gap-1 col-span-2">
          <Label htmlFor="module-description">Description</Label>
          <Input id="module-description" {...registerMetadata('description')} />
          {metadataErrors.description && (
            <span className="text-xs text-destructive">{metadataErrors.description.message}</span>
          )}
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="module-version">Version</Label>
          <Input id="module-version" {...registerMetadata('version')} />
          {metadataErrors.version && (
            <span className="text-xs text-destructive">{metadataErrors.version.message}</span>
          )}
        </div>
      </div>

      <PlaybooksSection control={control} register={register} />
      <CrewTypesSection control={control} register={register} />
      <ItemsSection control={control} register={register} />
      <SpecialAbilitiesSection control={control} register={register} />
      <FactionsSection control={control} register={register} />
      <TablesSection control={control} register={register} />

      {error && <p className="text-xs text-destructive">{error}</p>}

      <div className="flex gap-2">
        <Button type="submit" disabled={finalizeAndSave.isPending}>
          Finalize &amp; save
        </Button>
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </form>
  )
}

function FieldArraySection({
  title,
  fields,
  onAdd,
  onRemove,
  renderRow,
}: {
  title: string
  fields: { id: string }[]
  onAdd: () => void
  onRemove: (index: number) => void
  renderRow: (index: number) => React.ReactNode
}) {
  return (
    <div className="flex flex-col gap-2 rounded-lg border border-border/50 p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-foreground">{title}</h3>
        <Button type="button" variant="outline" size="sm" onClick={onAdd}>
          Add
        </Button>
      </div>
      {fields.length === 0 && <p className="text-xs text-muted-foreground">None yet.</p>}
      {fields.map((field, index) => (
        <div key={field.id} className="flex items-start gap-2 rounded-lg bg-muted/30 p-2">
          <div className="grid flex-1 grid-cols-2 gap-2">{renderRow(index)}</div>
          <Button
            type="button"
            variant="destructive"
            size="icon-sm"
            onClick={() => onRemove(index)}
            aria-label="Remove"
          >
            ×
          </Button>
        </div>
      ))}
    </div>
  )
}

function PlaybooksSection({
  control,
  register,
}: {
  control: Control<DraftFormValues>
  register: UseFormRegister<DraftFormValues>
}) {
  const { fields, append, remove } = useFieldArray({ control, name: 'playbooks' })
  return (
    <FieldArraySection
      title="Playbooks"
      fields={fields}
      onAdd={() =>
        append({
          id: '',
          name: '',
          starting_action_dots: '',
          special_ability_ids: '',
          xp_trigger: '',
          item_ids: '',
          contact_names: '',
        })
      }
      onRemove={remove}
      renderRow={(index) => (
        <>
          <Input placeholder="id" {...register(`playbooks.${index}.id`)} />
          <Input placeholder="name" {...register(`playbooks.${index}.name`)} />
          <Input
            placeholder="starting dots (prowl:2, hunt:1)"
            {...register(`playbooks.${index}.starting_action_dots`)}
          />
          <Input
            placeholder="special ability ids"
            {...register(`playbooks.${index}.special_ability_ids`)}
          />
          <Input placeholder="xp trigger" {...register(`playbooks.${index}.xp_trigger`)} />
          <Input placeholder="item ids" {...register(`playbooks.${index}.item_ids`)} />
          <Input placeholder="contact names" {...register(`playbooks.${index}.contact_names`)} />
        </>
      )}
    />
  )
}

function CrewTypesSection({
  control,
  register,
}: {
  control: Control<DraftFormValues>
  register: UseFormRegister<DraftFormValues>
}) {
  const { fields, append, remove } = useFieldArray({ control, name: 'crew_types' })
  return (
    <FieldArraySection
      title="Crew types"
      fields={fields}
      onAdd={() =>
        append({
          id: '',
          name: '',
          starting_upgrade_ids: '',
          special_ability_ids: '',
          claim_names: '',
        })
      }
      onRemove={remove}
      renderRow={(index) => (
        <>
          <Input placeholder="id" {...register(`crew_types.${index}.id`)} />
          <Input placeholder="name" {...register(`crew_types.${index}.name`)} />
          <Input
            placeholder="starting upgrade ids"
            {...register(`crew_types.${index}.starting_upgrade_ids`)}
          />
          <Input
            placeholder="special ability ids"
            {...register(`crew_types.${index}.special_ability_ids`)}
          />
          <Input placeholder="claim names" {...register(`crew_types.${index}.claim_names`)} />
        </>
      )}
    />
  )
}

function ItemsSection({
  control,
  register,
}: {
  control: Control<DraftFormValues>
  register: UseFormRegister<DraftFormValues>
}) {
  const { fields, append, remove } = useFieldArray({ control, name: 'items' })
  return (
    <FieldArraySection
      title="Items"
      fields={fields}
      onAdd={() => append({ id: '', name: '', description: '', load: '1', tags: '' })}
      onRemove={remove}
      renderRow={(index) => (
        <>
          <Input placeholder="id" {...register(`items.${index}.id`)} />
          <Input placeholder="name" {...register(`items.${index}.name`)} />
          <Input placeholder="description" {...register(`items.${index}.description`)} />
          <Input placeholder="load" type="number" {...register(`items.${index}.load`)} />
          <Input placeholder="tags" {...register(`items.${index}.tags`)} />
        </>
      )}
    />
  )
}

function SpecialAbilitiesSection({
  control,
  register,
}: {
  control: Control<DraftFormValues>
  register: UseFormRegister<DraftFormValues>
}) {
  const { fields, append, remove } = useFieldArray({ control, name: 'special_abilities' })
  return (
    <FieldArraySection
      title="Special abilities"
      fields={fields}
      onAdd={() => append({ id: '', name: '', description: '', tags: '' })}
      onRemove={remove}
      renderRow={(index) => (
        <>
          <Input placeholder="id" {...register(`special_abilities.${index}.id`)} />
          <Input placeholder="name" {...register(`special_abilities.${index}.name`)} />
          <Input
            placeholder="description"
            {...register(`special_abilities.${index}.description`)}
          />
          <Input placeholder="tags" {...register(`special_abilities.${index}.tags`)} />
        </>
      )}
    />
  )
}

function FactionsSection({
  control,
  register,
}: {
  control: Control<DraftFormValues>
  register: UseFormRegister<DraftFormValues>
}) {
  const { fields, append, remove } = useFieldArray({ control, name: 'factions' })
  return (
    <FieldArraySection
      title="Factions"
      fields={fields}
      onAdd={() => append({ id: '', name: '', description: '', tier_hint: '' })}
      onRemove={remove}
      renderRow={(index) => (
        <>
          <Input placeholder="id" {...register(`factions.${index}.id`)} />
          <Input placeholder="name" {...register(`factions.${index}.name`)} />
          <Input placeholder="description" {...register(`factions.${index}.description`)} />
          <Input placeholder="tier hint" type="number" {...register(`factions.${index}.tier_hint`)} />
        </>
      )}
    />
  )
}

function TablesSection({
  control,
  register,
}: {
  control: Control<DraftFormValues>
  register: UseFormRegister<DraftFormValues>
}) {
  const { fields, append, remove } = useFieldArray({ control, name: 'tables' })
  return (
    <FieldArraySection
      title="Tables"
      fields={fields}
      onAdd={() => append({ name: '', columns: '', rows: '' })}
      onRemove={remove}
      renderRow={(index) => (
        <>
          <Input placeholder="name" {...register(`tables.${index}.name`)} />
          <Input placeholder="columns" {...register(`tables.${index}.columns`)} />
          <textarea
            placeholder={'rows (one per line, comma-separated cells)'}
            {...register(`tables.${index}.rows`)}
            className="col-span-2 min-h-16 rounded-lg border border-input bg-transparent px-2.5 py-1 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
          />
        </>
      )}
    />
  )
}
