import { useLastCampaignId } from '@/hooks/use-last-campaign-id'
import { PlayLink } from '@/components/play-link'

// FR-28's interactive sheet (stress/harm/XP/load/coin) lives inside /play
// as a side panel, not this route - a deliberate information-architecture
// choice (one active-session view, not a sheet page plus a separate chat
// page), not a persistence gap.
export function CharacterSheetPage() {
  const lastCampaignId = useLastCampaignId()
  return (
    <div className="flex flex-col items-center justify-center min-h-[40vh] gap-4 text-center">
      <h1 className="text-3xl font-bold tracking-tight text-foreground">Character Sheet</h1>
      <p className="text-muted-foreground">
        The interactive sheet is shown alongside chat in{' '}
        <PlayLink campaignId={lastCampaignId} className="underline underline-offset-2">
          Play
        </PlayLink>
        .
      </p>
    </div>
  )
}
