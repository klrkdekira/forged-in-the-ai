import { Button } from '@/components/ui/button'
import type {
  CanonSnapshot,
  ClockSnapshot,
  CrewSnapshot,
  SheetOperation,
} from '@/hooks/use-session-socket'

import { ClaimMap } from './claim-map'
import { DistrictMap } from './district-map'
import { TickBoxes } from './tick-boxes'

// FR-28/FR-29: the crew's heat/wanted level/rep/coin are clickable, same
// engine-operation shape as the character sheet panel (previously
// read-only - Table view v1 only wired up clocks and claims); active
// clocks (clickable, same tick-box control as the sheet panel's
// stress/XP), the crew's claims and the district map (each as a
// generated Konva diagram, ADR-0007, alongside the precise text list -
// the map is a fiction aid, not the only source of the detail), and
// (once session zero has generated one, FR-36) the setting. Neither map
// has stored positions/adjacency to lay out from yet, so both use a
// computed ring layout (lib/map-layout.ts) rather than an authored one.
export function TableViewPanel({
  clocks,
  crew,
  canon,
  onOperate,
}: {
  clocks: Record<string, ClockSnapshot>
  crew: CrewSnapshot
  canon: CanonSnapshot | null
  onOperate: (operation: SheetOperation) => void
}) {
  const clockEntries = Object.entries(clocks)

  return (
    <div className="flex h-full flex-col gap-4 overflow-auto rounded-lg border border-border/50 bg-background/50 p-4 text-sm">
      <div>
        <h2 className="text-lg font-semibold text-foreground">{crew.name}</h2>
        <p className="text-xs text-muted-foreground">{crew.crew_type}</p>
      </div>

      <div className="flex flex-col gap-1">
        <span className="text-xs font-semibold text-muted-foreground">Heat</span>
        <TickBoxes
          segments={9}
          marked={crew.heat.heat}
          onSetMarked={(marked) =>
            onOperate({
              name: 'add_crew_heat',
              args: { amount: marked - crew.heat.heat },
            })
          }
        />
      </div>

      <div className="flex flex-col gap-1">
        <span className="text-xs font-semibold text-muted-foreground">Wanted level</span>
        <TickBoxes
          segments={4}
          marked={crew.wanted_level}
          onSetMarked={(marked) =>
            onOperate({
              name: 'adjust_wanted_level',
              args: { amount: marked - crew.wanted_level },
            })
          }
        />
      </div>

      <div className="flex flex-col gap-1">
        <span className="text-xs font-semibold text-muted-foreground">
          Rep (turf: {crew.rep.turf})
        </span>
        <TickBoxes
          segments={crew.rep.threshold}
          marked={crew.rep.rep}
          onSetMarked={(marked) =>
            onOperate({
              name: 'adjust_crew_rep',
              args: { amount: marked - crew.rep.rep },
            })
          }
        />
      </div>

      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-muted-foreground">Coin</span>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="icon-sm"
            onClick={() => onOperate({ name: 'adjust_crew_coin', args: { amount: -1 } })}
            disabled={crew.coin <= 0}
          >
            -
          </Button>
          <span className="w-6 text-center">{crew.coin}</span>
          <Button
            type="button"
            variant="outline"
            size="icon-sm"
            onClick={() => onOperate({ name: 'adjust_crew_coin', args: { amount: 1 } })}
          >
            +
          </Button>
        </div>
      </div>

      <div className="flex flex-col gap-2">
        <span className="text-xs font-semibold text-muted-foreground">Setting</span>
        {canon ? (
          <div className="flex flex-col gap-1 text-xs">
            <span className="font-medium text-foreground">{canon.setting_name}</span>
            {canon.tone && <span className="italic text-muted-foreground">{canon.tone}</span>}
            <span className="text-muted-foreground">
              Factions: {canon.factions.length > 0 ? canon.factions.join(', ') : 'none yet'}
            </span>
            <DistrictMap locations={canon.locations} />
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">
            Not generated yet - the GM sets this up during session zero.
          </p>
        )}
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
        <ClaimMap claims={crew.claims} />
        {crew.claims.length > 0 && (
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
        )}
      </div>
    </div>
  )
}
