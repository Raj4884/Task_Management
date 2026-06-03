/** LogSentry - Filter Panel component */
export function renderFilterPanel(container, { onApply, services = [] } = {}) {
    container.innerHTML = `
    <div class="filter-bar animate-fadeIn">
        <select id="filter-time" class="select" style="width:150px">
            <option value="15m">Last 15 min</option><option value="1h" selected>Last 1 hour</option>
            <option value="6h">Last 6 hours</option><option value="24h">Last 24 hours</option>
            <option value="7d">Last 7 days</option>
        </select>
        <select id="filter-service" class="select" style="width:160px">
            <option value="">All Services</option>
            ${services.map(s => `<option value="${s}">${s}</option>`).join('')}
        </select>
        <div class="flex gap-2 items-center" style="flex-wrap:wrap">
            ${['ERROR','WARN','INFO','DEBUG','FATAL','TRACE'].map(lvl => `
                <label class="flex items-center gap-1" style="cursor:pointer;font-size:var(--text-xs)">
                    <input type="checkbox" class="level-filter" value="${lvl}" ${['ERROR','WARN','INFO'].includes(lvl) ? 'checked' : ''}>
                    <span class="badge badge-${lvl.toLowerCase()}">${lvl}</span>
                </label>
            `).join('')}
        </div>
        <button class="btn btn-primary btn-sm" id="filter-apply">Apply</button>
        <button class="btn btn-ghost btn-sm" id="filter-reset">Reset</button>
    </div>`;

    document.getElementById('filter-apply')?.addEventListener('click', () => {
        if (onApply) onApply(getFilters());
    });
    document.getElementById('filter-reset')?.addEventListener('click', () => {
        document.getElementById('filter-time').value = '1h';
        document.getElementById('filter-service').value = '';
        document.querySelectorAll('.level-filter').forEach(cb => { cb.checked = ['ERROR','WARN','INFO'].includes(cb.value); });
        if (onApply) onApply(getFilters());
    });
}

export function getFilters() {
    const timeVal = document.getElementById('filter-time')?.value || '1h';
    const timeMap = { '15m': 15, '1h': 60, '6h': 360, '24h': 1440, '7d': 10080 };
    const mins = timeMap[timeVal] || 60;
    const start = new Date(Date.now() - mins * 60000).toISOString();

    const levels = [];
    document.querySelectorAll('.level-filter:checked').forEach(cb => levels.push(cb.value));

    return {
        service_name: document.getElementById('filter-service')?.value || '',
        levels: levels.join(','),
        start_time: start,
        end_time: new Date().toISOString(),
    };
}
