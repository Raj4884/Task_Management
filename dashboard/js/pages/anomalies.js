/** LogSentry - Anomalies Page */
import { api } from '../api.js';
import { renderAnomalyPanel } from '../components/anomaly-panel.js';

export async function renderAnomaliesPage(container) {
    container.innerHTML = `
    <div class="page-enter">
        <div class="page-header"><h1>Anomaly Detection</h1>
            <div class="page-header-actions">
                <button class="btn btn-sm btn-primary" id="retrain-btn">🤖 Retrain Models</button>
            </div>
        </div>
        <div id="model-status-area" class="mb-6"></div>
        <div id="anomalies-list-area"><div class="skeleton skeleton-chart"></div></div>
    </div>`;

    document.getElementById('retrain-btn')?.addEventListener('click', async () => {
        const btn = document.getElementById('retrain-btn');
        btn.disabled = true; btn.textContent = 'Training...';
        try { await api.trainModels(); btn.textContent = '✅ Training Complete'; } catch(e) { btn.textContent = '❌ Failed'; }
        setTimeout(() => { btn.disabled = false; btn.textContent = '🤖 Retrain Models'; }, 3000);
    });

    try {
        const [anomalies, modelStatus] = await Promise.all([api.getAnomalies({ limit: 20 }), api.getModelStatus()]);
        renderAnomalyPanel(document.getElementById('anomalies-list-area'), Array.isArray(anomalies) ? anomalies : []);

        if (modelStatus) {
            const ms = document.getElementById('model-status-area');
            ms.innerHTML = `<div class="card card-compact flex gap-6 items-center" style="flex-wrap:wrap">
                <div><span class="text-xs text-muted">Isolation Forest</span><br><span class="badge ${modelStatus.isolation_forest?.is_trained ? 'badge-success' : 'badge-warn'}">${modelStatus.isolation_forest?.is_trained ? 'Trained' : 'Untrained'}</span></div>
                <div><span class="text-xs text-muted">Pattern Detector</span><br><span class="badge ${modelStatus.pattern_detector?.trained ? 'badge-success' : 'badge-warn'}">${modelStatus.pattern_detector?.trained ? 'Trained' : 'Untrained'}</span></div>
                <div><span class="text-xs text-muted">Last Trained</span><br><span class="text-sm">${modelStatus.last_trained ? new Date(modelStatus.last_trained).toLocaleString() : 'Never'}</span></div>
            </div>`;
        }
    } catch(e) {
        document.getElementById('anomalies-list-area').innerHTML = '<div class="empty-state"><p>Unable to load anomalies</p></div>';
    }
}
