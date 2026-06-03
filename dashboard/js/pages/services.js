/** LogSentry - Services Page */
import { api } from '../api.js';
import { renderServiceMap } from '../components/service-map.js';
import { createAreaChart } from '../components/chart.js';

export async function renderServicesPage(container) {
    container.innerHTML = `
    <div class="page-enter">
        <div class="page-header"><h1>Services</h1></div>
        <div id="services-grid-area"><div class="services-grid">${'<div class="skeleton skeleton-card" style="height:120px"></div>'.repeat(6)}</div></div>
        <div id="service-detail-area" class="mt-6 hidden"></div>
    </div>`;

    try {
        const services = await api.getServices();
        renderServiceMap(document.getElementById('services-grid-area'), services || []);
    } catch(e) {
        document.getElementById('services-grid-area').innerHTML = '<div class="empty-state"><p>Unable to load services</p></div>';
    }
}
