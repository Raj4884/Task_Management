/** LogSentry - Log Explorer Page */
import { api } from '../api.js';
import { renderSearchBar } from '../components/search-bar.js';
import { renderFilterPanel, getFilters } from '../components/filter-panel.js';
import { renderLogViewer } from '../components/log-viewer.js';

let currentQuery = '';
let currentPage = 1;

export async function renderExplorePage(container) {
    container.innerHTML = `
    <div class="page-enter">
        <div class="page-header"><h1>Log Explorer</h1>
            <div class="page-header-actions">
                <button class="btn btn-sm btn-secondary" id="export-csv-btn">Export CSV</button>
                <button class="btn btn-sm btn-secondary" id="export-json-btn">Export JSON</button>
            </div>
        </div>
        <div id="search-area"></div>
        <div id="filter-area" class="mt-4"></div>
        <div id="logs-area" class="mt-4"><div class="skeleton skeleton-chart"></div></div>
    </div>`;

    // Load services for filter dropdown
    let services = [];
    try { const svcData = await api.getServices(); services = (svcData || []).map(s => s.service_name); } catch(e) {}

    renderSearchBar(document.getElementById('search-area'), { onSearch: (q) => { currentQuery = q; currentPage = 1; loadLogs(); } });
    renderFilterPanel(document.getElementById('filter-area'), { services, onApply: () => { currentPage = 1; loadLogs(); } });
    await loadLogs();

    document.getElementById('export-csv-btn')?.addEventListener('click', () => window.open(`/api/export/csv?q=${currentQuery}`, '_blank'));
    document.getElementById('export-json-btn')?.addEventListener('click', () => window.open(`/api/export/json?q=${currentQuery}`, '_blank'));
}

async function loadLogs() {
    const filters = getFilters();
    const params = { q: currentQuery, page: currentPage, page_size: 50, ...filters };
    const area = document.getElementById('logs-area');

    try {
        const data = await api.searchLogs(params);
        if (data) {
            renderLogViewer(area, data.logs || [], {
                page: data.page, totalPages: data.total_pages, total: data.total,
                onPageChange: (p) => { currentPage = p; loadLogs(); },
            });
        } else {
            area.innerHTML = '<div class="empty-state"><p>Unable to load logs. API may be unavailable.</p></div>';
        }
    } catch (err) {
        area.innerHTML = `<div class="empty-state"><p>Error: ${err.message}</p></div>`;
    }
}
