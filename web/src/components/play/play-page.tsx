import { useEffect, useRef, useState } from 'react'

import { useNavigate, useParams } from '@tanstack/react-router'
import { Dices, Download, FolderCog, Trash2 } from 'lucide-react'

import { apiClient } from '@/api/client'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { useLastCampaignId } from '@/hooks/use-last-campaign-id'
import type { ControllerSnapshot } from '@/hooks/use-session-socket'
import { useSessionSocket } from '@/hooks/use-session-socket'

import { AnimatedDiceRoller } from './animated-dice-roller'
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
    reconnecting,
    reconnectAttempt,
    busy,
    messages,
    state,
    pendingRoll,
    sendMessage,
    sendRollDecision,
    sendSheetOperation,
    sendUndo,
    sendXCard,
    clearBusy,
    reconnect,
  } = useSessionSocket(campaignId)
  const navigate = useNavigate()
  const [draft, setDraft] = useState('')
  const [sidePanel, setSidePanel] = useState<'sheet' | 'table' | 'journal' | 'relationships'>(
    'sheet',
  )
  const [selectedCharacterId, setSelectedCharacterId] = useState<string | null>(null)
  const [xCardOpen, setXCardOpen] = useState(false)
  const [diceRollerOpen, setDiceRollerOpen] = useState(false)
  const [manageCampaignOpen, setManageCampaignOpen] = useState(false)
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  async function handleDeleteCampaign() {
    setDeleting(true)
    try {
      await apiClient.DELETE('/api/campaigns/{campaign_id}', {
        params: { path: { campaign_id: campaignId } },
      })
      navigate({ to: '/' })
    } catch {
      setDeleting(false)
    }
  }

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
      <div className="flex items-center justify-between border-b border-border/40 pb-3">
        <div className="flex items-center gap-3">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
              {state?.character.name ?? 'Play'}
              {Boolean(state?.phase) && (
                <span className="text-xs font-semibold uppercase tracking-wider px-2 py-0.5 rounded bg-primary/10 text-primary border border-primary/20">
                  {String(state?.phase).replace('_', ' ')}
                </span>
              )}
            </h1>
            <p className="text-xs text-muted-foreground">
              {state
                ? `${state.character.playbook} · ${state.crew.name}`
                : reconnecting
                ? `Reconnecting to server (attempt ${reconnectAttempt})…`
                : 'Connecting…'}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {state?.character && (
            <div className="hidden sm:flex items-center gap-2 text-xs text-muted-foreground mr-2">
              <span className="px-2 py-1 rounded bg-muted/40 font-medium">
                Stress: <strong className="text-foreground">{state.character.stress.marked}/9</strong>
              </span>
              <span className="px-2 py-1 rounded bg-muted/40 font-medium">
                Coin: <strong className="text-foreground">{state.character.coin}</strong>
              </span>
            </div>
          )}
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="border-muted text-muted-foreground hover:text-foreground flex items-center gap-1.5"
            onClick={() => setManageCampaignOpen(true)}
          >
            <FolderCog className="size-4" />
            Campaign
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="border-primary/40 text-primary hover:bg-primary/10 flex items-center gap-1.5"
            onClick={() => setDiceRollerOpen(true)}
          >
            <Dices className="size-4" />
            Roll Dice
          </Button>
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
            className={`text-xs rounded-full px-2.5 py-1 font-semibold flex items-center gap-1.5 ${
              connected
                ? 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/20'
                : reconnecting
                ? 'bg-amber-500/10 text-amber-500 border border-amber-500/20 animate-pulse'
                : 'bg-destructive/10 text-destructive border border-destructive/20'
            }`}
          >
            <span
              className={`size-1.5 rounded-full ${
                connected
                  ? 'bg-emerald-500'
                  : reconnecting
                  ? 'bg-amber-500'
                  : 'bg-destructive'
              }`}
            />
            {connected
              ? 'Live Session'
              : reconnecting
              ? `Reconnecting (${reconnectAttempt})`
              : 'Disconnected'}
          </span>
          {!connected && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-7 text-xs border-amber-500/30 text-amber-500 hover:bg-amber-500/10"
              onClick={reconnect}
            >
              Reconnect
            </Button>
          )}
        </div>
      </div>

      <div className="flex flex-1 gap-4 overflow-hidden">
        <div className="flex flex-1 flex-col gap-4 overflow-hidden">
          <div className="flex-1 overflow-auto rounded-lg border border-border/50 bg-background/50 p-4 flex flex-col gap-3">
            {messages.map((message, index) => (
              <ChatMessageView key={index} message={message} />
            ))}
            {showTyping && <TypingIndicator onCancel={clearBusy} />}
            <div ref={bottomRef} />
          </div>

          <form onSubmit={handleSubmit} className="flex gap-2">
            <select
              disabled={!connected || busy}
              onChange={(e) => {
                if (!e.target.value) return
                const act = e.target.value
                setDraft(`I attempt to use ${act.toUpperCase()} to `)
                e.target.value = ''
              }}
              className="h-9 rounded-md border border-input bg-background px-2 text-xs font-medium text-muted-foreground hover:bg-muted/40 cursor-pointer"
            >
              <option value="">+ Roll Action...</option>
              <option value="attune">Attune</option>
              <option value="command">Command</option>
              <option value="consort">Consort</option>
              <option value="finesse">Finesse</option>
              <option value="hunt">Hunt</option>
              <option value="prowl">Prowl</option>
              <option value="skirmish">Skirmish</option>
              <option value="study">Study</option>
              <option value="survey">Survey</option>
              <option value="sway">Sway</option>
              <option value="tinker">Tinker</option>
              <option value="wreck">Wreck</option>
            </select>
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

      <AnimatedDiceRoller open={diceRollerOpen} onOpenChange={setDiceRollerOpen} />

      {/* Manage Campaign Dialog */}
      <Dialog open={manageCampaignOpen} onOpenChange={setManageCampaignOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <FolderCog className="size-5 text-primary" /> Manage Campaign
            </DialogTitle>
            <DialogDescription>
              Export session backup or permanently delete this campaign.
            </DialogDescription>
          </DialogHeader>

          <div className="flex flex-col gap-3 my-4">
            <a
              href={`/api/campaigns/${campaignId}/export`}
              download
              className="flex items-center justify-between p-3 rounded-lg border border-border/60 bg-muted/20 hover:bg-muted/50 transition-colors text-sm font-medium"
            >
              <div className="flex items-center gap-2">
                <Download className="size-4 text-primary" />
                <span>Export Campaign Bundle</span>
              </div>
              <span className="text-xs text-muted-foreground font-normal">JSON format</span>
            </a>

            <div className="flex items-center justify-between p-3 rounded-lg border border-destructive/30 bg-destructive/5 hover:bg-destructive/10 transition-colors text-sm">
              <div className="flex items-center gap-2 text-destructive font-medium">
                <Trash2 className="size-4" />
                <span>Delete Campaign</span>
              </div>
              <Button
                type="button"
                variant="destructive"
                size="sm"
                onClick={() => {
                  setManageCampaignOpen(false)
                  setConfirmDeleteOpen(true)
                }}
              >
                Delete
              </Button>
            </div>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setManageCampaignOpen(false)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Campaign Confirmation */}
      <Dialog open={confirmDeleteOpen} onOpenChange={setConfirmDeleteOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-destructive flex items-center gap-2">
              <Trash2 className="size-5" /> Confirm Permanent Deletion
            </DialogTitle>
            <DialogDescription>
              Are you sure you want to delete this campaign? All SQLite database files, roll logs, and character progression will be permanently erased.
            </DialogDescription>
          </DialogHeader>

          <DialogFooter className="mt-4 flex justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => setConfirmDeleteOpen(false)}
              disabled={deleting}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="destructive"
              onClick={handleDeleteCampaign}
              disabled={deleting}
            >
              {deleting ? 'Deleting…' : 'Delete Campaign'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

function TypingIndicator({ onCancel }: { onCancel?: () => void }) {
  return (
    <div className="self-start flex items-center gap-3 rounded-lg bg-accent/40 px-3 py-1.5 text-xs text-muted-foreground border border-border/30">
      <div className="flex items-center gap-1">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="size-1.5 animate-bounce rounded-full bg-muted-foreground"
            style={{ animationDelay: `${i * 0.15}s` }}
          />
        ))}
      </div>
      <span>GM thinking…</span>
      {onCancel && (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-5 px-1.5 text-[0.65rem] text-muted-foreground hover:text-foreground hover:bg-background/50"
          onClick={onCancel}
        >
          Unlock controls
        </Button>
      )}
    </div>
  )
}
