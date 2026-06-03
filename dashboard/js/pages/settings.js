/** LogSentry - Settings Page */
export async function renderSettingsPage(container) {
    const user = JSON.parse(localStorage.getItem('logsentry_user') || '{"username":"admin","email":"admin@logsentry.io","role":"admin"}');
    container.innerHTML = `
    <div class="page-enter">
        <div class="page-header"><h1>Settings</h1></div>
        <div class="card mb-6" style="max-width:600px">
            <h3 class="mb-4">Profile</h3>
            <div class="form-group mb-4"><label>Username</label><input class="input" value="${user.username}" disabled></div>
            <div class="form-group mb-4"><label>Email</label><input class="input" value="${user.email || ''}" disabled></div>
            <div class="form-group mb-4"><label>Role</label><span class="badge badge-info">${user.role}</span></div>
        </div>
        <div class="card" style="max-width:600px">
            <h3 class="mb-4">About LogSentry</h3>
            <div class="text-sm text-secondary">
                <p><strong>Version:</strong> 1.0.0</p>
                <p><strong>Architecture:</strong> Microservices (FastAPI + PostgreSQL + Redis)</p>
                <p><strong>ML Models:</strong> Isolation Forest, Statistical Detection, Pattern Analysis</p>
                <p class="mt-4 text-muted">Enterprise-grade distributed log analysis platform with real-time monitoring and ML-powered anomaly detection.</p>
            </div>
        </div>
    </div>`;
}
