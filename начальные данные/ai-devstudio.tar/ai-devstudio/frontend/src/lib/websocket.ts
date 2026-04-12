type WSHandler = (data: any) => void

class WSClient {
  private ws: WebSocket | null = null
  private handlers: Map<string, WSHandler[]> = new Map()
  private url: string = ''
  private reconnectTimer: any = null

  connect(path: string) {
    const WS_URL = process.env.NEXT_PUBLIC_WS_URL || `wss://${window.location.host}`
    const token = localStorage.getItem('access_token') || ''
    this.url = `${WS_URL}${path}?token=${token}`
    this._connect()
  }

  private _connect() {
    if (this.ws) this.ws.close()
    this.ws = new WebSocket(this.url)

    this.ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        const handlers = this.handlers.get(data.event) || []
        handlers.forEach((h) => h(data))
        // Глобальные обработчики
        const all = this.handlers.get('*') || []
        all.forEach((h) => h(data))
      } catch {}
    }

    this.ws.onclose = () => {
      // Переподключение через 3 секунды
      this.reconnectTimer = setTimeout(() => this._connect(), 3000)
    }

    this.ws.onerror = () => {
      this.ws?.close()
    }
  }

  on(event: string, handler: WSHandler) {
    if (!this.handlers.has(event)) this.handlers.set(event, [])
    this.handlers.get(event)!.push(handler)
  }

  off(event: string, handler: WSHandler) {
    const list = this.handlers.get(event) || []
    this.handlers.set(event, list.filter((h) => h !== handler))
  }

  disconnect() {
    clearTimeout(this.reconnectTimer)
    this.ws?.close()
    this.ws = null
  }
}

export const dashboardWS = new WSClient()
export const projectWS = new WSClient()
