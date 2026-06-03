/**
 * LogSentry - Sidebar component
 */
import { getCurrentRoute, navigate } from '../router.js';
import { logout } from '../auth.js';

const NAV_ITEMS = [
    { id: 'dashboard', label: 'Dashboard', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>' },
    { id: 'explore', label: 'Log Explorer', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>' },
    { id: 'services', label: 'Services', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="8" rx="2"/><rect x="2" y="14" width="20" height="8" rx="2"/><circle cx="6" cy="6" r="1" fill="currentColor"/><circle cx="6" cy="18" r="1" fill="currentColor"/></svg>' },
    { id: 'anomalies', label: 'Anomalies', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><circle cx="12" cy="17" r="1" fill="currentColor"/></svg>' },
    { id: 'alerts', label: 'Alerts', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 01-3.46 0"/></svg>' },
    { id: 'settings', label: 'Settings', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/></svg>' },
];

export function renderSidebar(container) {
    const current = getCurrentRoute();
    const user = JSON.parse(localStorage.getItem('logsentry_user') || '{"username":"admin","role":"admin"}');
    const initial = (user.username || 'A')[0].toUpperCase();

    container.innerHTML = `
    <aside class="sidebar" id="sidebar">
        <div class="sidebar-header">
            <div class="sidebar-logo">◈</div>
            <span class="sidebar-brand">LogSentry</span>
            <button class="sidebar-toggle" id="sidebar-toggle" aria-label="Toggle sidebar">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
            </button>
        </div>
        <nav class="sidebar-nav">
            ${NAV_ITEMS.map(item => `
                <button class="sidebar-nav-item ${current === item.id ? 'active' : ''}" data-route="${item.id}">
                    ${item.icon}
                    <span class="sidebar-nav-label">${item.label}</span>
                </button>
            `).join('')}
        </nav>
        <div class="sidebar-footer">
            <div class="sidebar-avatar">${initial}</div>
            <div class="sidebar-footer-info">
                <div class="sidebar-footer-name">${user.username}</div>
                <div class="sidebar-footer-role">${user.role}</div>
            </div>
            <button class="btn btn-ghost btn-icon" id="logout-btn" data-tooltip="Logout">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
            </button>
        </div>
    </aside>`;

    // Navigation
    container.querySelectorAll('.sidebar-nav-item').forEach(btn => {
        btn.addEventListener('click', () => navigate(btn.dataset.route));
    });

    // Toggle
    document.getElementById('sidebar-toggle')?.addEventListener('click', () => {
        document.querySelector('.app-layout')?.classList.toggle('sidebar-collapsed');
    });

    // Logout
    document.getElementById('logout-btn')?.addEventListener('click', logout);
}

export function updateActiveNav() {
    const current = getCurrentRoute();
    document.querySelectorAll('.sidebar-nav-item').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.route === current);
    });
}
