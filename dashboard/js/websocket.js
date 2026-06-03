/**
 * LogSentry - WebSocket and SSE for real-time data
 */
export class RealtimeConnection {
    constructor() {
        this.ws = null;
        this.sse = null;
        this.onLog = null;
        this.onAlert = null;
        this.reconnectDelay = 1000;
        this.maxReconnectDelay = 30000;
        this.connected = false;
    }

    connect() {
        this._connectSSE();
    }

    _connectSSE() {
        try {
            this.sse = new EventSource('/api/logs/stream');
            this.sse.onopen = () => { this.connected = true; this.reconnectDelay = 1000; };
            this.sse.onmessage = (event) => {
                try {
                    const log = JSON.parse(event.data);
                    if (this.onLog) this.onLog(log);
                } catch (e) { /* ignore parse errors */ }
            };
            this.sse.onerror = () => {
                this.connected = false;
                this.sse.close();
                setTimeout(() => this._connectSSE(), this.reconnectDelay);
                this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxReconnectDelay);
            };
        } catch (e) {
            console.warn('SSE not available');
        }
    }

    disconnect() {
        if (this.sse) { this.sse.close(); this.sse = null; }
        if (this.ws) { this.ws.close(); this.ws = null; }
        this.connected = false;
    }
}

export const realtime = new RealtimeConnection();
