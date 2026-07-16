import Markdown from 'react-markdown'

import type { JournalEntry, useSessionSocket } from '@/hooks/use-session-socket'
import { summarize } from '@/lib/journal-summarize'

// FR-31/FR-32: one-line, human-readable status per tool call - reusing the
// Journal view's own summarize() over the entity-tagged event(s) the tool
// logged, rather than dumping the tool's raw result JSON into the chat.
// Falls back to the tool's error message (or just its name) when it didn't
// log anything, e.g. an unknown tool or bad arguments.
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
      <div className="self-end max-w-[80%] rounded-lg bg-primary text-primary-foreground px-3 py-2 text-sm">
        {message.text}
      </div>
    )
  }
  if (message.kind === 'companion') {
    return (
      <div className="self-start max-w-[80%] rounded-lg bg-secondary/60 px-3 py-2 text-sm">
        <div className="text-xs font-semibold text-muted-foreground">{message.name}</div>
        {message.text}
      </div>
    )
  }
  if (message.kind === 'narration') {
    return (
      <div className="self-start max-w-[80%] rounded-lg bg-accent/40 px-3 py-2 text-sm [&_p]:mb-2 [&_p:last-child]:mb-0 [&_ul]:list-disc [&_ol]:list-decimal [&_ul]:pl-5 [&_ol]:pl-5 [&_strong]:font-semibold [&_em]:italic">
        <Markdown>{message.text}</Markdown>
        {!message.done && <span className="animate-pulse">▍</span>}
      </div>
    )
  }
  if (message.kind === 'tool') {
    const statuses = toolCallStatuses(message.name, message.result, message.events)
    return (
      <div className="self-start flex max-w-[80%] flex-col gap-1 rounded-lg border border-border/60 bg-muted/40 px-3 py-1.5 text-xs text-muted-foreground">
        {statuses.map((status, index) => (
          <span key={index} className="flex items-center gap-1.5">
            <span aria-hidden className="text-[0.6rem]">
              ●
            </span>
            {status}
          </span>
        ))}
      </div>
    )
  }
  return (
    <div className="self-start max-w-[80%] rounded-lg bg-destructive/10 text-destructive px-3 py-2 text-sm">
      {message.message}
    </div>
  )
}
