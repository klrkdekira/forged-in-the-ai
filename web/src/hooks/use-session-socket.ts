import { useCallback, useEffect, useRef, useState } from 'react'

export type ChatMessage =
  | { kind: 'player'; text: string }
  | { kind: 'narration'; text: string; done: boolean }
  | { kind: 'tool'; name: string; result: unknown }
  | { kind: 'error'; message: string }

export interface GameStateSnapshot {
  character: { name: string; playbook: string; [key: string]: unknown }
  crew: { name: string; crew_type: string; [key: string]: unknown }
  [key: string]: unknown
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

// FR-30: server-authoritative state deltas over one WebSocket connection.
// The client only ever sends player messages; every state change arrives
// as a tool_call/narration_done event from the server.
export function useSessionSocket() {
  const [connected, setConnected] = useState(false)
  const [busy, setBusy] = useState(false)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [state, setState] = useState<GameStateSnapshot | null>(null)
  const [pendingRoll, setPendingRoll] = useState<RollProposal | null>(null)
  const socketRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const socket = new WebSocket(`${protocol}//${window.location.host}/ws/session`)
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
      }
    }

    return () => socket.close()
  }, [])

  const sendMessage = useCallback((text: string) => {
    setMessages((prev) => [...prev, { kind: 'player', text }])
    setBusy(true)
    socketRef.current?.send(JSON.stringify({ type: 'player_message', text }))
  }, [])

  const sendRollDecision = useCallback((decision: RollDecision) => {
    setPendingRoll(null)
    socketRef.current?.send(JSON.stringify({ type: 'roll_decision', decision }))
  }, [])

  return { connected, busy, messages, state, pendingRoll, sendMessage, sendRollDecision }
}
