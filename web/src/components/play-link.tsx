import { Link } from '@tanstack/react-router'
import type { ReactNode } from 'react'

// FR-18: /play now requires a campaignId - a nav link to "play" has to
// pick between the last-opened campaign and the picker (/) depending on
// whether one is known, which are two different routes with different
// param shapes, not just two different strings for the same `to`.
export function PlayLink({
  campaignId,
  className,
  children,
}: {
  campaignId: string | null
  className?: string
  children: ReactNode
}) {
  if (campaignId) {
    return (
      <Link to="/play/$campaignId" params={{ campaignId }} className={className}>
        {children}
      </Link>
    )
  }
  return (
    <Link to="/" className={className}>
      {children}
    </Link>
  )
}
