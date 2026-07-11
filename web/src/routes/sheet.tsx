import { createFileRoute } from '@tanstack/react-router'

import { CharacterSheetPage } from '@/components/character-sheet-page'

export const Route = createFileRoute('/sheet')({
  component: CharacterSheetPage,
})
