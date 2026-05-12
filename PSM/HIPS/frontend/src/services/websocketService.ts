export type EventCallback = (event: any) => void

class WebSocketService {
  private ws: WebSocket | null = null
  private callbacks: Map<string, EventCallback[]> = new Map()
  private reconnectInterval: number = 5000
  private reconnectTimer: number | null = null

  connect() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/ws/events`

    try {
      this.ws = new WebSocket(wsUrl)

      this.ws.onopen = () => {
        if (this.reconnectTimer) {
          clearTimeout(this.reconnectTimer)
          this.reconnectTimer = null
        }
      }

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          this.dispatchIncomingEvent(data)
        } catch (error) {
          console.error('Error parsing WebSocket message:', error)
        }
      }

      this.ws.onerror = () => {
        // connection errors handled in onclose → scheduleReconnect
      }

      this.ws.onclose = () => {
        this.scheduleReconnect()
      }
    } catch (error) {
      this.scheduleReconnect()
    }
  }

  disconnect() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }

    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }

  on(eventType: string, callback: EventCallback) {
    if (!this.callbacks.has(eventType)) {
      this.callbacks.set(eventType, [])
    }
    this.callbacks.get(eventType)!.push(callback)
  }

  off(eventType: string, callback: EventCallback) {
    const callbacks = this.callbacks.get(eventType)
    if (callbacks) {
      const index = callbacks.indexOf(callback)
      if (index > -1) {
        callbacks.splice(index, 1)
      }
    }
  }

  private notifyCallbacks(eventType: string, data: any) {
    const callbacks = this.callbacks.get(eventType)
    if (callbacks) {
      callbacks.forEach((callback) => callback(data))
    }

    // Also notify 'all' listeners
    const allCallbacks = this.callbacks.get('all')
    if (allCallbacks) {
      allCallbacks.forEach((callback) => callback(data))
    }
  }

  private dispatchIncomingEvent(payload: any) {
    // Preserve the raw channel first.
    if (payload?.type) {
      this.notifyCallbacks(payload.type, payload)
    }

    // Backend websocket publishes { type: "event", data: { event_type: ... } }.
    const eventType: string | undefined = payload?.data?.event_type
    if (!eventType) return

    // Fan out to broad channels consumed by pages.
    this.notifyCallbacks('all', payload.data)
    this.notifyCallbacks('activity', payload.data)

    if (eventType.startsWith('process_')) {
      this.notifyCallbacks('process', payload.data)
      this.notifyCallbacks('log', payload.data)
      return
    }

    if (eventType.startsWith('network_')) {
      this.notifyCallbacks('network', payload.data)
      this.notifyCallbacks('log', payload.data)
      return
    }

    if (eventType.startsWith('file_')) {
      this.notifyCallbacks('file', payload.data)
      this.notifyCallbacks('log', payload.data)
      return
    }

    if (eventType === 'registry_change') {
      this.notifyCallbacks('registry', payload.data)
      this.notifyCallbacks('log', payload.data)
      return
    }

    if (eventType.includes('alert') || eventType.includes('ransomware')) {
      this.notifyCallbacks('alert', payload.data)
      return
    }

    // Fallback for other monitor events.
    this.notifyCallbacks('log', payload.data)
  }

  private scheduleReconnect() {
    if (!this.reconnectTimer) {
      this.reconnectTimer = window.setTimeout(() => {
        this.connect()
      }, this.reconnectInterval)
    }
  }
}

export const websocketService = new WebSocketService()
