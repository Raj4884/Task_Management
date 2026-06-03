/** LogSentry - Alerts Page */
import { api } from '../api.js';

const SEV_CLASSES = { info: 'badge-info', warning: 'badge-warn', critical: 'badge-error', emergency: 'badge-fatal' };
const STATUS_CLASSES = { active: 'badge-error', acknowledged: 'badge-warn', resolved: 'badge-success', silenced: 'badge-trace' };

export async function renderAlertsPage(container) {
    container.innerHTML = `
    <div class="page-enter">
        <div class="page-header"><h1>Alerts</h1></div>
        <div id="alerts-area"><div class="skeleton skeleton-chart"></div></div>
    </div>`;

    await loadAlerts(container);
}

async function loadAlerts(container) {
    const area = document.getElementById('alerts-area');
    try {
        const alerts = await api.getAlerts({ limit: 50 });
        if (!alerts || alerts.length === 0) {
            area.innerHTML = '<div class="empty-state"><p>No alerts. Your services are running smoothly! 🎉</p></div>';
            return;
        }
        area.innerHTML = `<div class="log-table-container"><table class="table"><thead><tr>
            <th>Status</th><th>Severity</th><th>Title</th><th>Service</th><th>Triggered</th><th>Actions</th>
        </tr></thead><tbody>${alerts.map(a => `<tr>
            <td><span class="badge ${STATUS_CLASSES[a.status] || ''}">${a.status}</span></td>
            <td><span class="badge ${SEV_CLASSES[a.severity] || ''}">${a.severity}</span></td>
            <td>${a.title}</td>
            <td>${a.service_name || '-'}</td>
            <td class="text-xs text-muted">${new Date(a.triggered_at).toLocaleString()}</td>
            <td class="flex gap-1">
                ${a.status === 'active' ? `<button class="btn btn-sm btn-ghost" onclick="window._ackAlert('${a.id}')">Ack</button>` : ''}
                ${a.status !== 'resolved' ? `<button class="btn btn-sm btn-ghost" onclick="window._resolveAlert('${a.id}')">Resolve</button>` : ''}
            </td>
        </tr>`).join('')}</tbody></table></div>`;
    } catch(e) {
        area.innerHTML = '<div class="empty-state"><p>Unable to load alerts</p></div>';
    }
}

// Global handlers for inline onclick
window._ackAlert = async (id) => { await api.acknowledgeAlert(id); renderAlertsPage(document.getElementById('page-content')); };
window._resolveAlert = async (id) => { await api.resolveAlert(id); renderAlertsPage(document.getElementById('page-content')); };
