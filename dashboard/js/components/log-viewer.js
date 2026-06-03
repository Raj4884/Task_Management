/** LogSentry - Log Viewer table component */
const LEVEL_CLASSES = { TRACE: 'badge-trace', DEBUG: 'badge-debug', INFO: 'badge-info', WARN: 'badge-warn', ERROR: 'badge-error', FATAL: 'badge-fatal' };

export function renderLogViewer(container, logs, { onPageChange, page = 1, totalPages = 1, total = 0 } = {}) {
    if (!logs || logs.length === 0) {
        container.innerHTML = `<div class="empty-state"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg><p>No logs found. Try adjusting your filters.</p></div>`;
        return;
    }

    container.innerHTML = `
    <div class="log-table-container">
        <table class="table" id="log-table">
            <thead><tr>
                <th style="width:160px">Timestamp</th><th style="width:70px">Level</th>
                <th style="width:140px">Service</th><th>Message</th><th style="width:100px">Host</th>
            </tr></thead>
            <tbody>${logs.map((log, i) => `
                <tr class="${log.level === 'ERROR' ? 'row-error' : log.level === 'FATAL' ? 'row-fatal' : ''}" data-idx="${i}" style="cursor:pointer">
                    <td class="log-timestamp">${formatTime(log.timestamp)}</td>
                    <td><span class="badge ${LEVEL_CLASSES[log.level] || 'badge-info'}">${log.level}</span></td>
                    <td class="truncate" style="max-width:140px">${log.service_name}</td>
                    <td class="log-message">${escapeHtml(log.message)}</td>
                    <td class="text-xs text-muted">${log.host || '-'}</td>
                </tr>
                <tr class="log-detail-row hidden" id="detail-${i}">
                    <td colspan="5">
                        <div class="log-detail">
                            <pre>${escapeHtml(log.message)}</pre>
                            <div class="flex gap-4 mt-2 text-xs text-muted">
                                ${log.trace_id ? `<span>Trace: ${log.trace_id}</span>` : ''}
                                ${log.environment ? `<span>Env: ${log.environment}</span>` : ''}
                                ${log.error_fingerprint ? `<span>Fingerprint: ${log.error_fingerprint}</span>` : ''}
                            </div>
                            ${log.metadata && Object.keys(log.metadata).length ? `<pre class="mt-2" style="font-size:11px;color:var(--text-muted)">${JSON.stringify(log.metadata, null, 2)}</pre>` : ''}
                        </div>
                    </td>
                </tr>
            `).join('')}</tbody>
        </table>
    </div>
    ${totalPages > 1 ? renderPagination(page, totalPages, total) : ''}`;

    // Row expand/collapse
    container.querySelectorAll('#log-table tbody tr[data-idx]').forEach(row => {
        row.addEventListener('click', () => {
            const detail = document.getElementById(`detail-${row.dataset.idx}`);
            if (detail) detail.classList.toggle('hidden');
        });
    });

    // Pagination
    if (onPageChange) {
        container.querySelectorAll('.pagination .btn[data-page]').forEach(btn => {
            btn.addEventListener('click', () => onPageChange(parseInt(btn.dataset.page)));
        });
    }
}

function renderPagination(page, totalPages, total) {
    let pages = [];
    for (let i = Math.max(1, page - 2); i <= Math.min(totalPages, page + 2); i++) pages.push(i);
    return `<div class="pagination">
        <button class="btn btn-sm btn-ghost" data-page="${Math.max(1, page - 1)}" ${page <= 1 ? 'disabled' : ''}>‹</button>
        ${pages.map(p => `<button class="btn btn-sm ${p === page ? 'active' : 'btn-ghost'}" data-page="${p}">${p}</button>`).join('')}
        <button class="btn btn-sm btn-ghost" data-page="${Math.min(totalPages, page + 1)}" ${page >= totalPages ? 'disabled' : ''}>›</button>
        <span class="pagination-info">${total.toLocaleString()} total</span>
    </div>`;
}

function formatTime(ts) {
    if (!ts) return '-';
    const d = new Date(ts);
    return d.toLocaleString('en-US', { month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
}

function escapeHtml(s) {
    if (!s) return '';
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
