import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/sheet')({
  component: () => (
    <div className="flex flex-col items-center justify-center min-h-[40vh] gap-4 text-center">
      <h1 className="text-3xl font-bold tracking-tight text-foreground">
        Character Sheet
      </h1>
      <p className="text-muted-foreground">
        Coming soon — stress, harm, load, and XP trackers.
      </p>
    </div>
  ),
})
