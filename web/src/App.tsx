import { useState } from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'

import { apiClient } from '@/api/client'
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

function NewCampaignDialog({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const navigate = useNavigate()
  const [name, setName] = useState('')

  const createCampaign = useMutation({
    mutationFn: async (campaignName: string) => {
      const { data, error } = await apiClient.POST('/api/campaigns', {
        body: { name: campaignName },
      })
      if (error) throw error
      return data
    },
    onSuccess: (campaign) => {
      onOpenChange(false)
      setName('')
      navigate({ to: '/play/$campaignId', params: { campaignId: campaign.id } })
    },
  })

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) return
    createCampaign.mutate(trimmed)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>New Campaign</DialogTitle>
            <DialogDescription>Name your campaign to start a fresh crew.</DialogDescription>
          </DialogHeader>
          <Input
            autoFocus
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Campaign name"
            className="mt-4"
          />
          <DialogFooter>
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
