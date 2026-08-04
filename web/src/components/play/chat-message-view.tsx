import Markdown from 'react-markdown'

import type { JournalEntry, useSessionSocket } from '@/hooks/use-session-socket'
import { describeRollDecision, summarize } from '@/lib/journal-summarize'

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
