import { createFileRoute } from '@tanstack/react-router'

import { IngestionPage } from '@/components/ingestion/ingestion-page'

export const Route = createFileRoute('/ingestion')({
  component: IngestionPage,
})
