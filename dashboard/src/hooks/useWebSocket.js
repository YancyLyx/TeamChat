import { useEffect, useRef, useCallback, useState } from 'react'

const WS_URL = `ws://${window.location.hostname}:8000/ws`
const MAX_RETRIES = 5
const BASE_DELAY = 1000

/**
 * WebSocket connection hook with auto-reconnect.
 *
 * Returns:
 *  - messages: array of received message objects
 *  - connectionStatus: 'connected' | 'disconnected' | 'connecting'
 *  - clearMessages: () => void
 */
export function useWebSocket() {
  const [messages, setMessages] = useState([])
  const [connectionStatus, setConnectionStatus] = useState('disconnected')
  const wsRef = useRef(null)
  const retryCountRef = useRef(0)
  const retryTimerRef = useRef(null)

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    setConnectionStatus('connecting')
    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen = () => {
      setConnectionStatus('connected')
      retryCountRef.current = 0
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        setMessages((prev) => [...prev, msg])
      } catch {
        // ignore malformed messages
      }
    }

    ws.onerror = () => {
      // onclose will fire after this
    }

    ws.onclose = () => {
      setConnectionStatus('disconnected')
      wsRef.current = null

      // Exponential backoff reconnect
      if (retryCountRef.current < MAX_RETRIES) {
        retryCountRef.current += 1
        const delay = BASE_DELAY * Math.pow(2, retryCountRef.current - 1)
        retryTimerRef.current = setTimeout(() => connect(), delay)
      }
    }
  }, [])

  const clearMessages = useCallback(() => {
    setMessages([])
  }, [])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(retryTimerRef.current)
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [connect])

  return { messages, connectionStatus, clearMessages }
}
