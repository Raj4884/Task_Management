/**
 * LogSentry - Main Application Entry Point
 * Initializes auth, router, sidebar, and page rendering.
 */
import { api } from './api.js';
import { isAuthenticated, renderLoginPage, logout } from './auth.js';
import { registerRoute, initRouter, getCurrentRoute } from './router.js';
import { renderSidebar, updateActiveNav } from './components/sidebar.js';
import { renderDashboardPage, cleanupDashboard } from './pages/dashboard.js';
import { renderExplorePage } from './pages/explore.js';
import { renderServicesPage } from './pages/services.js';
import { renderAnomaliesPage } from './pages/anomalies.js';
import { renderAlertsPage } from './pages/alerts.js';
import { renderSettingsPage } from './pages/settings.js';

// Configure API client
api.onUnauthorized = () => { logout(); };

// Page cleanup tracking
let currentCleanup = null;

// Register all routes
registerRoute('dashboard', renderDashboardPage);
registerRoute('explore', renderExplorePage);
registerRoute('services', renderServicesPage);
registerRoute('anomalies', renderAnomaliesPage);
registerRoute('alerts', renderAlertsPage);
registerRoute('settings', renderSettingsPage);

// Page render mapping
const PAGE_RENDERERS = {
    dashboard: renderDashboardPage,
    explore: renderExplorePage,
    services: renderServicesPage,
    anomalies: renderAnomaliesPage,
    alerts: renderAlertsPage,
    settings: renderSettingsPage,
};

const PAGE_CLEANUPS = {
    dashboard: cleanupDashboard,
};

function initApp() {
    if (!isAuthenticated()) {
        renderLoginPage(() => {
            initApp();
        });
        return;
    }

    // Render shell
    const app = document.getElementById('app');
    app.innerHTML = `
        <div class="app-layout" id="app-layout">
            <div id="sidebar-area"></div>
            <main class="main-content" id="page-content"></main>
        </div>`;

    renderSidebar(document.getElementById('sidebar-area'));

    // Initialize router
    initRouter(async (route) => {
        // Cleanup previous page
        if (currentCleanup) { currentCleanup(); currentCleanup = null; }

        // Update navigation highlight
        updateActiveNav();

        // Render page
        const contentEl = document.getElementById('page-content');
        const renderer = PAGE_RENDERERS[route];
        
        if (renderer) {
            await renderer(contentEl);
            currentCleanup = PAGE_CLEANUPS[route] || null;
        } else {
            contentEl.innerHTML = `<div class="page-enter"><div class="page-header"><h1>404</h1></div><p class="text-secondary">Page not found.</p></div>`;
        }
    });
}

// Boot
document.addEventListener('DOMContentLoaded', initApp);
