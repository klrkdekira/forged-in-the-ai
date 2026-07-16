import { useState } from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'

import { apiClient } from '@/api/client'
import type { components } from '@/api/schema'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'

// FR-18: the campaign picker - create a new campaign, or resume one already
// on disk. This is the entry point every /play/$campaignId link ultimately
// depends on: there's no session without one.
export default function App() {
  const [newCampaignOpen, setNewCampaignOpen] = useState(false)
  const [loadCampaignOpen, setLoadCampaignOpen] = useState(false)

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] gap-6 text-center animate-in fade-in zoom-in duration-500">
      <h1 className="text-4xl md:text-6xl font-black tracking-tight text-foreground">
        Forged <span className="text-primary">AI</span>
      </h1>
      <p className="text-xl text-muted-foreground max-w-[600px]">
        A premium tabletop RPG engine for Forged in the Dark, powered by AI.
      </p>
      <div className="flex gap-4 mt-8">
        <Button type="button" size="lg" onClick={() => setNewCampaignOpen(true)}>
          New Campaign
        </Button>
        <Button type="button" variant="outline" size="lg" onClick={() => setLoadCampaignOpen(true)}>
          Load Campaign
        </Button>
      </div>

      <NewCampaignDialog open={newCampaignOpen} onOpenChange={setNewCampaignOpen} />
      <LoadCampaignDialog open={loadCampaignOpen} onOpenChange={setLoadCampaignOpen} />
    </div>
  )
}

type Character = components['schemas']['Character']
type Crew = components['schemas']['Crew']

// Uploaded sheets are trusted only as far as the server's own Pydantic
// validation goes (ADR-0006: the server schema is the validator, this
// client-side cast is just so TS doesn't fight an inherently-external blob).
async function readJsonFile<T>(file: File): Promise<T> {
  const text = await file.text()
  return JSON.parse(text) as T
}

// FR-8/G2: players bring their existing character (and crew) sheets rather
// than always starting from the fixed MVP starter - either a saved
// guided-entry file (cli/guided_entry.py's own output, listed via
// GET /api/characters) or a directly uploaded JSON export. There's no
// saved-file list for crews (no guided crew entry flow exists), so a crew
// is upload-only.
function NewCampaignDialog({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [savedCharacterId, setSavedCharacterId] = useState('')
  const [characterFile, setCharacterFile] = useState<File | null>(null)
  const [crewFile, setCrewFile] = useState<File | null>(null)
  const [importError, setImportError] = useState<string | null>(null)

  const savedCharacters = useQuery({
    queryKey: ['characters'],
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/api/characters')
      if (error) throw error
      return data
    },
    enabled: open,
  })

  const createCampaign = useMutation({
    mutationFn: async (campaignName: string) => {
      let character: Character | undefined
      if (characterFile) {
        character = await readJsonFile<Character>(characterFile)
      } else if (savedCharacterId) {
        const { data, error } = await apiClient.GET('/api/characters/{character_id}', {
          params: { path: { character_id: savedCharacterId } },
        })
        if (error) throw error
        character = data
      }
      const crew = crewFile ? await readJsonFile<Crew>(crewFile) : undefined

      const { data, error } = await apiClient.POST('/api/campaigns', {
        body: { name: campaignName, character, crew },
      })
      if (error) throw error
      return data
    },
    onSuccess: (campaign) => {
      onOpenChange(false)
      setName('')
      setSavedCharacterId('')
      setCharacterFile(null)
      setCrewFile(null)
      setImportError(null)
      navigate({ to: '/play/$campaignId', params: { campaignId: campaign.id } })
    },
    onError: () => {
      setImportError(
        'Could not create the campaign - check that any uploaded files are valid character/crew JSON.',
      )
    },
  })

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) return
    setImportError(null)
    createCampaign.mutate(trimmed)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>New Campaign</DialogTitle>
            <DialogDescription>
              Name your campaign, and optionally import an existing character and crew.
            </DialogDescription>
          </DialogHeader>
          <Input
            autoFocus
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Campaign name"
            className="mt-4"
          />

          <div className="mt-4 flex flex-col gap-1">
            <span className="text-xs font-semibold text-muted-foreground">
              Character (optional)
            </span>
            <select
              value={savedCharacterId}
              onChange={(event) => {
                setSavedCharacterId(event.target.value)
                if (event.target.value) setCharacterFile(null)
              }}
              className="h-8 rounded-lg border border-input bg-transparent px-2 text-sm"
              disabled={!!characterFile}
            >
              <option value="">Start fresh (no import)</option>
              {savedCharacters.data?.map((character) => (
                <option key={character.id} value={character.id}>
                  {character.name} ({character.playbook})
                </option>
              ))}
            </select>
            <label className="text-xs text-muted-foreground">
              or upload a character JSON file
              <input
                type="file"
                accept="application/json"
                className="mt-1 block text-xs"
                onChange={(event) => {
                  const file = event.target.files?.[0] ?? null
                  setCharacterFile(file)
                  if (file) setSavedCharacterId('')
                }}
              />
            </label>
          </div>

          <div className="mt-4 flex flex-col gap-1">
            <span className="text-xs font-semibold text-muted-foreground">Crew (optional)</span>
            <label className="text-xs text-muted-foreground">
              upload a crew JSON file
              <input
                type="file"
                accept="application/json"
                className="mt-1 block text-xs"
                onChange={(event) => setCrewFile(event.target.files?.[0] ?? null)}
              />
            </label>
          </div>

          {importError && <p className="mt-3 text-xs text-destructive">{importError}</p>}

          <DialogFooter className="mt-4">
            <Button type="submit" disabled={!name.trim() || createCampaign.isPending}>
              Create
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function LoadCampaignDialog({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const campaigns = useQuery({
    queryKey: ['campaigns'],
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/api/campaigns')
      if (error) throw error
      return data
    },
    enabled: open,
  })

  function handleOpenChange(next: boolean) {
    onOpenChange(next)
    if (next) queryClient.invalidateQueries({ queryKey: ['campaigns'] })
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Load Campaign</DialogTitle>
          <DialogDescription>Pick a campaign to resume.</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-1 mt-2 max-h-64 overflow-auto">
          {campaigns.isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
          {campaigns.data?.length === 0 && (
            <p className="text-sm text-muted-foreground">No campaigns yet.</p>
          )}
          {campaigns.data?.map((campaign) => (
            <Button
              key={campaign.id}
              type="button"
              variant="ghost"
              className="justify-start"
              onClick={() =>
                navigate({ to: '/play/$campaignId', params: { campaignId: campaign.id } })
              }
            >
              {campaign.name}
            </Button>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  )
}
