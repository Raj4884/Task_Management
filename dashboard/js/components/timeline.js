/** LogSentry - Timeline component (simple) */
export function renderTimeline(container, data) {
    if (!data || data.length === 0) { container.innerHTML = ''; return; }
    container.innerHTML = `<div class="card card-compact"><h3 style="font-size:var(--text-md);margin-bottom:var(--space-3)">Activity Timeline</h3><div style="display:flex;gap:2px;height:40px;align-items:flex-end">${data.map(d => {
        const max = Math.max(...data.map(x => x.value), 1);
        const h = Math.max(4, (d.value / max) * 40);
        return `<div style="flex:1;height:${h}px;background:var(--accent-primary);border-radius:2px 2px 0 0;opacity:0.7" data-tooltip="${d.value} logs"></div>`;
    }).join('')}</div></div>`;
}
