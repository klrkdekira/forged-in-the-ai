import { Link, createFileRoute } from '@tanstack/react-router'

// FR-31/FR-32's journal (the event log, chronological with expandable
// audit records) lives inside /play as a side panel, same reasoning as
// /sheet: the log it reads only exists for the active WS connection's
// lifetime, no persisted session to show here yet (Phase 5).
export const Route = createFileRoute('/journal')({
  component: () => (
    <div className="flex flex-col items-center justify-center min-h-[40vh] gap-4 text-center">
      <h1 className="text-3xl font-bold tracking-tight text-foreground">Journal</h1>
      <p className="text-muted-foreground">
        The journal is shown alongside chat in{' '}
        <Link to="/play" className="underline underline-offset-2">
          Play
        </Link>{' '}
        for now - it needs a live session, and there's no separate persisted one to show here yet.
      </p>
    </div>
  ),
})
