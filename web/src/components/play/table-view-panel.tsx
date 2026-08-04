import { Button } from '@/components/ui/button'
import type {
  CanonSnapshot,
  ControllerSnapshot,
  ClockSnapshot,
  CrewSnapshot,
  SessionZeroSnapshot,
  SheetOperation,
} from '@/hooks/use-session-socket'

import { ClaimMap } from './claim-map'
import { DistrictMap } from './district-map'
import { TickBoxes } from './tick-boxes'

export function TableViewPanel({
  clocks,
  crew,
  controllers,
  canon,
  sessionZero,
  onOperate,
}: {
  clocks: Record<string, ClockSnapshot>
  crew: CrewSnapshot
  controllers: Record<string, ControllerSnapshot>
  canon: CanonSnapshot | null
  sessionZero: SessionZeroSnapshot | null
  onOperate: (operation: SheetOperation) => void
}) {
  const clockEntries = Object.entries(clocks)

  return (
    <div className="flex h-full flex-col gap-4 overflow-auto rounded-lg border border-border/50 bg-background/50 p-4 text-sm">
      {/* Crew Header */}
      <div className="flex flex-col gap-1.5 rounded-lg border border-border/40 bg-muted/20 p-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold tracking-tight text-foreground">{crew.name}</h2>
          <span className="capitalize text-xs font-semibold px-2 py-0.5 rounded border border-border bg-muted/40">
            {crew.crew_type}
          </span>
        </div>
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <span>Tier {crew.tier}</span>
          <span className="capitalize">{crew.hold} hold</span>
          <span>Vault stash {crew.stash}</span>
        </div>
      </div>

      <div className="rounded-md border border-border/40 bg-background/40 p-2.5">
        <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Controller seats
        </span>
        <ul className="mt-1 flex flex-col gap-1 text-xs text-foreground">
          {Object.values(controllers).map((seat) => (
            <li key={seat.seat_id}>
              <span className="font-medium">{seat.seat_id}</span> ({seat.kind}):{' '}
              {seat.character_ids.join(', ') || 'no characters'}
            </li>
          ))}
        </ul>
      </div>

      {/* Heat Meter */}
      <div className="flex flex-col gap-1.5 rounded-md border border-border/40 p-2.5 bg-background/40">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            Heat
          </span>
          <span className="text-xs font-medium text-muted-foreground">{crew.heat.heat}/9</span>
        </div>
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

      {/* Wanted Level */}
      <div className="flex flex-col gap-1.5 rounded-md border border-border/40 p-2.5 bg-background/40">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            Wanted Level
          </span>
          <span className="text-xs font-medium text-muted-foreground">{crew.wanted_level}/4</span>
        </div>
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

      {/* Rep & Turf */}
      <div className="flex flex-col gap-1.5 rounded-md border border-border/40 p-2.5 bg-background/40">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            Rep ({crew.rep.rep}/{crew.rep.threshold})
          </span>
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <span>Turf: {crew.rep.turf}</span>
            <Button
              type="button"
              variant="outline"
              size="icon-sm"
              className="h-5 w-5 text-xs"
              onClick={() => onOperate({ name: 'adjust_crew_turf', args: { amount: -1 } })}
              disabled={crew.rep.turf <= 0}
            >
              -
            </Button>
            <Button
              type="button"
              variant="outline"
              size="icon-sm"
              className="h-5 w-5 text-xs"
              onClick={() => onOperate({ name: 'adjust_crew_turf', args: { amount: 1 } })}
            >
              +
            </Button>
          </div>
        </div>
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

      {/* Crew Coin / Vault */}
      <div className="flex items-center justify-between rounded-md border border-border/40 p-2.5 bg-background/40">
        <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          Crew Vault Coin
        </span>
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
          <span className="w-6 text-center font-bold text-foreground">{crew.coin}</span>
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

      <div className="flex items-center justify-between rounded-md border border-border/40 p-2.5 bg-background/40">
        <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          Crew XP
        </span>
        <span className="text-xs font-medium text-muted-foreground">
          {crew.xp.marked}/{crew.xp.segments}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <div className="rounded-md border border-border/40 bg-background/40 p-2.5">
          <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Upgrades
          </span>
          {crew.upgrade_ids.length > 0 ? (
            <ul className="mt-1 flex flex-col gap-1 text-xs text-foreground">
              {crew.upgrade_ids.map((upgrade) => (
                <li key={upgrade}>{upgrade}</li>
              ))}
            </ul>
          ) : (
            <p className="mt-1 text-xs text-muted-foreground">None</p>
          )}
        </div>
        <div className="rounded-md border border-border/40 bg-background/40 p-2.5">
          <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Special abilities
          </span>
          {crew.special_ability_ids.length > 0 ? (
            <ul className="mt-1 flex flex-col gap-1 text-xs text-foreground">
              {crew.special_ability_ids.map((ability) => (
                <li key={ability}>{ability}</li>
              ))}
            </ul>
          ) : (
            <p className="mt-1 text-xs text-muted-foreground">None</p>
          )}
        </div>
      </div>

      <div className="rounded-md border border-border/40 bg-background/40 p-2.5">
        <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Cohorts
        </span>
        {crew.cohorts.length > 0 ? (
          <ul className="mt-1 flex flex-col gap-1 text-xs text-foreground">
            {crew.cohorts.map((cohort, index) => (
              <li key={`${cohort.types.join('-')}-${index}`}>
                {cohort.is_expert ? 'Expert' : 'Gang'}: {cohort.types.join(', ') || 'untyped'} · harm{' '}
                {cohort.harm.level}
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-1 text-xs text-muted-foreground">None</p>
        )}
      </div>

      {/* Active Clocks */}
      <div className="flex flex-col gap-2 rounded-md border border-border/40 p-2.5 bg-background/40">
        <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          Progress Clocks ({clockEntries.length})
        </span>
        {clockEntries.length > 0 ? (
          <ul className="flex flex-col gap-2">
            {clockEntries.map(([clockId, clock]) => (
              <li key={clockId} className="flex flex-col gap-1 rounded bg-muted/20 p-2 border border-border/30">
                <div className="flex items-center justify-between text-xs font-medium">
                  <span>{clock.name}</span>
                  <span className="text-muted-foreground">{clock.filled}/{clock.segments}</span>
                </div>
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
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-muted-foreground">No active progress clocks.</p>
        )}
      </div>

      {/* Claims */}
      <div className="flex flex-col gap-2 rounded-md border border-border/40 p-2.5 bg-background/40">
        <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          Claims & Turf
        </span>
        {crew.claims.length > 0 ? (
          <>
            <ClaimMap claims={crew.claims} />
            <ul className="flex flex-col gap-1 text-xs">
              {crew.claims.map((claim) => (
                <li key={claim.id} className="flex items-center justify-between">
                  <span className={claim.controlled ? 'font-medium text-foreground' : 'text-muted-foreground'}>
                    {claim.name} {claim.is_turf && '(Turf)'}
                  </span>
                  <span className={`text-[0.65rem] px-2 py-0.5 rounded font-medium ${claim.controlled ? 'bg-primary text-primary-foreground' : 'border border-border bg-muted/30 text-muted-foreground'}`}>
                    {claim.controlled ? 'Controlled' : 'Contested'}
                  </span>
                </li>
              ))}
            </ul>
          </>
        ) : (
          <p className="text-xs text-muted-foreground">No claims established yet.</p>
        )}
      </div>

      {/* Setting */}
      <div className="flex flex-col gap-2 rounded-md border border-border/40 p-2.5 bg-background/40">
        <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          Setting & Canon
        </span>
        {canon ? (
          <div className="flex flex-col gap-1.5 text-xs">
            <span className="font-bold text-foreground">{canon.setting_name}</span>
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

      {/* Safety Boundaries */}
      {sessionZero && (
        <div className="flex flex-col gap-2 rounded-md border border-border/40 p-2.5 bg-background/40 text-xs">
          <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            Safety Boundaries
          </span>
          {sessionZero.lines.length > 0 && (
            <div>
              <span className="font-medium text-destructive">Lines: </span>
              <span className="text-muted-foreground">{sessionZero.lines.join(', ')}</span>
            </div>
          )}
          {sessionZero.veils.length > 0 && (
            <div>
              <span className="font-medium text-amber-500">Veils: </span>
              <span className="text-muted-foreground">{sessionZero.veils.join(', ')}</span>
            </div>
          )}
          {sessionZero.tone && (
            <div>
              <span className="font-medium text-foreground">Tone: </span>
              <span className="text-muted-foreground">{sessionZero.tone}</span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
