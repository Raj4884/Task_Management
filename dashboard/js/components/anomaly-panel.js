/** LogSentry - Anomaly Panel component */
const TYPE_COLORS = { error_spike: 'var(--color-error)', volume_anomaly: 'var(--color-warning)', latency_anomaly: 'var(--accent-secondary)', pattern_anomaly: 'var(--color-debug)', novel_error: 'var(--color-fatal)' };

export function renderAnomalyPanel(container, anomalies) {
    if (!anomalies || anomalies.length === 0) {
        container.innerHTML = '<div class="empty-state"><p>No anomalies detected. ML models are monitoring your services.</p></div>';
        return;
    }
    container.innerHTML = anomalies.map(a => `
        <div class="card card-compact mb-4 animate-slideInUp" style="border-left:3px solid ${TYPE_COLORS[a.anomaly_type] || 'var(--accent-primary)'}">
            <div class="flex justify-between items-center mb-2">
                <div class="flex items-center gap-2">
                    <span class="badge" style="background:${TYPE_COLORS[a.anomaly_type]}20;color:${TYPE_COLORS[a.anomaly_type]}">${(a.anomaly_type||'').replace(/_/g,' ')}</span>
                    <span class="text-sm">${a.service_name || 'Global'}</span>
                </div>
                <span class="text-xs text-muted">${new Date(a.detected_at).toLocaleString()}</span>
            </div>
            <p class="text-sm mb-2">${a.description || 'Anomaly detected'}</p>
            <div class="flex items-center gap-3">
                <span class="text-xs text-muted">Severity</span>
                <div class="progress-bar" style="width:120px;height:4px">
                    <div class="progress-bar-fill" style="width:${(a.severity_score * 100)}%;background:${a.severity_score > 0.7 ? 'var(--color-error)' : a.severity_score > 0.4 ? 'var(--color-warning)' : 'var(--accent-primary)'}"></div>
                </div>
                <span class="text-xs" style="color:${a.severity_score > 0.7 ? 'var(--color-error)' : 'var(--text-muted)'}">${(a.severity_score * 100).toFixed(0)}%</span>
            </div>
        </div>
    `).join('');
}
