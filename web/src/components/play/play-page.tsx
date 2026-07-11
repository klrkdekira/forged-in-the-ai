import { useEffect, useRef, useState } from 'react'

import { useParams } from '@tanstack/react-router'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useLastCampaignId } from '@/hooks/use-last-campaign-id'
import { useSessionSocket } from '@/hooks/use-session-socket'

import { CharacterSheetPanel } from './character-sheet-panel'
import { ChatMessageView } from './chat-message-view'
import { JournalPanel } from './journal-panel'
import { RollNegotiationDialog } from './roll-negotiation-dialog'
import { TableViewPanel } from './table-view-panel'

export function PlayPage() {
  const { campaignId } = useParams({ from: '/play/$campaignId' })
  useLastCampaignId(campaignId)
  const {
    connected,
    busy,
    messages,
    state,
    pendingRoll,
    sendMessage,
    sendRollDecision,
    sendSheetOperation,
  } = useSessionSocket(campaignId)
  const [draft, setDraft] = useState('')
  const [sidePanel, setSidePanel] = useState<'sheet' | 'table' | 'journal'>('sheet')
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

      <div className="flex flex-1 gap-4 overflow-hidden">
        <div className="flex flex-1 flex-col gap-4 overflow-hidden">
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
        </div>

        {state && (
          <div className="hidden w-72 shrink-0 flex-col gap-2 lg:flex">
            <div className="flex gap-1 rounded-lg border border-border/50 bg-background/50 p-1">
              <Button
                type="button"
                size="sm"
                variant={sidePanel === 'sheet' ? 'default' : 'ghost'}
                className="flex-1"
                onClick={() => setSidePanel('sheet')}
              >
                Sheet
              </Button>
              <Button
                type="button"
                size="sm"
                variant={sidePanel === 'table' ? 'default' : 'ghost'}
                className="flex-1"
                onClick={() => setSidePanel('table')}
              >
                Table
              </Button>
              <Button
                type="button"
                size="sm"
                variant={sidePanel === 'journal' ? 'default' : 'ghost'}
                className="flex-1"
                onClick={() => setSidePanel('journal')}
              >
                Journal
              </Button>
            </div>
            <div className="flex-1 overflow-hidden">
              {sidePanel === 'sheet' && (
                <CharacterSheetPanel character={state.character} onOperate={sendSheetOperation} />
              )}
              {sidePanel === 'table' && (
                <TableViewPanel
                  clocks={state.clocks}
                  crew={state.crew}
                  onOperate={sendSheetOperation}
                />
              )}
              {sidePanel === 'journal' && <JournalPanel entries={state.log.events} />}
            </div>
          </div>
        )}
      </div>

      {pendingRoll && <RollNegotiationDialog proposal={pendingRoll} onDecide={sendRollDecision} />}
    </div>
  )
}
