/**
 * LogSentry - API Client
 * Handles all HTTP communication with the backend.
 */

class ApiClient {
    constructor(baseUrl = '') {
        this.baseUrl = baseUrl;
        this.onUnauthorized = null;
    }

    getToken() { return localStorage.getItem('logsentry_token'); }
    setToken(token) { localStorage.setItem('logsentry_token', token); }
    setRefreshToken(token) { localStorage.setItem('logsentry_refresh', token); }
    getRefreshToken() { return localStorage.getItem('logsentry_refresh'); }
    clearTokens() { localStorage.removeItem('logsentry_token'); localStorage.removeItem('logsentry_refresh'); }

    async request(method, path, body = null, params = null) {
        let url = `${this.baseUrl}${path}`;
        if (params) {
            const qs = new URLSearchParams();
            Object.entries(params).forEach(([k, v]) => { if (v !== null && v !== undefined && v !== '') qs.append(k, v); });
            const s = qs.toString();
            if (s) url += `?${s}`;
        }

        const headers = { 'Content-Type': 'application/json' };
        const token = this.getToken();
        if (token) headers['Authorization'] = `Bearer ${token}`;

        const opts = { method, headers };
        if (body) opts.body = JSON.stringify(body);

        try {
            const resp = await fetch(url, opts);
            if (resp.status === 401 && this.onUnauthorized) {
                // Try refresh
                const refreshed = await this.refreshToken();
                if (refreshed) {
                    headers['Authorization'] = `Bearer ${this.getToken()}`;
                    const retry = await fetch(url, { ...opts, headers });
                    if (retry.ok) return retry.json();
                }
                this.onUnauthorized();
                return null;
            }
            if (!resp.ok) {
                const err = await resp.json().catch(() => ({ detail: resp.statusText }));
                throw new Error(err.detail || err.message || `HTTP ${resp.status}`);
            }
            return resp.json();
        } catch (err) {
            if (err.name === 'TypeError' && err.message.includes('fetch')) {
                console.warn('API unavailable, using fallback data');
                return null;
            }
            throw err;
        }
    }

    async refreshToken() {
        const refresh = this.getRefreshToken();
        if (!refresh) return false;
        try {
            const resp = await fetch(`${this.baseUrl}/auth/refresh`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ refresh_token: refresh }),
            });
            if (resp.ok) {
                const data = await resp.json();
                this.setToken(data.access_token);
                if (data.refresh_token) this.setRefreshToken(data.refresh_token);
                return true;
            }
        } catch (e) { /* ignore */ }
        return false;
    }

    // Auth
    login(username, password) { return this.request('POST', '/auth/login', { username, password }); }
    register(username, email, password) { return this.request('POST', '/auth/register', { username, email, password }); }
    getMe() { return this.request('GET', '/auth/me'); }

    // Logs
    searchLogs(params) { return this.request('GET', '/api/search', null, params); }
    
    // Analytics
    getDashboardStats() { return this.request('GET', '/api/analytics/dashboard-stats'); }
    getTimeseries(params) { return this.request('GET', '/api/analytics/timeseries', null, params); }
    getErrorRate(params) { return this.request('GET', '/api/analytics/error-rate', null, params); }
    getServices() { return this.request('GET', '/api/analytics/services'); }
    getServiceDetail(name) { return this.request('GET', `/api/analytics/services/${name}`); }
    
    // Alerts
    getAlerts(params) { return this.request('GET', '/api/analytics/alerts', null, params); }
    acknowledgeAlert(id) { return this.request('PUT', `/api/analytics/alerts/${id}/acknowledge`); }
    resolveAlert(id) { return this.request('PUT', `/api/analytics/alerts/${id}/resolve`); }
    
    // Anomalies
    getAnomalies(params) { return this.request('GET', '/api/anomalies', null, params); }
    getRealtimeScores() { return this.request('GET', '/api/anomalies/realtime'); }
    trainModels() { return this.request('POST', '/api/anomalies/train'); }
    getModelStatus() { return this.request('GET', '/api/anomalies/models/status'); }
}

export const api = new ApiClient();
