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

// FR-30: server-authoritative state deltas over one WebSocket connection.
// The client only ever sends player messages; every state change arrives
// as a tool_call/narration_done event from the server.
export function useSessionSocket() {
  const [connected, setConnected] = useState(false)
  const [busy, setBusy] = useState(false)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [state, setState] = useState<GameStateSnapshot | null>(null)
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
        case 'tool_call':
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

  return { connected, busy, messages, state, sendMessage }
}
