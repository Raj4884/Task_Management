/** LogSentry - Service Map / Health Grid */
import { navigate } from '../router.js';

export function renderServiceMap(container, services) {
    if (!services || services.length === 0) {
        container.innerHTML = '<div class="empty-state"><p>No services detected yet. Waiting for log data...</p></div>';
        return;
    }
    container.innerHTML = `<div class="services-grid">${services.map(s => {
        const statusClass = s.status === 'active' ? 'status-dot-active' : s.status === 'degraded' ? 'status-dot-degraded' : 'status-dot-down';
        return `
        <div class="card card-compact service-card animate-scaleIn" data-service="${s.service_name}">
            <div class="service-card-header">
                <span class="status-dot ${statusClass}"></span>
                <span class="service-card-name">${s.service_name}</span>
            </div>
            <div class="service-card-stats">
                <div class="service-card-stat">
                    <div class="service-card-stat-value">${formatNum(s.total_logs_24h)}</div>
                    <div class="service-card-stat-label">Logs</div>
                </div>
                <div class="service-card-stat">
                    <div class="service-card-stat-value" style="color:var(--color-error)">${formatNum(s.errors_24h)}</div>
                    <div class="service-card-stat-label">Errors</div>
                </div>
                <div class="service-card-stat">
                    <div class="service-card-stat-value" style="color:${s.error_rate_pct > 10 ? 'var(--color-error)' : 'var(--color-success)'}">${s.error_rate_pct}%</div>
                    <div class="service-card-stat-label">Error Rate</div>
                </div>
            </div>
        </div>`;
    }).join('')}</div>`;

    container.querySelectorAll('.service-card').forEach(card => {
        card.addEventListener('click', () => navigate(`services/${card.dataset.service}`));
    });
}

function formatNum(n) { return n >= 1000 ? (n/1000).toFixed(1)+'K' : (n||0).toString(); }
