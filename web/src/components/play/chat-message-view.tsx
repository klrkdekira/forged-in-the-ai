import type { useSessionSocket } from '@/hooks/use-session-socket'

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
  if (message.kind === 'narration') {
    return (
      <div className="self-start max-w-[80%] rounded-lg bg-accent/40 px-3 py-2 text-sm whitespace-pre-wrap">
        {message.text}
        {!message.done && <span className="animate-pulse">▍</span>}
      </div>
    )
  }
  if (message.kind === 'tool') {
    return (
      <div className="self-start max-w-[80%] rounded-lg border border-border/60 bg-muted/40 px-3 py-2 text-xs font-mono">
        <div className="font-semibold text-muted-foreground">{message.name}</div>
        <pre className="whitespace-pre-wrap">{JSON.stringify(message.result, null, 2)}</pre>
      </div>
    )
  }
  return (
    <div className="self-start max-w-[80%] rounded-lg bg-destructive/10 text-destructive px-3 py-2 text-sm">
      {message.message}
    </div>
  )
}
