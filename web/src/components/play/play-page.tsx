import { useEffect, useRef, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useSessionSocket } from '@/hooks/use-session-socket'

import { ChatMessageView } from './chat-message-view'
import { RollNegotiationDialog } from './roll-negotiation-dialog'

export function PlayPage() {
  const { connected, busy, messages, state, pendingRoll, sendMessage, sendRollDecision } =
    useSessionSocket()
  const [draft, setDraft] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    const text = draft.trim()
    if (!text || busy) return
    sendMessage(text)
    setDraft('')
  }

  return (
    <div className="flex flex-col gap-4 h-[calc(100vh-8rem)]">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            {state?.character.name ?? 'Play'}
          </h1>
          <p className="text-sm text-muted-foreground">
            {state ? `${state.character.playbook} · ${state.crew.name}` : 'Connecting…'}
          </p>
        </div>
        <span
          className={`text-xs rounded-full px-2 py-1 ${
            connected ? 'bg-primary/10 text-primary' : 'bg-destructive/10 text-destructive'
          }`}
        >
          {connected ? 'Connected' : 'Disconnected'}
        </span>
      </div>

      <div className="flex-1 overflow-auto rounded-lg border border-border/50 bg-background/50 p-4 flex flex-col gap-3">
        {messages.map((message, index) => (
          <ChatMessageView key={index} message={message} />
        ))}
        <div ref={bottomRef} />
      </div>

      <form onSubmit={handleSubmit} className="flex gap-2">
        <Input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="What do you do?"
          disabled={!connected || busy}
        />
        <Button type="submit" disabled={!connected || busy || !draft.trim()}>
          Send
        </Button>
      </form>

      {pendingRoll && <RollNegotiationDialog proposal={pendingRoll} onDecide={sendRollDecision} />}
    </div>
  )
}
