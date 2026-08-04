import { useEffect, useRef, useState } from 'react'

import { useParams } from '@tanstack/react-router'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useLastCampaignId } from '@/hooks/use-last-campaign-id'
import type { ControllerSnapshot } from '@/hooks/use-session-socket'
import { useSessionSocket } from '@/hooks/use-session-socket'

import { CharacterSheetPanel } from './character-sheet-panel'
import { ChatMessageView } from './chat-message-view'
import { JournalPanel } from './journal-panel'
import { RelationshipMap } from './relationship-map'
import { RollNegotiationDialog } from './roll-negotiation-dialog'
import { TableViewPanel } from './table-view-panel'
import { XCardDialog } from './x-card-dialog'

// FR-35: a character with no seat naming it is human-controlled by
// default (engine.controller.is_ai_controlled) - looked up, never stored
// on the character itself.
function isAiControlled(controllers: Record<string, ControllerSnapshot>, characterId: string) {
  return Object.values(controllers).some(
    (controller) => controller.kind === 'ai' && controller.character_ids.includes(characterId),
  )
}

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
    sendUndo,
    sendXCard,
  } = useSessionSocket(campaignId)
  const [draft, setDraft] = useState('')
  const [sidePanel, setSidePanel] = useState<'sheet' | 'table' | 'journal' | 'relationships'>(
    'sheet',
  )
  const [selectedCharacterId, setSelectedCharacterId] = useState<string | null>(null)
  const [xCardOpen, setXCardOpen] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  // FR-25/FR-35: the sheet panel used to always show state.character (the
  // primary PC computed field) - a companion's own sheet was never
  // reachable at all. Falls back to the first known PC if nothing's
  // selected yet, or the selection no longer exists (e.g. after a reconnect).
  const characterIds = state ? Object.keys(state.characters) : []
  const activeCharacterId =
    selectedCharacterId && state?.characters[selectedCharacterId]
      ? selectedCharacterId
      : (characterIds[0] ?? null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // The GM's turn covers an LLM call plus however many tool-calling rounds
  // it takes (each shown as its own status line) before narration starts
  // streaming - `busy` alone stays true across all of that, so this only
  // shows once there's nothing else already telling the player something
  // is happening: not mid-stream (the streaming text/cursor is its own
  // feedback) and not while the roll negotiation dialog has the floor.
  const lastMessage = messages.at(-1)
  const isStreamingNarration = lastMessage?.kind === 'narration' && !lastMessage.done
  const showTyping = busy && !pendingRoll && !isStreamingNarration

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
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="border-destructive/40 text-destructive hover:bg-destructive/10"
            onClick={() => setXCardOpen(true)}
            disabled={!connected}
          >
            X-Card
          </Button>
          <span
            className={`text-xs rounded-full px-2 py-1 ${
              connected ? 'bg-primary/10 text-primary' : 'bg-destructive/10 text-destructive'
            }`}
          >
            {connected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
      </div>

      <div className="flex flex-1 gap-4 overflow-hidden">
        <div className="flex flex-1 flex-col gap-4 overflow-hidden">
          <div className="flex-1 overflow-auto rounded-lg border border-border/50 bg-background/50 p-4 flex flex-col gap-3">
            {messages.map((message, index) => (
              <ChatMessageView key={index} message={message} />
            ))}
            {showTyping && <TypingIndicator />}
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
              <Button
                type="button"
                size="sm"
                variant={sidePanel === 'relationships' ? 'default' : 'ghost'}
                className="flex-1"
                onClick={() => setSidePanel('relationships')}
              >
                Ties
              </Button>
            </div>
            <div className="flex-1 overflow-hidden">
              {sidePanel === 'sheet' && activeCharacterId && (
                <div className="flex h-full flex-col gap-2">
                  {characterIds.length > 1 && (
                    <div className="flex flex-wrap gap-1">
                      {characterIds.map((characterId) => (
                        <Button
                          key={characterId}
                          type="button"
                          size="sm"
                          variant={characterId === activeCharacterId ? 'default' : 'ghost'}
                          onClick={() => setSelectedCharacterId(characterId)}
                        >
                          {state.characters[characterId].name}
                          {isAiControlled(state.controllers, characterId) && (
                            <span className="text-[0.65rem] opacity-70">AI</span>
                          )}
                        </Button>
                      ))}
                    </div>
                  )}
                  <CharacterSheetPanel
                    characterId={activeCharacterId}
                    character={state.characters[activeCharacterId]}
                    onOperate={sendSheetOperation}
                  />
                </div>
              )}
              {sidePanel === 'table' && (
                <TableViewPanel
                  clocks={state.clocks}
                  crew={state.crew}
                  canon={state.canon}
                  sessionZero={state.session_zero}
                  onOperate={sendSheetOperation}
                />
              )}
              {sidePanel === 'journal' && (
                <JournalPanel
                  entries={state.log.events}
                  campaignId={campaignId}
                  onUndo={sendUndo}
                />
              )}
              {sidePanel === 'relationships' && (
                <RelationshipMap
                  character={state.character}
                  crew={state.crew}
                  npcs={state.npcs}
                  factionStatuses={state.faction_statuses}
                  relationships={state.relationships}
                  journalEntries={state.log.events}
                />
              )}
            </div>
          </div>
        )}
      </div>

      {pendingRoll && state && (
        <RollNegotiationDialog
          proposal={pendingRoll}
          characters={state.characters}
          onDecide={sendRollDecision}
        />
      )}

      <XCardDialog
        open={xCardOpen}
        onOpenChange={setXCardOpen}
        onInvoke={(note, text) => sendXCard(note, undefined, text)}
      />
    </div>
  )
}

function TypingIndicator() {
  return (
    <div className="self-start flex items-center gap-1 rounded-lg bg-accent/40 px-3 py-2">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="size-1.5 animate-bounce rounded-full bg-muted-foreground"
          style={{ animationDelay: `${i * 0.15}s` }}
        />
      ))}
    </div>
  )
}
