import { useCallback, useEffect, useRef, useState } from 'react'

export type ChatMessage =
  | { kind: 'player'; text: string }
  | { kind: 'companion'; name: string; text: string }
  | { kind: 'narration'; text: string; done: boolean }
  | { kind: 'tool'; name: string; result: unknown; events: JournalEntry[] }
  | { kind: 'companion-decision'; name: string; decision: RollDecision }
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

export interface ArmorSnapshot {
  has_armor: boolean
  has_heavy_armor: boolean
  has_special_armor: boolean
  armor_used: boolean
  heavy_armor_used: boolean
  special_armor_used: boolean
}

export interface TraumaSnapshot {
  conditions: string[]
}

// FR-28: the character-sheet fields the interactive panel renders. Not
// generated from the server's OpenAPI spec - GameState/Character are only
// ever exchanged over the WS channel, which has no OpenAPI representation
// (ADR-0002's generated-types contract covers REST endpoints).
export interface CharacterSnapshot {
  name: string
  alias?: string | null
  look?: string | null
  heritage?: string | null
  heritage_detail?: string | null
  background?: string | null
  background_detail?: string | null
  playbook: string
  action_ratings?: Record<string, number>
  special_ability_ids?: string[]
  stress: { marked: number }
  trauma?: TraumaSnapshot
  trauma_pending: boolean
  harm: { entries: HarmEntrySnapshot[] }
  armor?: ArmorSnapshot
  vice?: string | null
  vice_detail?: string | null
  vice_purveyor?: string | null
  healing_clock: ClockSnapshot
  coin: number
  stash?: number
  load: number
  load_level?: 'light' | 'normal' | 'heavy'
  items: CharacterItemSnapshot[]
  friend?: string | null
  rival?: string | null
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

export interface CohortSnapshot {
  types: string[]
  is_expert: boolean
  quality: number
  scale: number
  edges: string[]
  flaws: string[]
  harm: { level: string }
}

export interface CrewSnapshot {
  name: string
  crew_type: string
  tier: number
  hold: 'weak' | 'strong'
  claims: ClaimSnapshot[]
  heat: { heat: number }
  wanted_level: number
  rep: { rep: number; turf: number; threshold: number }
  coin: number
  stash: number
  xp: XpTrackSnapshot
  upgrade_ids: string[]
  special_ability_ids: string[]
  cohorts: CohortSnapshot[]
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

// FR-34: nodes for the relationship map - NPCs, factions (as a status
// with the crew), and generic relationship edges between any two
// entities (identified by "<type>:<id>" strings on either side).
export interface NpcSnapshot {
  id: string
  name: string
  tags: string[]
  faction_id: string | null
}

export interface FactionStatusSnapshot {
  crew_id: string
  faction_id: string
  status: number
  history: number[]
}

export interface RelationshipSnapshot {
  subject_type: string
  subject_id: string
  object_type: string
  object_id: string
  kind: 'ally' | 'rival' | 'debt' | 'romance' | 'vendetta'
  status: string | null
  history: number[]
}

// FR-25/FR-35: a seat (human or AI) controlling any number of PCs; a
// character with no seat naming it is human-controlled by default (see
// engine.controller.Controller/is_ai_controlled - looked up, not stored on
// the character itself).
export interface ControllerSnapshot {
  seat_id: string
  kind: 'human' | 'ai'
  character_ids: string[]
  cohort_ids: string[]
}

export interface GameStateSnapshot {
  session: { phase: string; [key: string]: unknown }
  character: CharacterSnapshot
  characters: Record<string, CharacterSnapshot>
  crew: CrewSnapshot
  controllers: Record<string, ControllerSnapshot>
  clocks: Record<string, ClockSnapshot>
  canon: CanonSnapshot | null
  session_zero: SessionZeroSnapshot | null
  npcs: Record<string, NpcSnapshot>
  faction_statuses: Record<string, FactionStatusSnapshot>
  relationships: Record<string, RelationshipSnapshot>
  log: { events: JournalEntry[] }
  [key: string]: unknown
}

export interface SheetOperation {
  name:
    | 'mark_stress'
    | 'mark_trauma'
    | 'use_armor'
    | 'restore_armor'
    | 'apply_harm'
    | 'heal_character'
    | 'mark_xp'
    | 'adjust_coin'
    | 'adjust_stash'
    | 'cash_out_stash'
    | 'set_item_carried'
    | 'set_load_level'
    | 'tick_clock'
    | 'add_crew_heat'
    | 'adjust_wanted_level'
    | 'adjust_crew_rep'
    | 'adjust_crew_coin'
    | 'adjust_crew_turf'
    | 'develop_crew'
  args: Record<string, unknown>
}

// FR-16: the GM-proposed roll (Action Roll steps 1-4) the player negotiates
// before it executes - pool/position/effect shown, push/Devil's Bargain/
// trade-off offered.
export interface RollProposal {
  character_id: string
  action: string
  position: 'controlled' | 'risky' | 'desperate'
  effect: 'zero' | 'limited' | 'standard' | 'great' | 'extreme'
  pool_size: number
  devils_bargain?: string | null
}

export interface RollDecision {
  push_dice?: boolean
  push_effect?: boolean
  devils_bargain?: string | null
  trade?: 'worse_position_better_effect' | 'better_position_worse_effect' | null
  assist_character_id?: string | null
  declined?: boolean
}

// FR-19: after an undo, the visible chat needs to shrink to match the
// rewound log too, not just the mechanical state - rebuilt from the same
// player_message/narration/companion_roll_decision events the recap/
// journal already use, rather than just clearing it (a blank panel would
// look like a bug, not a deliberate rewind). A player_message carrying a
// speaker is an AI companion's line (FR-35), rebuilt under its own name
// rather than as something the human typed. Exported for its own tests.
export function messagesFromLog(events: JournalEntry[]): ChatMessage[] {
  return events
    .filter(
      (entry) =>
        entry.event_type === 'player_message' ||
        entry.event_type === 'narration' ||
        entry.event_type === 'companion_roll_decision',
    )
    .map((entry): ChatMessage => {
      if (entry.event_type === 'narration') {
        return { kind: 'narration', text: String(entry.payload.text), done: true }
      }
      if (entry.event_type === 'companion_roll_decision') {
        const p = entry.payload
        return {
          kind: 'companion-decision',
          name: String(p.name),
          decision: {
            push_dice: p.push_dice as boolean | undefined,
            push_effect: p.push_effect as boolean | undefined,
            devils_bargain: p.devils_bargain as string | null | undefined,
            trade: p.trade as RollDecision['trade'],
            assist_character_id: p.assist_character_id as string | null | undefined,
            declined: p.declined as boolean | undefined,
          },
        }
      }
      if (entry.payload.speaker !== undefined) {
        return {
          kind: 'companion',
          name: String(entry.payload.speaker),
          text: String(entry.payload.text),
        }
      }
      return { kind: 'player', text: String(entry.payload.text) }
    })
}

// FR-18/FR-30: server-authoritative state deltas over one WebSocket
// connection, scoped to one persisted campaign. The client only ever sends
// player messages; every state change arrives as a tool_call/narration_done
// event from the server.
export function useSessionSocket(campaignId: string) {
  const [connected, setConnected] = useState(false)
  const [reconnecting, setReconnecting] = useState(false)
  const [reconnectAttempt, setReconnectAttempt] = useState(0)
  const [busy, setBusy] = useState(false)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [state, setState] = useState<GameStateSnapshot | null>(null)
  const [pendingRoll, setPendingRoll] = useState<RollProposal | null>(null)
  const socketRef = useRef<WebSocket | null>(null)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const attemptRef = useRef<number>(0)
  const unmountedRef = useRef<boolean>(false)

  const connect = useCallback(() => {
    if (unmountedRef.current) return
    if (timerRef.current) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const socket = new WebSocket(`${protocol}//${window.location.host}/ws/session/${campaignId}`)
    socketRef.current = socket

    socket.onopen = () => {
      setConnected(true)
      setReconnecting(false)
      setReconnectAttempt(0)
      attemptRef.current = 0
    }

    socket.onclose = () => {
      setConnected(false)
      setBusy(false)
      setPendingRoll(null)

      if (!unmountedRef.current) {
        attemptRef.current += 1
        setReconnecting(true)
        setReconnectAttempt(attemptRef.current)
        const delay = Math.min(1000 * Math.pow(1.5, attemptRef.current - 1), 10000)
        timerRef.current = setTimeout(() => {
          connect()
        }, delay)
      }
    }

    socket.onmessage = (event: MessageEvent<string>) => {
      const data = JSON.parse(event.data)
      switch (data.type) {
        case 'state':
          setState(data.state)
          setBusy(false)
          setMessages((prev) => (prev.length === 0 ? messagesFromLog(data.state.log.events) : prev))
          break
        case 'roll_proposed':
          setPendingRoll({
            character_id: data.character_id,
            action: data.action,
            position: data.position,
            effect: data.effect,
            pool_size: data.pool_size,
            devils_bargain: data.devils_bargain,
          })
          break
        case 'tool_call':
          setPendingRoll(null)
          if (data.state) {
            setState(data.state)
          }
          setMessages((prev) => [
            ...prev,
            { kind: 'tool', name: data.name, result: data.result, events: data.events ?? [] },
          ])
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
        case 'companion_message':
          // FR-35: an AI crewmate's in-character line, labelled with its
          // own name - without this it would be invisible live and only
          // surface (mislabelled) after an undo rebuild.
          if (data.state) {
            setState(data.state)
          }
          setMessages((prev) => [
            ...prev,
            { kind: 'companion', name: data.name, text: data.text },
          ])
          break
        case 'companion_roll_decision':
          // FR-16/FR-35: previously invisible live (dropped entirely, not
          // just deferred to the Journal) - a companion's push/bargain/
          // trade-off choice, the same decision a human makes in the roll
          // negotiation dialog. Fields ride flat alongside character_id/name
          // (matching every other event payload in this app), not nested
          // under a "decision" key.
          if (data.state) {
            setState(data.state)
          }
          setMessages((prev) => [
            ...prev,
            {
              kind: 'companion-decision',
              name: data.name,
              decision: {
                push_dice: data.push_dice,
                push_effect: data.push_effect,
                devils_bargain: data.devils_bargain,
                trade: data.trade,
                assist_character_id: data.assist_character_id,
              },
            },
          ])
          break
        case 'error':
          setBusy(false)
          setPendingRoll(null)
          if (data.state) {
            setState(data.state)
          }
          setMessages((prev) => [...prev, { kind: 'error', message: data.message }])
          break
        case 'undo_done':
        case 'x_card_done':
          setState(data.state)
          setBusy(false)
          setPendingRoll(null)
          setMessages(messagesFromLog(data.state.log.events))
          break
      }
    }
  }, [campaignId])

  useEffect(() => {
    unmountedRef.current = false
    setMessages([])
    setState(null)
    setPendingRoll(null)
    attemptRef.current = 0

    connect()

    return () => {
      unmountedRef.current = true
      if (timerRef.current) {
        clearTimeout(timerRef.current)
      }
      socketRef.current?.close()
    }
  }, [campaignId, connect])

  const manualReconnect = useCallback(() => {
    if (socketRef.current) {
      socketRef.current.close()
    }
    attemptRef.current = 0
    setReconnecting(true)
    connect()
  }, [connect])

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

  const sendXCard = useCallback(
    (note?: string, sequence?: number, text?: string) => {
      setBusy(true)
      socketRef.current?.send(JSON.stringify({ type: 'x_card', note, sequence, text }))
    },
    [],
  )

  const clearBusy = useCallback(() => {
    setBusy(false)
    setPendingRoll(null)
  }, [])

  return {
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
    reconnect: manualReconnect,
  }
}
