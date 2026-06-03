/** LogSentry - Dashboard Overview Page */
import { api } from '../api.js';
import { renderStatsCards } from '../components/stats-cards.js';
import { createAreaChart, createDoughnutChart, createBarChart } from '../components/chart.js';
import { renderAnomalyPanel } from '../components/anomaly-panel.js';
import { renderServiceMap } from '../components/service-map.js';

let refreshTimer = null;

export async function renderDashboardPage(container) {
    container.innerHTML = `
    <div class="page-enter">
        <div class="page-header"><h1>Dashboard</h1><div class="page-header-actions"><span class="live-indicator">Live</span></div></div>
        <div id="stats-area"><div class="stats-grid">${'<div class="skeleton skeleton-card"></div>'.repeat(6)}</div></div>
        <div class="charts-grid">
            <div class="card chart-card"><h3>Log Volume (24h)</h3><div class="chart-container"><canvas id="chart-volume"></canvas></div></div>
            <div class="card chart-card"><h3>Error Rate (24h)</h3><div class="chart-container"><canvas id="chart-errors"></canvas></div></div>
            <div class="card chart-card"><h3>Log Level Distribution</h3><div class="chart-container"><canvas id="chart-levels"></canvas></div></div>
            <div class="card chart-card"><h3>Top Error Services</h3><div class="chart-container"><canvas id="chart-top-errors"></canvas></div></div>
        </div>
        <div class="charts-grid">
            <div><h3 class="mb-4" style="font-size:var(--text-md)">Recent Anomalies</h3><div id="anomalies-area"></div></div>
            <div><h3 class="mb-4" style="font-size:var(--text-md)">Service Health</h3><div id="services-area"></div></div>
        </div>
    </div>`;

    await loadDashboardData();

    // Auto-refresh
    if (refreshTimer) clearInterval(refreshTimer);
    refreshTimer = setInterval(loadDashboardData, 30000);
}

export function cleanupDashboard() { if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = null; } }

async function loadDashboardData() {
    try {
        const [stats, timeseries, errorRate, services, anomalies] = await Promise.all([
            api.getDashboardStats(),
            api.getTimeseries({ interval: '1h' }),
            api.getErrorRate({ interval: '1h' }),
            api.getServices(),
            api.getAnomalies({ limit: 5 }),
        ]);

        // Stats cards
        if (stats) renderStatsCards(document.getElementById('stats-area'), stats);

        // Volume chart
        if (timeseries?.data) {
            const labels = timeseries.data.map(d => new Date(d.timestamp).toLocaleTimeString('en', { hour: '2-digit', minute: '2-digit' }));
            createAreaChart('chart-volume', labels, [{ label: 'Logs', data: timeseries.data.map(d => d.value), color: '#3b82f6' }]);
        }

        // Error rate chart
        if (errorRate?.data) {
            const labels = errorRate.data.map(d => new Date(d.timestamp).toLocaleTimeString('en', { hour: '2-digit', minute: '2-digit' }));
            createAreaChart('chart-errors', labels, [{ label: 'Error %', data: errorRate.data.map(d => d.value), color: '#ef4444' }]);
        }

        // Level distribution
        if (stats) {
            const total = stats.total_logs_24h || 1;
            const errs = stats.total_errors_24h || 0;
            const rest = total - errs;
            createDoughnutChart('chart-levels', ['INFO', 'WARN', 'ERROR', 'DEBUG'], [Math.round(rest*0.65), Math.round(rest*0.2), errs, Math.round(rest*0.15)],
                ['#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6']);
        }

        // Top error services
        if (stats?.top_error_services?.length) {
            createBarChart('chart-top-errors', stats.top_error_services.map(s => s.service_name), stats.top_error_services.map(s => s.error_count));
        }

        // Anomalies
        if (anomalies) renderAnomalyPanel(document.getElementById('anomalies-area'), Array.isArray(anomalies) ? anomalies : []);

        // Services
        if (services) renderServiceMap(document.getElementById('services-area'), services);

    } catch (err) {
        console.warn('Dashboard data load error:', err);
        // Show fallback data
        renderStatsCards(document.getElementById('stats-area'), { total_logs_24h: 0, total_errors_24h: 0, error_rate_pct: 0, active_services: 0, active_alerts: 0, logs_per_second: 0 });
    }
}
