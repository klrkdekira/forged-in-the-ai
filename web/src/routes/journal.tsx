import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/journal')({
  component: () => (
    <div className="flex flex-col items-center justify-center min-h-[40vh] gap-4 text-center">
      <h1 className="text-3xl font-bold tracking-tight text-foreground">
        Journal
      </h1>
      <p className="text-muted-foreground">
        Coming soon — chronological turn log with expandable roll audit records.
      </p>
    </div>
  ),
})
