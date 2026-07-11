import { useCallback, useEffect, useRef, useState } from 'react'

export type ChatMessage =
  | { kind: 'player'; text: string }
  | { kind: 'narration'; text: string; done: boolean }
  | { kind: 'tool'; name: string; result: unknown }
  | { kind: 'error'; message: string }

export interface XpTrackSnapshot {
  marked: number
  segments: number
}

export interface HarmEntrySnapshot {
  level: number
  name: string
}

export interface CharacterItemSnapshot {
  item_id: string
  carried: boolean
}

// FR-28: the character-sheet fields the interactive panel renders. Not
// generated from the server's OpenAPI spec - GameState/Character are only
// ever exchanged over the WS channel, which has no OpenAPI representation
// (ADR-0002's generated-types contract covers REST endpoints).
export interface CharacterSnapshot {
  name: string
  playbook: string
  stress: { marked: number }
  harm: { entries: HarmEntrySnapshot[] }
  coin: number
  load: number
  items: CharacterItemSnapshot[]
  playbook_xp: XpTrackSnapshot
  attribute_xp: Record<'insight' | 'prowess' | 'resolve', XpTrackSnapshot>
  [key: string]: unknown
}

// FR-29: a crew's claim, shown read-only in the table view v1 - claiming
// territory isn't wired to any engine operation yet (it's set at crew
// creation/guided entry), so there's nothing for the panel to call.
export interface ClaimSnapshot {
  id: string
  name: string
  controlled: boolean
  is_turf: boolean
}

export interface CrewSnapshot {
  name: string
  crew_type: string
  claims: ClaimSnapshot[]
  [key: string]: unknown
}

export interface ClockSnapshot {
  name: string
  kind: string
  segments: number
  filled: number
}

// FR-36: session zero's generated setting - null until the GM agent
// calls set_campaign_canon (ai/tools.py), which is why every field here
// has to be optional at the top: canon itself may not exist yet.
export interface CanonSnapshot {
  setting_name: string
  tone: string | null
  factions: string[]
  locations: string[]
  facts: string[]
}

// FR-17: session zero's safety-tool agreements - null until
// set_session_zero_config is called.
export interface SessionZeroSnapshot {
  lines: string[]
  veils: string[]
  tone: string | null
}

// FR-31/FR-32: one entity-tagged event from the append-only log - the
// journal view's entire data source, already broadcast in every `state`
// message (FR-19: the journal is fully reconstructible from the event log).
export interface JournalEntry {
  sequence: number
  entity_type: string
  entity_id: string
  event_type: string
  payload: Record<string, unknown>
  occurred_at: string
}

export interface GameStateSnapshot {
  character: CharacterSnapshot
  crew: CrewSnapshot
  clocks: Record<string, ClockSnapshot>
  canon: CanonSnapshot | null
  session_zero: SessionZeroSnapshot | null
  log: { events: JournalEntry[] }
  [key: string]: unknown
}

export interface SheetOperation {
  name:
    | 'mark_stress'
    | 'apply_harm'
    | 'heal_character'
    | 'mark_xp'
    | 'adjust_coin'
    | 'set_item_carried'
    | 'tick_clock'
  args: Record<string, unknown>
}

// FR-16: the GM-proposed roll (Action Roll steps 1-4) the player negotiates
// before it executes - pool/position/effect shown, push/Devil's Bargain/
// trade-off offered.
export interface RollProposal {
  action: string
  position: 'controlled' | 'risky' | 'desperate'
  effect: 'zero' | 'limited' | 'standard' | 'great' | 'extreme'
  pool_size: number
}

export interface RollDecision {
  push_dice?: boolean
  push_effect?: boolean
  devils_bargain?: string | null
  trade?: 'worse_position_better_effect' | 'better_position_worse_effect' | null
}

// FR-19: after an undo, the visible chat needs to shrink to match the
// rewound log too, not just the mechanical state - rebuilt from the same
// player_message/narration events the recap/journal already use, rather
// than just clearing it (a blank panel would look like a bug, not a
// deliberate rewind).
function messagesFromLog(events: JournalEntry[]): ChatMessage[] {
  return events
    .filter((entry) => entry.event_type === 'player_message' || entry.event_type === 'narration')
    .map((entry) =>
      entry.event_type === 'player_message'
        ? { kind: 'player', text: String(entry.payload.text) }
        : { kind: 'narration', text: String(entry.payload.text), done: true },
    )
}

// FR-18/FR-30: server-authoritative state deltas over one WebSocket
// connection, scoped to one persisted campaign. The client only ever sends
// player messages; every state change arrives as a tool_call/narration_done
// event from the server.
export function useSessionSocket(campaignId: string) {
  const [connected, setConnected] = useState(false)
  const [busy, setBusy] = useState(false)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [state, setState] = useState<GameStateSnapshot | null>(null)
  const [pendingRoll, setPendingRoll] = useState<RollProposal | null>(null)
  const socketRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    setMessages([])
    setState(null)
    setPendingRoll(null)

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const socket = new WebSocket(`${protocol}//${window.location.host}/ws/session/${campaignId}`)
    socketRef.current = socket

    socket.onopen = () => setConnected(true)
    socket.onclose = () => setConnected(false)
    socket.onmessage = (event: MessageEvent<string>) => {
      const data = JSON.parse(event.data)
      switch (data.type) {
        case 'state':
          setState(data.state)
          break
        case 'roll_proposed':
          setPendingRoll({
            action: data.action,
            position: data.position,
            effect: data.effect,
            pool_size: data.pool_size,
          })
          break
        case 'tool_call':
          setPendingRoll(null)
          setMessages((prev) => [...prev, { kind: 'tool', name: data.name, result: data.result }])
          break
        case 'narration_chunk':
          setMessages((prev) => {
            const last = prev.at(-1)
            if (last?.kind === 'narration' && !last.done) {
              return [...prev.slice(0, -1), { ...last, text: last.text + data.text }]
            }
            return [...prev, { kind: 'narration', text: data.text, done: false }]
          })
          break
        case 'narration_done':
          setState(data.state)
          setBusy(false)
          setMessages((prev) => {
            const last = prev.at(-1)
            return last?.kind === 'narration' ? [...prev.slice(0, -1), { ...last, done: true }] : prev
          })
          break
        case 'error':
          setBusy(false)
          setMessages((prev) => [...prev, { kind: 'error', message: data.message }])
          break
        case 'undo_done':
          setState(data.state)
          setBusy(false)
          setPendingRoll(null)
          setMessages(messagesFromLog(data.state.log.events))
          break
      }
    }

    return () => socket.close()
  }, [campaignId])

  const sendMessage = useCallback((text: string) => {
    setMessages((prev) => [...prev, { kind: 'player', text }])
    setBusy(true)
    socketRef.current?.send(JSON.stringify({ type: 'player_message', text }))
  }, [])

  const sendRollDecision = useCallback((decision: RollDecision) => {
    setPendingRoll(null)
    socketRef.current?.send(JSON.stringify({ type: 'roll_decision', decision }))
  }, [])

  const sendSheetOperation = useCallback((operation: SheetOperation) => {
    socketRef.current?.send(JSON.stringify({ type: 'sheet_operation', ...operation }))
  }, [])

  const sendUndo = useCallback((sequence: number) => {
    socketRef.current?.send(JSON.stringify({ type: 'undo', sequence }))
  }, [])

  return {
    connected,
    busy,
    messages,
    state,
    pendingRoll,
    sendMessage,
    sendRollDecision,
    sendSheetOperation,
    sendUndo,
  }
}
