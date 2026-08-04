import { useState } from 'react'
import Markdown from 'react-markdown'
import { Dices, Trophy, CheckCircle2, AlertTriangle, ShieldAlert, RotateCcw } from 'lucide-react'

import type { JournalEntry, useSessionSocket } from '@/hooks/use-session-socket'
import { describeRollDecision, summarize } from '@/lib/journal-summarize'
import { AnimatedDiceRoller, type DiceRollResult } from './animated-dice-roller'
import { Button } from '@/components/ui/button'

function toolCallStatuses(name: string, result: unknown, events: JournalEntry[]): string[] {
  if (events.length > 0) return events.map(summarize)
  const error = (result as { error?: unknown } | null)?.error
  return [typeof error === 'string' ? error : `Called ${name}`]
}

export function ChatMessageView({
  message,
}: {
  message: ReturnType<typeof useSessionSocket>['messages'][number]
}) {
  const [replayResult, setReplayResult] = useState<DiceRollResult | null>(null)

  if (message.kind === 'player') {
    return (
      <div className="self-end max-w-[80%] rounded-xl bg-gradient-to-r from-primary to-primary/90 text-primary-foreground px-4 py-2.5 text-sm shadow-sm border border-primary/20">
        {message.text}
      </div>
    )
  }
  if (message.kind === 'companion') {
    return (
      <div className="self-start max-w-[80%] rounded-xl bg-secondary/80 border border-secondary px-4 py-2.5 text-sm shadow-sm">
        <div className="flex items-center gap-1.5 mb-1">
          <span className="text-[0.65rem] font-bold px-1.5 py-0.5 rounded bg-muted text-muted-foreground border border-border">
            {message.name}
          </span>
        </div>
        <div className="text-foreground">{message.text}</div>
      </div>
    )
  }
  if (message.kind === 'narration') {
    return (
      <div className="self-start max-w-[85%] rounded-xl bg-card border border-border/60 p-4 text-sm shadow-md text-card-foreground leading-relaxed [&_p]:mb-2 [&_p:last-child]:mb-0 [&_ul]:list-disc [&_ol]:list-decimal [&_ul]:pl-5 [&_ol]:pl-5 [&_strong]:font-semibold [&_strong]:text-primary [&_em]:italic">
        <div className="flex items-center gap-2 mb-2 pb-1 border-b border-border/30">
          <span className="text-[0.65rem] font-bold tracking-wider uppercase text-amber-500 border border-amber-500/30 bg-amber-500/10 px-1.5 py-0.5 rounded">
            GM Referee
          </span>
        </div>
        <Markdown>{message.text}</Markdown>
        {!message.done && <span className="inline-block animate-pulse font-bold text-amber-500"> ▍</span>}
      </div>
    )
  }
  if (message.kind === 'tool') {
    const rollEvent = message.events.find(
      (e) =>
        e.event_type === 'action_roll' ||
        e.event_type === 'fortune_roll' ||
        e.event_type === 'resistance_roll' ||
        e.event_type === 'engagement_roll',
    )

    if (rollEvent && Array.isArray(rollEvent.payload.dice)) {
      const p = rollEvent.payload
      const dice = p.dice as number[]
      const highest = Number(p.highest ?? Math.max(...dice))
      const band = String(p.band ?? 'partial')
      const actionName = String(p.action || rollEvent.event_type.replace('_', ' '))

      const isCritical = band === 'critical'
      const isSuccess = band === 'success'
      const isPartial = band === 'partial'

      const rollData: DiceRollResult = {
        dice,
        highest,
        band,
        action: actionName,
        position: p.position ? String(p.position) : undefined,
        effect: p.effect ? String(p.effect) : undefined,
      }

      return (
        <div className="self-start flex max-w-[85%] flex-col gap-2 rounded-xl border border-border/50 bg-card/60 p-3 text-xs shadow-md">
          <div className="flex items-center justify-between border-b border-border/30 pb-2">
            <div className="flex items-center gap-1.5 font-bold capitalize text-foreground text-sm">
              <Dices className="size-4 text-primary" />
              {actionName}
              {Boolean(p.position) && (
                <span className="text-[0.65rem] font-semibold uppercase px-1.5 py-0.5 rounded bg-muted text-muted-foreground border border-border">
                  {String(p.position)} / {String(p.effect)}
                </span>
              )}
            </div>
            <span
              className={`text-[0.65rem] font-bold uppercase tracking-wider px-2 py-0.5 rounded flex items-center gap-1 ${
                isCritical
                  ? 'bg-amber-500/20 text-amber-500 border border-amber-500/30'
                  : isSuccess
                  ? 'bg-emerald-500/20 text-emerald-500 border border-emerald-500/30'
                  : isPartial
                  ? 'bg-amber-500/20 text-amber-500 border border-amber-500/30'
                  : 'bg-rose-500/20 text-rose-500 border border-rose-500/30'
              }`}
            >
              {isCritical && <Trophy className="size-3" />}
              {isSuccess && <CheckCircle2 className="size-3" />}
              {isPartial && <AlertTriangle className="size-3" />}
              {!isCritical && !isSuccess && !isPartial && <ShieldAlert className="size-3" />}
              {band}
            </span>
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              {dice.map((d, i) => {
                const isHigh = d === highest
                return (
                  <div
                    key={i}
                    className={`size-8 rounded-lg flex items-center justify-center font-bold text-sm shadow-xs border ${
                      isHigh
                        ? 'bg-primary text-primary-foreground border-primary ring-2 ring-primary/30 font-extrabold scale-105'
                        : 'bg-muted/40 border-border/60 text-muted-foreground'
                    }`}
                  >
                    {d}
                  </div>
                )
              })}
            </div>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-7 text-[0.7rem] px-2 gap-1 text-muted-foreground hover:text-foreground"
              onClick={() => setReplayResult(rollData)}
            >
              <RotateCcw className="size-3" /> Replay 3D
            </Button>
          </div>

          {replayResult && (
            <AnimatedDiceRoller
              open={Boolean(replayResult)}
              onOpenChange={(open) => !open && setReplayResult(null)}
              result={replayResult}
            />
          )}
        </div>
      )
    }

    const statuses = toolCallStatuses(message.name, message.result, message.events)
    return (
      <div className="self-start flex max-w-[80%] flex-col gap-1.5 rounded-lg border border-border/40 bg-muted/30 px-3 py-2 text-xs text-muted-foreground shadow-xs">
        {statuses.map((status, index) => (
          <span key={index} className="flex items-center gap-2 font-medium">
            <span aria-hidden className="inline-block size-1.5 rounded-full bg-amber-500" />
            {status}
          </span>
        ))}
      </div>
    )
  }
  if (message.kind === 'companion-decision') {
    return (
      <div className="self-start flex max-w-[80%] items-center gap-2 rounded-lg border border-border/40 bg-muted/30 px-3 py-2 text-xs text-muted-foreground shadow-xs">
        <span aria-hidden className="inline-block size-1.5 rounded-full bg-blue-500" />
        <span className="font-semibold text-foreground">{message.name}:</span> {describeRollDecision(message.decision)}
      </div>
    )
  }
  return (
    <div className="self-start max-w-[80%] rounded-xl bg-destructive/10 border border-destructive/30 text-destructive px-4 py-2.5 text-sm shadow-sm font-medium">
      {message.message}
    </div>
  )
}
