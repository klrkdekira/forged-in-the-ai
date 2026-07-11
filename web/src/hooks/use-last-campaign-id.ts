import { useEffect } from 'react'

const STORAGE_KEY = 'forged-ai:last-campaign-id'

// FR-18: /play now requires a campaignId, so nav links that used to point
// at a bare /play need somewhere to go instead - the last campaign opened,
// remembered across reloads, falling back to the campaign picker (/) if
// none is known yet.
export function useLastCampaignId(campaignId?: string): string | null {
  useEffect(() => {
    if (campaignId) localStorage.setItem(STORAGE_KEY, campaignId)
  }, [campaignId])

  return campaignId ?? localStorage.getItem(STORAGE_KEY)
}
