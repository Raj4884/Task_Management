/**
 * LogSentry - Stats Cards component
 */
export function renderStatsCards(container, stats) {
    const cards = [
        { label: 'Total Logs (24h)', value: formatNumber(stats.total_logs_24h), icon: '📊', color: 'var(--accent-primary)', trend: null },
        { label: 'Errors (24h)', value: formatNumber(stats.total_errors_24h), icon: '⚠️', color: 'var(--color-error)', trend: null },
        { label: 'Error Rate', value: `${stats.error_rate_pct || 0}%`, icon: '📈', color: stats.error_rate_pct > 10 ? 'var(--color-error)' : 'var(--color-success)', trend: null },
        { label: 'Active Services', value: stats.active_services || 0, icon: '🖥️', color: 'var(--color-success)', trend: null },
        { label: 'Active Alerts', value: stats.active_alerts || 0, icon: '🔔', color: stats.active_alerts > 0 ? 'var(--color-warning)' : 'var(--text-muted)', trend: null },
        { label: 'Logs/sec', value: stats.logs_per_second || 0, icon: '⚡', color: 'var(--accent-secondary)', trend: null },
    ];

    container.innerHTML = `<div class="stats-grid">${cards.map((c, i) => `
        <div class="stat-card animate-slideInUp stagger-${i + 1}">
            <div class="stat-card-header">
                <span class="stat-card-label">${c.label}</span>
                <div class="stat-card-icon" style="background:${c.color}20;color:${c.color};font-size:18px;">${c.icon}</div>
            </div>
            <div class="stat-card-value" style="color:${c.color}">${c.value}</div>
        </div>
    `).join('')}</div>`;
}

function formatNumber(n) {
    if (n === undefined || n === null) return '0';
    if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
    if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
    return n.toString();
}
