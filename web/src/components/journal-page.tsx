import { useLastCampaignId } from '@/hooks/use-last-campaign-id'
import { PlayLink } from '@/components/play-link'

// FR-31/FR-32's journal (the event log, chronological with expandable
// audit records) lives inside /play as a side panel, same reasoning as
// /sheet: a deliberate information-architecture choice, not a persistence
// gap.
export function JournalPage() {
  const lastCampaignId = useLastCampaignId()
  return (
    <div className="flex flex-col items-center justify-center min-h-[40vh] gap-4 text-center">
      <h1 className="text-3xl font-bold tracking-tight text-foreground">Journal</h1>
      <p className="text-muted-foreground">
        The journal is shown alongside chat in{' '}
        <PlayLink campaignId={lastCampaignId} className="underline underline-offset-2">
          Play
        </PlayLink>
        .
      </p>
    </div>
  )
}
