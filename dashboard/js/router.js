/**
 * LogSentry - Hash-based SPA Router
 */
const routes = {};
let currentPage = null;

export function registerRoute(path, handler) { routes[path] = handler; }

export function navigate(path) { window.location.hash = path; }

export function getCurrentRoute() {
    return window.location.hash.replace('#', '') || 'dashboard';
}

export function initRouter(onRouteChange) {
    const handleRoute = () => {
        const route = getCurrentRoute();
        if (routes[route]) {
            currentPage = route;
            onRouteChange(route);
        } else if (routes['dashboard']) {
            currentPage = 'dashboard';
            onRouteChange('dashboard');
        }
    };
    window.addEventListener('hashchange', handleRoute);
    handleRoute();
}
