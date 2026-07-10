import type { ClockSnapshot, CrewSnapshot, SheetOperation } from '@/hooks/use-session-socket'

import { TickBoxes } from './tick-boxes'

// FR-29: table view v1 - active clocks (clickable, same tick-box control as
// the sheet panel's stress/XP) and the crew's claims. The claim map itself
// (generated district/score imagery) is v2's job (TODO.md); claims here are
// a plain read-only list, since nothing currently mutates them at runtime.
export function TableViewPanel({
  clocks,
  crew,
  onOperate,
}: {
  clocks: Record<string, ClockSnapshot>
  crew: CrewSnapshot
  onOperate: (operation: SheetOperation) => void
}) {
  const clockEntries = Object.entries(clocks)

  return (
    <div className="flex h-full flex-col gap-4 overflow-auto rounded-lg border border-border/50 bg-background/50 p-4 text-sm">
      <div>
        <h2 className="text-lg font-semibold text-foreground">{crew.name}</h2>
        <p className="text-xs text-muted-foreground">{crew.crew_type}</p>
      </div>

      <div className="flex flex-col gap-3">
        <span className="text-xs font-semibold text-muted-foreground">Active clocks</span>
        {clockEntries.length > 0 ? (
          clockEntries.map(([clockId, clock]) => (
            <div key={clockId} className="flex flex-col gap-1">
              <span className="text-xs">
                {clock.name} <span className="text-muted-foreground capitalize">({clock.kind})</span>
              </span>
              <TickBoxes
                segments={clock.segments}
                marked={clock.filled}
                onSetMarked={(marked) =>
                  onOperate({
                    name: 'tick_clock',
                    args: { clock_id: clockId, amount: marked - clock.filled },
                  })
                }
              />
            </div>
          ))
        ) : (
          <p className="text-xs text-muted-foreground">No clocks yet.</p>
        )}
      </div>

      <div className="flex flex-col gap-2">
        <span className="text-xs font-semibold text-muted-foreground">Claims</span>
        {crew.claims.length > 0 ? (
          <ul className="flex flex-col gap-1">
            {crew.claims.map((claim) => (
              <li key={claim.id} className="flex items-center justify-between text-xs">
                <span>{claim.name}</span>
                <span className="text-muted-foreground">
                  {claim.controlled ? 'Controlled' : 'Contested'}
                  {claim.is_turf ? ' · Turf' : ''}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-muted-foreground">No claims yet.</p>
        )}
      </div>
    </div>
  )
}
