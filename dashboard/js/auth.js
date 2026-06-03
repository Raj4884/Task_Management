/**
 * LogSentry - Authentication module
 */
import { api } from './api.js';

export function isAuthenticated() {
    return !!api.getToken();
}

export async function login(username, password) {
    const data = await api.login(username, password);
    if (data && data.access_token) {
        api.setToken(data.access_token);
        if (data.refresh_token) api.setRefreshToken(data.refresh_token);
        return true;
    }
    return false;
}

export async function register(username, email, password) {
    const data = await api.register(username, email, password);
    if (data && data.access_token) {
        api.setToken(data.access_token);
        if (data.refresh_token) api.setRefreshToken(data.refresh_token);
        return true;
    }
    return false;
}

export function logout() {
    api.clearTokens();
    localStorage.removeItem('logsentry_user');
    window.location.hash = '';
    window.location.reload();
}

export function renderLoginPage(onSuccess) {
    const app = document.getElementById('app');
    app.innerHTML = `
    <div class="login-page">
        <div class="login-card">
            <div class="login-logo">
                <div style="width:48px;height:48px;border-radius:12px;background:linear-gradient(135deg,#3b82f6,#06b6d4);display:flex;align-items:center;justify-content:center;margin:0 auto 12px;font-size:24px;color:white;font-weight:700;">◈</div>
                <h1>LogSentry</h1>
                <p>Distributed Log Analysis Platform</p>
            </div>
            <div class="login-tabs">
                <button class="login-tab active" id="tab-login" onclick="document.getElementById('login-form').classList.remove('hidden');document.getElementById('register-form').classList.add('hidden');this.classList.add('active');document.getElementById('tab-register').classList.remove('active');">Sign In</button>
                <button class="login-tab" id="tab-register" onclick="document.getElementById('register-form').classList.remove('hidden');document.getElementById('login-form').classList.add('hidden');this.classList.add('active');document.getElementById('tab-login').classList.remove('active');">Register</button>
            </div>
            <form id="login-form" class="login-form">
                <div class="form-group">
                    <label for="login-username">Username</label>
                    <input type="text" id="login-username" class="input" placeholder="admin" autocomplete="username" required>
                </div>
                <div class="form-group">
                    <label for="login-password">Password</label>
                    <input type="password" id="login-password" class="input" placeholder="••••••••" autocomplete="current-password" required>
                </div>
                <div id="login-error" class="login-error hidden"></div>
                <button type="submit" class="btn btn-primary btn-lg" id="login-btn">Sign In</button>
            </form>
            <form id="register-form" class="login-form hidden">
                <div class="form-group">
                    <label for="reg-username">Username</label>
                    <input type="text" id="reg-username" class="input" placeholder="johndoe" required>
                </div>
                <div class="form-group">
                    <label for="reg-email">Email</label>
                    <input type="email" id="reg-email" class="input" placeholder="john@example.com" required>
                </div>
                <div class="form-group">
                    <label for="reg-password">Password</label>
                    <input type="password" id="reg-password" class="input" placeholder="••••••••" required>
                </div>
                <div id="register-error" class="login-error hidden"></div>
                <button type="submit" class="btn btn-primary btn-lg" id="register-btn">Create Account</button>
            </form>
        </div>
    </div>`;

    document.getElementById('login-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const btn = document.getElementById('login-btn');
        const errEl = document.getElementById('login-error');
        btn.disabled = true; btn.textContent = 'Signing in...';
        errEl.classList.add('hidden');
        try {
            const ok = await login(
                document.getElementById('login-username').value,
                document.getElementById('login-password').value
            );
            if (ok) onSuccess();
            else { errEl.textContent = 'Invalid credentials'; errEl.classList.remove('hidden'); }
        } catch (err) {
            errEl.textContent = err.message; errEl.classList.remove('hidden');
        }
        btn.disabled = false; btn.textContent = 'Sign In';
    });

    document.getElementById('register-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const btn = document.getElementById('register-btn');
        const errEl = document.getElementById('register-error');
        btn.disabled = true; btn.textContent = 'Creating account...';
        errEl.classList.add('hidden');
        try {
            const ok = await register(
                document.getElementById('reg-username').value,
                document.getElementById('reg-email').value,
                document.getElementById('reg-password').value
            );
            if (ok) onSuccess();
            else { errEl.textContent = 'Registration failed'; errEl.classList.remove('hidden'); }
        } catch (err) {
            errEl.textContent = err.message; errEl.classList.remove('hidden');
        }
        btn.disabled = false; btn.textContent = 'Create Account';
    });
}
