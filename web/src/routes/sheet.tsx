import { Link, createFileRoute } from '@tanstack/react-router'

// FR-28's interactive sheet (stress/harm/XP/load/coin) lives inside /play
// as a side panel, not this route: the GameState it reflects only exists
// for the lifetime of the one active WS connection (no persisted,
// addressable session yet - that's Phase 5), so a separate page here would
// either open its own blank session or need state lifted well above where
// it lives today. Revisit once campaign save/load lands.
export const Route = createFileRoute('/sheet')({
  component: () => (
    <div className="flex flex-col items-center justify-center min-h-[40vh] gap-4 text-center">
      <h1 className="text-3xl font-bold tracking-tight text-foreground">Character Sheet</h1>
      <p className="text-muted-foreground">
        The interactive sheet is shown alongside chat in{' '}
        <Link to="/play" className="underline underline-offset-2">
          Play
        </Link>{' '}
        for now - it needs a live session, and there's no separate persisted one to show here yet.
      </p>
    </div>
  ),
})
