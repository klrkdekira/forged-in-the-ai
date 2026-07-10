import { createFileRoute } from '@tanstack/react-router'

import { PlayPage } from '@/components/play/play-page'

export const Route = createFileRoute('/play')({
  component: PlayPage,
})
