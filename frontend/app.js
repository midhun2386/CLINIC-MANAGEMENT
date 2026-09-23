/* ════════════════════════════════════════════════════════════════════
   Clinic EMR — Frontend Application (Blueprint v2)
   Single-file SPA with hash-based routing, JWT auth, role guards,
   approval workflow for staff, and TreatmentEntry-based data model.
   ════════════════════════════════════════════════════════════════════ */

(() => {
'use strict';

// ── Constants ───────────────────────────────────────────────────────
const API = '';  // Same-origin; change to e.g. 'http://localhost:5000' if needed
const TOKEN_KEY = 'emr_token';
const USER_KEY  = 'emr_user';

// ── State ───────────────────────────────────────────────────────────
let currentUser = null;
let currentToken = null;

// ════════════════════════════════════════════════════════════════════
//  UTILITIES
// ════════════════════════════════════════════════════════════════════

function $(sel, parent = document) { return parent.querySelector(sel); }
function $$(sel, parent = document) { return [...parent.querySelectorAll(sel)]; }

async function api(path, opts = {}) {
    const headers = { 'Content-Type': 'application/json' };
    if (currentToken) headers['Authorization'] = `Bearer ${currentToken}`;
    const res = await fetch(`${API}${path}`, { ...opts, headers: { ...headers, ...(opts.headers || {}) } });
    if (res.status === 401) { logout(); return null; }
    if (res.headers.get('content-type')?.includes('application/json')) {
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Request failed');
        return data;
    }
    if (!res.ok) throw new Error('Request failed');
    return res;
}

// Multipart API for file uploads
async function apiMultipart(path, formData) {
    const headers = {};
    if (currentToken) headers['Authorization'] = `Bearer ${currentToken}`;
    const res = await fetch(`${API}${path}`, { method: 'POST', headers, body: formData });
    if (res.status === 401) { logout(); return null; }
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Upload failed');
    return data;
}

function toast(msg, type = 'info') {
    const container = $('#toast-container');
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.textContent = msg;
    container.appendChild(el);
    setTimeout(() => { el.style.opacity = '0'; setTimeout(() => el.remove(), 300); }, 3500);
}

function formatDate(d) {
    if (!d) return '—';
    const date = new Date(d);
    return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
}

function initials(name) {
    if (!name) return '?';
    return name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
}

function escapeHtml(str) {
    if (!str) return '';
    const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
    return str.replace(/[&<>"']/g, m => map[m]);
}

function roleBadge(role) {
    return `<span class="badge badge-${role}">${role}</span>`;
}

function hasRole(...roles) {
    return currentUser && roles.includes(currentUser.role);
}

function isAdmin() {
    return hasRole('admin');
}

function isStaff() {
    return hasRole('staff');
}

function formatCurrency(amount) {
    if (amount === null || amount === undefined || amount === '') return '—';
    return `₹${Number(amount).toLocaleString('en-IN')}`;
}

// ════════════════════════════════════════════════════════════════════
//  AUTH
// ════════════════════════════════════════════════════════════════════

function loadSession() {
    currentToken = localStorage.getItem(TOKEN_KEY);
    const u = localStorage.getItem(USER_KEY);
    if (u) { try { currentUser = JSON.parse(u); } catch { currentUser = null; } }
    if (currentToken && currentUser) return true;
    currentToken = null; currentUser = null;
    return false;
}

function saveSession(token, user) {
    currentToken = token;
    currentUser = user;
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
}

function logout() {
    // Fire-and-forget logout call
    if (currentToken) api('/api/auth/logout', { method: 'POST' }).catch(() => {});
    currentToken = null;
    currentUser = null;
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    showLogin();
}

function showLogin() {
    $('#login-screen').style.display = '';
    $('#app-shell').style.display = 'none';
    $('#login-email').value = '';
    $('#login-password').value = '';
    $('#login-error').style.display = 'none';
}

function showApp() {
    $('#login-screen').style.display = 'none';
    $('#app-shell').style.display = 'flex';

    // Update user badge
    $('#user-name').textContent = currentUser.name;
    $('#user-role').textContent = currentUser.role;
    $('#user-avatar').textContent = initials(currentUser.name);

    // Role-based nav visibility
    $$('.nav-item[data-roles]').forEach(el => {
        const roles = el.dataset.roles.split(',');
        el.style.display = roles.includes(currentUser.role) ? '' : 'none';
    });

    // Load pending approval count for admin
    if (isAdmin()) {
        updateApprovalBadge();
    }

    route();
}

async function updateApprovalBadge() {
    try {
        const data = await api('/api/requests?status=pending');
        const count = data?.requests?.length || 0;
        const badge = $('#approval-badge');
        if (badge) {
            badge.textContent = count;
            badge.style.display = count > 0 ? '' : 'none';
        }
    } catch {}
}

// Login form
$('#login-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = $('#login-email').value.trim();
    const password = $('#login-password').value;
    const errorEl = $('#login-error');
    const btn = $('#login-btn');

    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span>';

    try {
        const data = await api('/api/auth/login', {
            method: 'POST',
            body: JSON.stringify({ email, password }),
        });
        if (!data) throw new Error('Login failed');
        saveSession(data.token, data.user);
        showApp();
    } catch (err) {
        errorEl.textContent = err.message;
        errorEl.style.display = 'block';
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<span>Sign In</span><svg class="btn-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M12 5l7 7-7 7"/></svg>';
    }
});

$('#logout-btn').addEventListener('click', logout);

// ════════════════════════════════════════════════════════════════════
//  ROUTER
// ════════════════════════════════════════════════════════════════════

const pages = {};

function registerPage(name, render) { pages[name] = render; }

function route() {
    const hash = location.hash.replace('#', '') || 'dashboard';
    const [page, ...params] = hash.split('/');

    // Guard admin pages
    if ((page === 'admin' || page === 'approvals') && !isAdmin()) {
        location.hash = '#dashboard';
        return;
    }

    // Update nav active state
    $$('.nav-item').forEach(el => {
        el.classList.toggle('active', el.dataset.page === page);
    });

    const main = $('#main-content');
    main.innerHTML = '<div class="loading-overlay"><div class="spinner"></div></div>';

    if (pages[page]) {
        pages[page](main, ...params);
    } else {
        main.innerHTML = '<div class="empty-state"><p>Page not found</p></div>';
    }
}

window.addEventListener('hashchange', () => {
    if (currentUser) route();
});

// ════════════════════════════════════════════════════════════════════
//  SIDEBAR (mobile)
// ════════════════════════════════════════════════════════════════════

$('#sidebar-toggle').addEventListener('click', () => {
    $('#sidebar').classList.add('open');
    $('#sidebar-overlay').classList.add('active');
});
$('#sidebar-close').addEventListener('click', closeSidebar);
$('#sidebar-overlay').addEventListener('click', closeSidebar);

function closeSidebar() {
    $('#sidebar').classList.remove('open');
    $('#sidebar-overlay').classList.remove('active');
}

// Close sidebar on nav click (mobile)
$$('.nav-item').forEach(el => el.addEventListener('click', closeSidebar));

// ════════════════════════════════════════════════════════════════════
//  MODAL
// ════════════════════════════════════════════════════════════════════

function openModal(title, bodyHtml) {
    $('#modal-title').textContent = title;
    $('#modal-body').innerHTML = bodyHtml;
    $('#modal-overlay').style.display = '';
}

function closeModal() {
    $('#modal-overlay').style.display = 'none';
}

$('#modal-close').addEventListener('click', closeModal);
$('#modal-overlay').addEventListener('click', (e) => {
    if (e.target === e.currentTarget) closeModal();
});

// ════════════════════════════════════════════════════════════════════
//  CHAT WIDGET
// ════════════════════════════════════════════════════════════════════

$('#chat-toggle').addEventListener('click', () => {
    const panel = $('#chat-panel');
    panel.style.display = panel.style.display === 'none' ? 'flex' : 'none';
});
$('#chat-close').addEventListener('click', () => {
    $('#chat-panel').style.display = 'none';
});

$('#chat-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const input = $('#chat-input');
    const msg = input.value.trim();
    if (!msg) return;
    input.value = '';

    addChatMessage(msg, 'user');

    try {
        const data = await api('/api/chatbot', {
            method: 'POST',
            body: JSON.stringify({ message: msg }),
        });
        if (!data) return;

        // The AI response is in data.message — render with markdown-like formatting
        let html = escapeHtml(data.message)
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\n/g, '<br>');

        addChatMessage(html, 'bot', true);
    } catch (err) {
        addChatMessage('Sorry, something went wrong. Please try again.', 'bot');
    }
});

function addChatMessage(content, who, isHtml = false) {
    const container = $('#chat-messages');
    const div = document.createElement('div');
    div.className = `chat-msg ${who}`;
    const bubble = document.createElement('div');
    bubble.className = 'chat-bubble';
    if (isHtml) bubble.innerHTML = content;
    else bubble.textContent = content;
    div.appendChild(bubble);
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

// ════════════════════════════════════════════════════════════════════
//  PAGE: DASHBOARD
// ════════════════════════════════════════════════════════════════════

registerPage('dashboard', async (main) => {
    let patientsCount = 0, entriesCount = 0, usersCount = 0, pendingApprovals = 0;

    try {
        const pData = await api('/api/patients');
        if (pData) {
            patientsCount = pData.patients.length;
            // Count total treatment entries
            pData.patients.forEach(p => {
                entriesCount += (p.treatment_entries || []).length;
            });
        }
    } catch {}

    if (isAdmin()) {
        try {
            const uData = await api('/api/admin/users');
            if (uData) usersCount = uData.users.length;
        } catch {}
        try {
            const aData = await api('/api/requests?status=pending');
            if (aData) pendingApprovals = aData.requests.length;
        } catch {}
    }

    main.innerHTML = `
        <div class="animate-in">
            <div class="page-header">
                <div>
                    <h1>Welcome back, ${escapeHtml(currentUser.name)}</h1>
                    <p>Here's an overview of your clinic's activity</p>
                </div>
            </div>

            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-icon indigo">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
                    </div>
                    <div class="stat-value">${patientsCount}</div>
                    <div class="stat-label">Total Patients</div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon green">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                    </div>
                    <div class="stat-value">${entriesCount}</div>
                    <div class="stat-label">Treatment Entries</div>
                </div>
                ${isAdmin() ? `
                <div class="stat-card">
                    <div class="stat-icon amber">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
                    </div>
                    <div class="stat-value">${usersCount}</div>
                    <div class="stat-label">Staff Accounts</div>
                </div>
                ${pendingApprovals > 0 ? `
                <div class="stat-card stat-card-highlight">
                    <div class="stat-icon orange">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>
                    </div>
                    <div class="stat-value">${pendingApprovals}</div>
                    <div class="stat-label">Pending Approvals</div>
                </div>` : ''}` : ''}
                <div class="stat-card">
                    <div class="stat-icon blue">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                    </div>
                    <div class="stat-value">${new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</div>
                    <div class="stat-label">Today</div>
                </div>
            </div>

            <div class="card">
                <div class="card-header">
                    <h2>Quick Actions</h2>
                </div>
                <div class="card-body">
                    <div class="btn-group">
                        <a href="#patients" class="btn btn-primary">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="16" height="16"><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="8.5" cy="7" r="4"/><line x1="20" y1="8" x2="20" y2="14"/><line x1="23" y1="11" x2="17" y2="11"/></svg>
                            Register Patient
                        </a>
                        <a href="#search" class="btn btn-secondary">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="16" height="16"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                            Search Records
                        </a>
                        <a href="#export" class="btn btn-secondary">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="16" height="16"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                            Export Data
                        </a>
                        ${isAdmin() ? `
                        <a href="#approvals" class="btn btn-secondary">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="16" height="16"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>
                            Approval Queue
                        </a>
                        <a href="#admin" class="btn btn-secondary">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="16" height="16"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33"/></svg>
                            Admin Panel
                        </a>` : ''}
                    </div>
                </div>
            </div>
        </div>
    `;
});

// ════════════════════════════════════════════════════════════════════
//  PAGE: PATIENTS
// ════════════════════════════════════════════════════════════════════

registerPage('patients', async (main, patientId) => {
    if (patientId) {
        renderPatientDetail(main, patientId);
        return;
    }

    let patients = [];
    try {
        const data = await api('/api/patients');
        patients = data?.patients || [];
    } catch (err) {
        toast(err.message, 'error');
    }

    main.innerHTML = `
        <div class="animate-in">
            <div class="page-header">
                <div>
                    <h1>Patients</h1>
                    <p>Manage patient registrations and demographics</p>
                </div>
                <div class="flex items-center" style="gap:var(--space-3);flex-wrap:wrap;">
                    <div class="btn-group">
                        <button class="btn btn-secondary btn-sm" id="btn-export-patients-xlsx" title="Export Patients to Excel">📊 Excel</button>
                        <button class="btn btn-secondary btn-sm" id="btn-export-patients-pdf" title="Export Patients to PDF">📄 PDF</button>
                        <button class="btn btn-secondary btn-sm" id="btn-export-patients-docx" title="Export Patients to Word">📝 Word</button>
                    </div>
                    <button class="btn btn-primary" id="btn-register-patient">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                        Register Patient
                    </button>
                </div>
            </div>

            <div class="card">
                <div class="card-header">
                    <h2>Patient List</h2>
                    <div class="search-bar" style="max-width:300px;">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                        <input type="text" id="patient-search" placeholder="Search patients…">
                    </div>
                </div>
                <div class="table-wrapper">
                    <table>
                        <thead>
                            <tr>
                                <th>Name</th>
                                <th>DOB</th>
                                <th>Gender</th>
                                <th>Phone</th>
                                <th>Email</th>
                                <th>Registered</th>
                                <th></th>
                            </tr>
                        </thead>
                        <tbody id="patients-tbody"></tbody>
                    </table>
                </div>
                <div id="patients-empty" class="empty-state" style="display:none;">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/></svg>
                    <p>No patients found</p>
                </div>
            </div>
        </div>
    `;

    const tbody = $('#patients-tbody');
    const emptyEl = $('#patients-empty');

    function renderPatients(list) {
        if (list.length === 0) {
            tbody.innerHTML = '';
            emptyEl.style.display = '';
            return;
        }
        emptyEl.style.display = 'none';
        tbody.innerHTML = list.map(p => `
            <tr class="clickable" data-id="${p.id}">
                <td><strong>${escapeHtml(p.name)}</strong></td>
                <td>${formatDate(p.dob)}</td>
                <td>${escapeHtml(p.gender || '—')}</td>
                <td>${escapeHtml(p.phone || '—')}</td>
                <td>${escapeHtml(p.email || '—')}</td>
                <td>${formatDate(p.created_at)}</td>
                <td>
                    <a href="#patients/${p.id}" class="btn btn-ghost btn-sm">View →</a>
                </td>
            </tr>
        `).join('');

        // Row click
        $$('tr[data-id]', tbody).forEach(row => {
            row.addEventListener('click', (e) => {
                if (e.target.closest('a,button')) return;
                location.hash = `#patients/${row.dataset.id}`;
            });
        });
    }

    renderPatients(patients);

    // Live search
    $('#patient-search').addEventListener('input', async (e) => {
        const q = e.target.value.trim();
        try {
            const data = await api(`/api/patients?q=${encodeURIComponent(q)}`);
            renderPatients(data?.patients || []);
        } catch {}
    });

    // Export buttons
    $('#btn-export-patients-xlsx')?.addEventListener('click', () => doExport('xlsx', { export_type: 'patients' }));
    $('#btn-export-patients-pdf')?.addEventListener('click', () => doExport('pdf', { export_type: 'patients' }));
    $('#btn-export-patients-docx')?.addEventListener('click', () => doExport('docx', { export_type: 'patients' }));

    // Register button
    $('#btn-register-patient').addEventListener('click', () => {
        openModal('Register New Patient', `
            <form id="form-register-patient">
                <div class="input-group">
                    <label for="rp-name">Full Name *</label>
                    <input type="text" id="rp-name" required placeholder="Patient full name">
                </div>
                <div class="input-row">
                    <div class="input-group">
                        <label for="rp-dob">Date of Birth *</label>
                        <input type="date" id="rp-dob" required>
                    </div>
                    <div class="input-group">
                        <label for="rp-gender">Gender *</label>
                        <select id="rp-gender" required>
                            <option value="">Select…</option>
                            <option value="Male">Male</option>
                            <option value="Female">Female</option>
                            <option value="Other">Other</option>
                        </select>
                    </div>
                </div>
                <div class="input-group">
                    <label for="rp-phone">Phone Number *</label>
                    <input type="tel" id="rp-phone" required placeholder="+91-9876543210">
                </div>
                <div class="input-group">
                    <label for="rp-email">Email (optional)</label>
                    <input type="email" id="rp-email" placeholder="patient@email.com">
                </div>
                <div class="input-group">
                    <label for="rp-additional-phone">Additional Phone (optional)</label>
                    <input type="tel" id="rp-additional-phone" placeholder="Alternate contact">
                </div>
                <div class="input-group">
                    <label for="rp-address">Address (optional)</label>
                    <textarea id="rp-address" placeholder="Patient address"></textarea>
                </div>
                <div id="rp-error" class="error-msg" style="display:none;"></div>
                <button type="submit" class="btn btn-primary btn-full mt-4">Register Patient</button>
            </form>
        `);

        $('#form-register-patient').addEventListener('submit', async (e) => {
            e.preventDefault();
            const body = {
                name: $('#rp-name').value.trim(),
                dob: $('#rp-dob').value || null,
                gender: $('#rp-gender').value || null,
                phone: $('#rp-phone').value.trim() || null,
                email: $('#rp-email').value.trim() || null,
                additional_phone: $('#rp-additional-phone').value.trim() || null,
                address: $('#rp-address').value.trim() || null,
            };
            try {
                await api('/api/patients', { method: 'POST', body: JSON.stringify(body) });
                closeModal();
                toast('Patient registered successfully!', 'success');
                route(); // Refresh
            } catch (err) {
                const errEl = $('#rp-error');
                errEl.textContent = err.message;
                errEl.style.display = '';
            }
        });
    });
});

// ── Patient Detail ──────────────────────────────────────────────────

async function renderPatientDetail(main, id) {
    let patient;
    try {
        const data = await api(`/api/patients/${id}`);
        patient = data?.patient;
    } catch (err) {
        main.innerHTML = `<div class="empty-state"><p>Patient not found</p></div>`;
        return;
    }

    const entries = patient.treatment_entries || [];
    let entriesHtml = '';
    if (entries.length > 0) {
        entriesHtml = `
            <div class="table-wrapper">
                <table>
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>Date</th>
                            <th>Treatment</th>
                            <th>Medicine</th>
                            <th>Remark</th>
                            <th>Next Visit</th>
                            <th>Payment</th>
                            <th></th>
                        </tr>
                    </thead>
                    <tbody>
                        ${entries.map(e => `
                            <tr>
                                <td><strong>${e.consultation_number}</strong></td>
                                <td>${formatDate(e.date_of_treatment)}</td>
                                <td>${escapeHtml(e.treatment_name || '—')}</td>
                                <td class="truncate" style="max-width:160px;" title="${escapeHtml(e.medicine || '')}">${escapeHtml(e.medicine || '—')}</td>
                                <td class="truncate" style="max-width:160px;" title="${escapeHtml(e.remark || '')}">${escapeHtml(e.remark || '—')}</td>
                                <td>${formatDate(e.next_consultation)}</td>
                                <td>${formatCurrency(e.payment)}${e.payment_method ? ` <span class="badge badge-tag">${escapeHtml(e.payment_method)}</span>` : ''}</td>
                                <td>
                                    <div class="btn-group">
                                        <button class="btn btn-ghost btn-sm btn-edit-record" data-record='${escapeHtml(JSON.stringify(e))}'>${isAdmin() ? 'Edit' : 'Request Edit'}</button>
                                        <button class="btn btn-ghost btn-sm btn-delete-record" data-record-id="${e.id}" data-record-name="${escapeHtml(e.treatment_name || 'entry')}">${isAdmin() ? 'Delete' : 'Request Delete'}</button>
                                    </div>
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    } else {
        entriesHtml = '<div class="empty-state"><p>No treatment entries yet</p></div>';
    }

    const photoHtml = patient.photo_url
        ? `<img src="${patient.photo_url}" class="patient-photo" alt="Patient photo">`
        : `<div class="patient-avatar-lg">${initials(patient.name)}</div>`;

    main.innerHTML = `
        <div class="animate-in">
            <div class="page-header">
                <a href="#patients" class="btn btn-ghost btn-sm">← Back to Patients</a>
                <div class="btn-group">
                    <button class="btn btn-secondary btn-sm" id="btn-edit-patient">${isAdmin() ? '✏️ Edit Patient' : '✏️ Request Edit'}</button>
                    <button class="btn btn-secondary btn-sm" id="btn-export-pat-detail-xlsx" title="Export to Excel">📊 Excel</button>
                    <button class="btn btn-secondary btn-sm" id="btn-export-pat-detail-pdf" title="Export to PDF">📄 PDF</button>
                    <button class="btn btn-secondary btn-sm" id="btn-export-pat-detail-docx" title="Export to Word">📝 Word</button>
                    <button class="btn btn-danger btn-sm" id="btn-delete-patient">${isAdmin() ? 'Delete Patient' : 'Request Delete'}</button>
                </div>
            </div>

            <div class="patient-detail-header">
                ${photoHtml}
                <div>
                    <h1>${escapeHtml(patient.name)}</h1>
                    <div class="patient-meta">
                        <span class="patient-meta-item"><strong>DOB:</strong> ${formatDate(patient.dob)}</span>
                        <span class="patient-meta-item"><strong>Gender:</strong> ${escapeHtml(patient.gender || '—')}</span>
                        <span class="patient-meta-item"><strong>Phone:</strong> ${escapeHtml(patient.phone || '—')}</span>
                        ${patient.email ? `<span class="patient-meta-item"><strong>Email:</strong> ${escapeHtml(patient.email)}</span>` : ''}
                        ${patient.additional_phone ? `<span class="patient-meta-item"><strong>Alt Phone:</strong> ${escapeHtml(patient.additional_phone)}</span>` : ''}
                        ${patient.address ? `<span class="patient-meta-item"><strong>Address:</strong> ${escapeHtml(patient.address)}</span>` : ''}
                    </div>
                </div>
            </div>

            <div class="card">
                <div class="card-header">
                    <h2>Treatment Entries (${entries.length})</h2>
                    <button class="btn btn-primary btn-sm" id="btn-add-record">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                        Add Treatment
                    </button>
                </div>
                ${entriesHtml}
            </div>
        </div>
    `;

    // Add record
    $('#btn-add-record')?.addEventListener('click', () => openTreatmentForm(patient.id));

    // Edit record buttons
    $$('.btn-edit-record', main).forEach(btn => {
        btn.addEventListener('click', () => {
            const record = JSON.parse(btn.dataset.record);
            openTreatmentForm(patient.id, record);
        });
    });

    // Delete record buttons
    $$('.btn-delete-record', main).forEach(btn => {
        btn.addEventListener('click', async () => {
            const recordId = btn.dataset.recordId;
            const recordName = btn.dataset.recordName;
            if (!confirm(`Delete treatment entry "${recordName}"? This cannot be undone.`)) return;
            try {
                const result = await api(`/api/records/${recordId}`, { method: 'DELETE' });
                if (result?.approval_request) {
                    toast('Delete request submitted for admin approval', 'info');
                } else {
                    toast('Treatment entry deleted', 'success');
                }
                route();
            } catch (err) {
                toast(err.message, 'error');
            }
        });
    });

    // Edit patient
    $('#btn-edit-patient')?.addEventListener('click', () => {
        openModal('Edit Patient', `
            <form id="form-edit-patient">
                <div class="input-group">
                    <label for="ep-name">Full Name *</label>
                    <input type="text" id="ep-name" required value="${escapeHtml(patient.name)}">
                </div>
                <div class="input-row">
                    <div class="input-group">
                        <label for="ep-dob">Date of Birth *</label>
                        <input type="date" id="ep-dob" required value="${patient.dob || ''}">
                    </div>
                    <div class="input-group">
                        <label for="ep-gender">Gender *</label>
                        <select id="ep-gender" required>
                            <option value="Male" ${patient.gender === 'Male' ? 'selected' : ''}>Male</option>
                            <option value="Female" ${patient.gender === 'Female' ? 'selected' : ''}>Female</option>
                            <option value="Other" ${patient.gender === 'Other' ? 'selected' : ''}>Other</option>
                        </select>
                    </div>
                </div>
                <div class="input-group">
                    <label for="ep-phone">Phone *</label>
                    <input type="tel" id="ep-phone" required value="${escapeHtml(patient.phone || '')}">
                </div>
                <div class="input-group">
                    <label for="ep-email">Email</label>
                    <input type="email" id="ep-email" value="${escapeHtml(patient.email || '')}">
                </div>
                <div class="input-group">
                    <label for="ep-additional-phone">Additional Phone</label>
                    <input type="tel" id="ep-additional-phone" value="${escapeHtml(patient.additional_phone || '')}">
                </div>
                <div class="input-group">
                    <label for="ep-address">Address</label>
                    <textarea id="ep-address">${escapeHtml(patient.address || '')}</textarea>
                </div>
                <div class="input-group">
                    <label for="ep-photo">Photo</label>
                    <input type="file" id="ep-photo" accept="image/*">
                </div>
                <div id="ep-error" class="error-msg" style="display:none;"></div>
                <button type="submit" class="btn btn-primary btn-full mt-4">${isAdmin() ? 'Save Changes' : 'Submit Edit Request'}</button>
            </form>
        `);

        $('#form-edit-patient').addEventListener('submit', async (e) => {
            e.preventDefault();
            const body = {
                name: $('#ep-name').value.trim(),
                dob: $('#ep-dob').value,
                gender: $('#ep-gender').value,
                phone: $('#ep-phone').value.trim(),
                email: $('#ep-email').value.trim(),
                additional_phone: $('#ep-additional-phone').value.trim(),
                address: $('#ep-address').value.trim(),
            };
            try {
                const result = await api(`/api/patients/${id}`, { method: 'PUT', body: JSON.stringify(body) });
                // Handle photo upload
                const photoFile = $('#ep-photo').files[0];
                if (photoFile) {
                    const fd = new FormData();
                    fd.append('photo', photoFile);
                    await apiMultipart(`/api/patients/${id}/photo`, fd);
                }
                if (result?.approval_request) {
                    toast('Edit request submitted for admin approval', 'info');
                } else {
                    toast('Patient updated', 'success');
                }
                closeModal();
                route();
            } catch (err) {
                const errEl = $('#ep-error');
                errEl.textContent = err.message;
                errEl.style.display = '';
            }
        });
    });

    // Export single patient
    $('#btn-export-pat-detail-xlsx')?.addEventListener('click', () => doExport('xlsx', { patient_ids: [patient.id] }));
    $('#btn-export-pat-detail-pdf')?.addEventListener('click', () => doExport('pdf', { patient_ids: [patient.id] }));
    $('#btn-export-pat-detail-docx')?.addEventListener('click', () => doExport('docx', { patient_ids: [patient.id] }));

    // Delete patient
    $('#btn-delete-patient')?.addEventListener('click', async () => {
        if (!confirm(`Delete patient "${patient.name}" and all their treatment entries? This cannot be undone.`)) return;
        try {
            const result = await api(`/api/patients/${id}`, { method: 'DELETE' });
            if (result?.approval_request) {
                toast('Delete request submitted for admin approval', 'info');
                route();
            } else {
                toast('Patient deleted', 'success');
                location.hash = '#patients';
            }
        } catch (err) {
            toast(err.message, 'error');
        }
    });
}

function openTreatmentForm(patientId, record = null) {
    const isEdit = !!record;
    openModal(isEdit ? 'Edit Treatment Entry' : 'Add Treatment Entry', `
        <form id="form-record">
            <div class="input-row">
                <div class="input-group">
                    <label for="rec-date">Date of Treatment *</label>
                    <input type="date" id="rec-date" required value="${record?.date_of_treatment || new Date().toISOString().split('T')[0]}">
                </div>
                <div class="input-group">
                    <label for="rec-consult-num">Consultation # *</label>
                    <input type="number" id="rec-consult-num" min="1" value="${record?.consultation_number || ''}" placeholder="Auto">
                </div>
            </div>
            <div class="input-group">
                <label for="rec-treatment">Treatment Name</label>
                <input type="text" id="rec-treatment" placeholder="e.g. Hypertension Follow-up" value="${escapeHtml(record?.treatment_name || '')}">
            </div>
            <div class="input-group">
                <label for="rec-medicine">Medicine</label>
                <textarea id="rec-medicine" placeholder="Medications and dosages…">${escapeHtml(record?.medicine || '')}</textarea>
            </div>
            <div class="input-group">
                <label for="rec-remark">Remark</label>
                <textarea id="rec-remark" placeholder="Visit notes, observations…">${escapeHtml(record?.remark || '')}</textarea>
            </div>
            <div class="input-group">
                <label for="rec-next">Next Consultation</label>
                <input type="date" id="rec-next" value="${record?.next_consultation || ''}">
            </div>
            <div class="input-row">
                <div class="input-group">
                    <label for="rec-payment">Payment Amount</label>
                    <input type="number" id="rec-payment" step="0.01" min="0" placeholder="0.00" value="${record?.payment ?? ''}">
                </div>
                <div class="input-group">
                    <label for="rec-payment-method">Payment Method</label>
                    <select id="rec-payment-method">
                        <option value="">Select…</option>
                        <option value="Cash" ${record?.payment_method === 'Cash' ? 'selected' : ''}>Cash</option>
                        <option value="Card" ${record?.payment_method === 'Card' ? 'selected' : ''}>Card</option>
                        <option value="UPI" ${record?.payment_method === 'UPI' ? 'selected' : ''}>UPI</option>
                        <option value="Insurance" ${record?.payment_method === 'Insurance' ? 'selected' : ''}>Insurance</option>
                    </select>
                </div>
            </div>
            <div id="rec-error" class="error-msg" style="display:none;"></div>
            <button type="submit" class="btn btn-primary btn-full mt-4">${isEdit ? (isAdmin() ? 'Update Entry' : 'Submit Edit Request') : 'Save Treatment Entry'}</button>
        </form>
    `);

    $('#form-record').addEventListener('submit', async (e) => {
        e.preventDefault();
        const body = {
            date_of_treatment: $('#rec-date').value,
            consultation_number: $('#rec-consult-num').value ? parseInt($('#rec-consult-num').value) : undefined,
            treatment_name: $('#rec-treatment').value.trim(),
            medicine: $('#rec-medicine').value.trim(),
            remark: $('#rec-remark').value.trim(),
            next_consultation: $('#rec-next').value || null,
            payment: $('#rec-payment').value ? parseFloat($('#rec-payment').value) : null,
            payment_method: $('#rec-payment-method').value || null,
        };
        try {
            if (isEdit) {
                const result = await api(`/api/records/${record.id}`, { method: 'PUT', body: JSON.stringify(body) });
                if (result?.approval_request) {
                    toast('Edit request submitted for admin approval', 'info');
                } else {
                    toast('Treatment entry updated', 'success');
                }
            } else {
                await api(`/api/patients/${patientId}/records`, { method: 'POST', body: JSON.stringify(body) });
                toast('Treatment entry added', 'success');
            }
            closeModal();
            route(); // Refresh
        } catch (err) {
            const errEl = $('#rec-error');
            errEl.textContent = err.message;
            errEl.style.display = '';
        }
    });
}

// ════════════════════════════════════════════════════════════════════
//  PAGE: RECORDS (browsable list of all treatment entries)
// ════════════════════════════════════════════════════════════════════

registerPage('records', async (main) => {
    let allRecords = [];
    try {
        const data = await api('/api/patients');
        const patients = data?.patients || [];
        for (const p of patients) {
            if (p.treatment_entries) {
                p.treatment_entries.forEach(e => {
                    e.patient_name = p.name;
                    e.patient_id = p.id;
                    allRecords.push(e);
                });
            }
        }
        allRecords.sort((a, b) => (b.date_of_treatment || '').localeCompare(a.date_of_treatment || ''));
    } catch (err) {
        toast(err.message, 'error');
    }

    main.innerHTML = `
        <div class="animate-in">
            <div class="page-header">
                <div>
                    <h1>Treatment Entries</h1>
                    <p>Browse all treatment records across patients</p>
                </div>
                <div class="btn-group">
                    <button class="btn btn-secondary btn-sm" id="btn-export-records-xlsx" title="Download Excel">📊 Export Excel</button>
                    <button class="btn btn-secondary btn-sm" id="btn-export-records-pdf" title="Download PDF">📄 Export PDF</button>
                    <button class="btn btn-secondary btn-sm" id="btn-export-records-docx" title="Download Word">📝 Export Word</button>
                </div>
            </div>

            <div class="card">
                <div class="card-header">
                    <h2>All Entries (${allRecords.length})</h2>
                </div>
                ${allRecords.length > 0 ? `
                <div class="table-wrapper">
                    <table>
                        <thead>
                            <tr>
                                <th>Patient</th>
                                <th>#</th>
                                <th>Date</th>
                                <th>Treatment</th>
                                <th>Medicine</th>
                                <th>Next Visit</th>
                                <th>Payment</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${allRecords.map(e => `
                                <tr class="clickable" onclick="location.hash='#patients/${e.patient_id}'">
                                    <td><strong>${escapeHtml(e.patient_name)}</strong></td>
                                    <td>${e.consultation_number}</td>
                                    <td>${formatDate(e.date_of_treatment)}</td>
                                    <td>${escapeHtml(e.treatment_name || '—')}</td>
                                    <td class="truncate" style="max-width:180px;">${escapeHtml(e.medicine || '—')}</td>
                                    <td>${formatDate(e.next_consultation)}</td>
                                    <td>${formatCurrency(e.payment)}${e.payment_method ? ` <span class="badge badge-tag">${escapeHtml(e.payment_method)}</span>` : ''}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>` : `
                <div class="empty-state">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                    <p>No treatment entries yet</p>
                </div>`}
            </div>
        </div>
    `;

    // Export buttons
    $('#btn-export-records-xlsx')?.addEventListener('click', () => doExport('xlsx', { export_type: 'records' }));
    $('#btn-export-records-pdf')?.addEventListener('click', () => doExport('pdf', { export_type: 'records' }));
    $('#btn-export-records-docx')?.addEventListener('click', () => doExport('docx', { export_type: 'records' }));
});

// ════════════════════════════════════════════════════════════════════
//  PAGE: SEARCH
// ════════════════════════════════════════════════════════════════════

registerPage('search', async (main) => {
    main.innerHTML = `
        <div class="animate-in">
            <div class="page-header">
                <div>
                    <h1>Search</h1>
                    <p>Find patients and treatment entries by name, treatment, or condition</p>
                </div>
            </div>

            <form id="search-form" class="search-filters">
                <div class="input-group search-main-input">
                    <label for="search-q">Search Query</label>
                    <input type="text" id="search-q" placeholder="Patient name, treatment name, medicine…">
                </div>
                <div class="input-group">
                    <label for="search-from">From</label>
                    <input type="date" id="search-from">
                </div>
                <div class="input-group">
                    <label for="search-to">To</label>
                    <input type="date" id="search-to">
                </div>
                <button type="submit" class="btn btn-primary" style="align-self:flex-end;">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                    Search
                </button>
            </form>

            <div id="search-results"></div>
        </div>
    `;

    const resultsEl = $('#search-results');

    $('#search-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const q = $('#search-q').value.trim();
        const dateFrom = $('#search-from')?.value || '';
        const dateTo = $('#search-to')?.value || '';

        if (!q) { toast('Enter a search query', 'info'); return; }

        resultsEl.innerHTML = '<div class="loading-overlay"><div class="spinner"></div></div>';

        try {
            const params = new URLSearchParams({ q });
            if (dateFrom) params.append('date_from', dateFrom);
            if (dateTo) params.append('date_to', dateTo);

            const data = await api(`/api/search?${params}`);
            renderSearchResults(resultsEl, data, q);
        } catch (err) {
            resultsEl.innerHTML = `<div class="empty-state"><p>Search failed: ${escapeHtml(err.message)}</p></div>`;
        }
    });
});

function renderSearchResults(container, data, query) {
    const patients = data?.patients || [];
    const records = data?.records || [];

    if (patients.length === 0 && records.length === 0) {
        container.innerHTML = `<div class="empty-state"><p>No results found for "${escapeHtml(query)}"</p></div>`;
        return;
    }

    let html = '';

    // Export buttons
    html += `
        <div class="flex items-center justify-between mb-6" style="flex-wrap:wrap;gap:var(--space-3);">
            <span style="color:var(--text-secondary);font-size:var(--font-sm);">
                Found ${patients.length} patient(s) and ${records.length} treatment entry(ies)
            </span>
            <div class="btn-group">
                <button class="btn btn-secondary btn-sm btn-export" data-format="xlsx" data-query="${escapeHtml(query)}">📊 Export Excel</button>
                <button class="btn btn-secondary btn-sm btn-export" data-format="pdf" data-query="${escapeHtml(query)}">📄 Export PDF</button>
                <button class="btn btn-secondary btn-sm btn-export" data-format="docx" data-query="${escapeHtml(query)}">📝 Export Word</button>
            </div>
        </div>
    `;

    if (patients.length > 0) {
        html += `
            <div class="card mb-6">
                <div class="card-header"><h2>Patients (${patients.length})</h2></div>
                <div class="table-wrapper">
                    <table>
                        <thead><tr><th>Name</th><th>DOB</th><th>Gender</th><th>Phone</th><th></th></tr></thead>
                        <tbody>
                            ${patients.map(p => `
                                <tr>
                                    <td><strong>${escapeHtml(p.name)}</strong></td>
                                    <td>${formatDate(p.dob)}</td>
                                    <td>${escapeHtml(p.gender || '—')}</td>
                                    <td>${escapeHtml(p.phone || '—')}</td>
                                    <td><a href="#patients/${p.id}" class="btn btn-ghost btn-sm">View →</a></td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        `;
    }

    if (records.length > 0) {
        html += `
            <div class="card">
                <div class="card-header"><h2>Treatment Entries (${records.length})</h2></div>
                <div class="table-wrapper">
                    <table>
                        <thead><tr><th>Patient</th><th>Date</th><th>Treatment</th><th>Medicine</th><th>Payment</th></tr></thead>
                        <tbody>
                            ${records.map(r => `
                                <tr>
                                    <td><strong>${escapeHtml(r.patient_name || '—')}</strong></td>
                                    <td>${formatDate(r.date_of_treatment)}</td>
                                    <td>${escapeHtml(r.treatment_name || '—')}</td>
                                    <td class="truncate" style="max-width:200px;">${escapeHtml(r.medicine || '—')}</td>
                                    <td>${formatCurrency(r.payment)}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        `;
    }

    container.innerHTML = html;

    // Export buttons
    $$('.btn-export', container).forEach(btn => {
        btn.addEventListener('click', () => doExport(btn.dataset.format, btn.dataset.query));
    });
}

async function doExport(format, payload = {}) {
    try {
        toast(`Generating ${format.toUpperCase()} export…`, 'info');
        const bodyObj = typeof payload === 'string' ? { search_query: payload } : { ...payload };
        bodyObj.format = format;

        const res = await fetch(`${API}/api/export`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${currentToken}`,
            },
            body: JSON.stringify(bodyObj),
        });
        if (!res.ok) {
            const errJson = await res.json().catch(() => ({}));
            throw new Error(errJson.error || 'Export failed');
        }

        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;

        const nowStr = new Date().toISOString().slice(0, 10);
        let prefix = 'clinic_export';
        if (bodyObj.export_type === 'records') prefix = 'treatment_entries';
        else if (bodyObj.export_type === 'patients') prefix = 'patients_list';
        else if (bodyObj.patient_ids && bodyObj.patient_ids.length === 1) prefix = `patient_${bodyObj.patient_ids[0]}_chart`;
        else if (bodyObj.search_query) prefix = `search_${bodyObj.search_query.replace(/[^a-zA-Z0-9]/g, '_')}`;

        a.download = `${prefix}_${nowStr}.${format}`;
        a.click();
        URL.revokeObjectURL(url);
        toast('Export downloaded!', 'success');
    } catch (err) {
        toast(err.message, 'error');
    }
}

// ════════════════════════════════════════════════════════════════════
//  PAGE: EXPORT DATA HUB
// ════════════════════════════════════════════════════════════════════

registerPage('export', async (main) => {
    let patients = [];
    try {
        const data = await api('/api/patients');
        patients = data?.patients || [];
    } catch {}

    main.innerHTML = `
        <div class="animate-in">
            <div class="page-header">
                <div>
                    <h1>Export Data & Reports</h1>
                    <p>Download treatment data, patient lists, and records in Excel, PDF, or Word format</p>
                </div>
            </div>

            <div class="grid-2 mb-6">
                <!-- Card 1: All Treatment Entries -->
                <div class="export-card">
                    <div class="card-header">
                        <h2>📋 Treatment Entries</h2>
                    </div>
                    <div class="export-card-body">
                        <p style="color:var(--text-secondary);font-size:var(--font-sm);margin-bottom:var(--space-4);line-height:1.5;">
                            Export all treatment data with the standardized 8-column format: Name, DOB, Phone, Treatment, Next Consultation, Payment, Payment Method, Gender.
                        </p>
                        <div class="btn-group">
                            <button class="btn btn-primary btn-sm" id="hub-rec-xlsx">📊 Excel (.xlsx)</button>
                            <button class="btn btn-secondary btn-sm" id="hub-rec-pdf">📄 PDF (.pdf)</button>
                            <button class="btn btn-secondary btn-sm" id="hub-rec-docx">📝 Word (.docx)</button>
                        </div>
                    </div>
                </div>

                <!-- Card 2: Patient Directory -->
                <div class="export-card">
                    <div class="card-header">
                        <h2>👥 Patient Directory</h2>
                    </div>
                    <div class="export-card-body">
                        <p style="color:var(--text-secondary);font-size:var(--font-sm);margin-bottom:var(--space-4);line-height:1.5;">
                            Download patient demographics with treatment details using the standardized export format.
                        </p>
                        <div class="btn-group">
                            <button class="btn btn-primary btn-sm" id="hub-pat-xlsx">📊 Excel (.xlsx)</button>
                            <button class="btn btn-secondary btn-sm" id="hub-pat-pdf">📄 PDF (.pdf)</button>
                            <button class="btn btn-secondary btn-sm" id="hub-pat-docx">📝 Word (.docx)</button>
                        </div>
                    </div>
                </div>

                <!-- Card 3: Single Patient -->
                <div class="export-card">
                    <div class="card-header">
                        <h2>👤 Individual Patient</h2>
                    </div>
                    <div class="export-card-body">
                        <p style="color:var(--text-secondary);font-size:var(--font-sm);margin-bottom:var(--space-3);line-height:1.5;">
                            Select a patient to export their complete treatment history:
                        </p>
                        <div class="input-group mb-4">
                            <label for="hub-patient-select">Choose Patient</label>
                            <select id="hub-patient-select">
                                <option value="">Select a patient…</option>
                                ${patients.map(p => `<option value="${p.id}">${escapeHtml(p.name)} (${p.phone || 'No phone'})</option>`).join('')}
                            </select>
                        </div>
                        <div class="btn-group">
                            <button class="btn btn-primary btn-sm" id="hub-single-xlsx">📊 Excel</button>
                            <button class="btn btn-secondary btn-sm" id="hub-single-pdf">📄 PDF</button>
                            <button class="btn btn-secondary btn-sm" id="hub-single-docx">📝 Word</button>
                        </div>
                    </div>
                </div>

                <!-- Card 4: Filtered Export -->
                <div class="export-card">
                    <div class="card-header">
                        <h2>🔍 Filtered Search Export</h2>
                    </div>
                    <div class="export-card-body">
                        <p style="color:var(--text-secondary);font-size:var(--font-sm);margin-bottom:var(--space-3);line-height:1.5;">
                            Export records matching specific treatments, medicines, or date ranges:
                        </p>
                        <div class="input-group mb-3">
                            <label for="hub-filter-q">Keyword / Treatment</label>
                            <input type="text" id="hub-filter-q" placeholder="e.g. diabetes, hypertension">
                        </div>
                        <div class="input-row mb-4">
                            <div class="input-group">
                                <label for="hub-filter-from">From</label>
                                <input type="date" id="hub-filter-from">
                            </div>
                            <div class="input-group">
                                <label for="hub-filter-to">To</label>
                                <input type="date" id="hub-filter-to">
                            </div>
                        </div>
                        <div class="btn-group">
                            <button class="btn btn-primary btn-sm" id="hub-filter-xlsx">📊 Excel</button>
                            <button class="btn btn-secondary btn-sm" id="hub-filter-pdf">📄 PDF</button>
                            <button class="btn btn-secondary btn-sm" id="hub-filter-docx">📝 Word</button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;

    // Event handlers for Hub
    $('#hub-rec-xlsx')?.addEventListener('click', () => doExport('xlsx', { export_type: 'records' }));
    $('#hub-rec-pdf')?.addEventListener('click', () => doExport('pdf', { export_type: 'records' }));
    $('#hub-rec-docx')?.addEventListener('click', () => doExport('docx', { export_type: 'records' }));

    $('#hub-pat-xlsx')?.addEventListener('click', () => doExport('xlsx', { export_type: 'patients' }));
    $('#hub-pat-pdf')?.addEventListener('click', () => doExport('pdf', { export_type: 'patients' }));
    $('#hub-pat-docx')?.addEventListener('click', () => doExport('docx', { export_type: 'patients' }));

    const getSinglePid = () => {
        const val = $('#hub-patient-select')?.value;
        if (!val) { toast('Please select a patient first', 'info'); return null; }
        return parseInt(val, 10);
    };
    $('#hub-single-xlsx')?.addEventListener('click', () => {
        const pid = getSinglePid();
        if (pid) doExport('xlsx', { patient_ids: [pid] });
    });
    $('#hub-single-pdf')?.addEventListener('click', () => {
        const pid = getSinglePid();
        if (pid) doExport('pdf', { patient_ids: [pid] });
    });
    $('#hub-single-docx')?.addEventListener('click', () => {
        const pid = getSinglePid();
        if (pid) doExport('docx', { patient_ids: [pid] });
    });

    const getFilterPayload = () => ({
        search_query: $('#hub-filter-q')?.value.trim() || '',
        date_from: $('#hub-filter-from')?.value || '',
        date_to: $('#hub-filter-to')?.value || '',
    });
    $('#hub-filter-xlsx')?.addEventListener('click', () => doExport('xlsx', getFilterPayload()));
    $('#hub-filter-pdf')?.addEventListener('click', () => doExport('pdf', getFilterPayload()));
    $('#hub-filter-docx')?.addEventListener('click', () => doExport('docx', getFilterPayload()));
});

// ════════════════════════════════════════════════════════════════════
//  PAGE: APPROVALS (Admin only)
// ════════════════════════════════════════════════════════════════════

registerPage('approvals', async (main) => {
    if (!isAdmin()) { location.hash = '#dashboard'; return; }

    let requests = [];
    try {
        const data = await api('/api/requests');
        requests = data?.requests || [];
    } catch (err) {
        toast(err.message, 'error');
    }

    const pending = requests.filter(r => r.status === 'PENDING');
    const reviewed = requests.filter(r => r.status !== 'PENDING');

    function statusBadge(status) {
        const cls = status === 'PENDING' ? 'badge-pending' : status === 'APPROVED' ? 'badge-approved' : 'badge-rejected';
        return `<span class="badge ${cls}">${status}</span>`;
    }

    function actionBadge(action) {
        return `<span class="badge ${action === 'EDIT' ? 'badge-tag' : 'badge-danger'}">${action}</span>`;
    }

    main.innerHTML = `
        <div class="animate-in">
            <div class="page-header">
                <div>
                    <h1>Approval Queue</h1>
                    <p>Review and approve/reject staff edit and delete requests</p>
                </div>
            </div>

            <div class="card mb-6">
                <div class="card-header">
                    <h2>Pending Requests (${pending.length})</h2>
                </div>
                ${pending.length > 0 ? `
                <div class="table-wrapper">
                    <table>
                        <thead>
                            <tr>
                                <th>Requested By</th>
                                <th>Action</th>
                                <th>Target</th>
                                <th>Details</th>
                                <th>Submitted</th>
                                <th></th>
                            </tr>
                        </thead>
                        <tbody>
                            ${pending.map(r => `
                                <tr>
                                    <td><strong>${escapeHtml(r.requester_name || 'Unknown')}</strong></td>
                                    <td>${actionBadge(r.action_type)}</td>
                                    <td>${escapeHtml(r.target_type)} — ${escapeHtml(r.target_name || `#${r.target_id}`)}</td>
                                    <td class="truncate" style="max-width:200px;" title="${r.proposed_changes ? escapeHtml(JSON.stringify(r.proposed_changes)) : 'Delete request'}">${r.action_type === 'EDIT' ? 'See changes…' : 'Delete request'}</td>
                                    <td>${formatDate(r.created_at)}</td>
                                    <td>
                                        <div class="btn-group">
                                            ${r.action_type === 'EDIT' ? `<button class="btn btn-ghost btn-sm btn-view-changes" data-changes='${escapeHtml(JSON.stringify(r.proposed_changes || {}))}'>View</button>` : ''}
                                            <button class="btn btn-primary btn-sm btn-approve" data-id="${r.id}">Approve</button>
                                            <button class="btn btn-danger btn-sm btn-reject" data-id="${r.id}">Reject</button>
                                        </div>
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>` : `
                <div class="empty-state">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>
                    <p>No pending requests — all caught up!</p>
                </div>`}
            </div>

            ${reviewed.length > 0 ? `
            <div class="card">
                <div class="card-header">
                    <h2>Review History (${reviewed.length})</h2>
                </div>
                <div class="table-wrapper">
                    <table>
                        <thead>
                            <tr>
                                <th>Requested By</th>
                                <th>Action</th>
                                <th>Target</th>
                                <th>Status</th>
                                <th>Reviewed By</th>
                                <th>Date</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${reviewed.map(r => `
                                <tr>
                                    <td>${escapeHtml(r.requester_name || 'Unknown')}</td>
                                    <td>${actionBadge(r.action_type)}</td>
                                    <td>${escapeHtml(r.target_type)} — ${escapeHtml(r.target_name || `#${r.target_id}`)}</td>
                                    <td>${statusBadge(r.status)}</td>
                                    <td>${escapeHtml(r.reviewer_name || '—')}</td>
                                    <td>${formatDate(r.reviewed_at)}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>` : ''}
        </div>
    `;

    // View changes
    $$('.btn-view-changes', main).forEach(btn => {
        btn.addEventListener('click', () => {
            const changes = JSON.parse(btn.dataset.changes);
            let html = '<div class="changes-preview">';
            for (const [key, value] of Object.entries(changes)) {
                html += `<div class="change-item"><strong>${escapeHtml(key)}:</strong> ${escapeHtml(String(value))}</div>`;
            }
            html += '</div>';
            openModal('Proposed Changes', html);
        });
    });

    // Approve
    $$('.btn-approve', main).forEach(btn => {
        btn.addEventListener('click', async () => {
            if (!confirm('Approve this request? The change will be applied immediately.')) return;
            try {
                await api(`/api/requests/${btn.dataset.id}`, {
                    method: 'PATCH',
                    body: JSON.stringify({ action: 'approve' }),
                });
                toast('Request approved and changes applied', 'success');
                updateApprovalBadge();
                route();
            } catch (err) {
                toast(err.message, 'error');
            }
        });
    });

    // Reject
    $$('.btn-reject', main).forEach(btn => {
        btn.addEventListener('click', async () => {
            if (!confirm('Reject this request?')) return;
            try {
                await api(`/api/requests/${btn.dataset.id}`, {
                    method: 'PATCH',
                    body: JSON.stringify({ action: 'reject' }),
                });
                toast('Request rejected', 'info');
                updateApprovalBadge();
                route();
            } catch (err) {
                toast(err.message, 'error');
            }
        });
    });
});

// ════════════════════════════════════════════════════════════════════
//  PAGE: ADMIN PANEL
// ════════════════════════════════════════════════════════════════════

registerPage('admin', async (main) => {
    if (!isAdmin()) { location.hash = '#dashboard'; return; }

    let users = [];
    try {
        const data = await api('/api/admin/users');
        users = data?.users || [];
    } catch (err) {
        toast(err.message, 'error');
    }

    main.innerHTML = `
        <div class="animate-in">
            <div class="page-header">
                <div>
                    <h1>Admin Panel</h1>
                    <p>Manage staff accounts and view system audit log</p>
                </div>
                <button class="btn btn-primary" id="btn-create-user">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                    Create Staff Account
                </button>
            </div>

            <div class="card mb-6">
                <div class="card-header">
                    <h2>Staff Accounts (${users.length})</h2>
                </div>
                <div class="table-wrapper">
                    <table>
                        <thead>
                            <tr>
                                <th>Name</th>
                                <th>Email</th>
                                <th>Role</th>
                                <th>Status</th>
                                <th>Created</th>
                                <th></th>
                            </tr>
                        </thead>
                        <tbody>
                            ${users.map(u => `
                                <tr>
                                    <td><strong>${escapeHtml(u.name)}</strong></td>
                                    <td>${escapeHtml(u.email)}</td>
                                    <td>${roleBadge(u.role)}</td>
                                    <td><span class="badge ${u.is_active ? 'badge-active' : 'badge-disabled'}">${u.is_active ? 'Active' : 'Disabled'}</span></td>
                                    <td>${formatDate(u.created_at)}</td>
                                    <td>
                                        <div class="btn-group">
                                            <button class="btn btn-ghost btn-sm btn-edit-user" data-user='${escapeHtml(JSON.stringify(u))}'>Edit</button>
                                            <button class="btn btn-ghost btn-sm btn-toggle-user" data-user-id="${u.id}" data-active="${u.is_active}">
                                                ${u.is_active ? 'Disable' : 'Enable'}
                                            </button>
                                            ${u.id !== currentUser.id ? `<button class="btn btn-ghost btn-sm btn-delete-user" data-user-id="${u.id}" data-user-name="${escapeHtml(u.name)}">Delete</button>` : ''}
                                        </div>
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>

            <div class="card">
                <div class="card-header">
                    <h2>Audit Log</h2>
                    <button class="btn btn-secondary btn-sm" id="btn-refresh-audit">Refresh</button>
                </div>
                <div id="audit-log-body" class="table-wrapper">
                    <div class="loading-overlay"><div class="spinner"></div></div>
                </div>
                <div id="audit-pagination" class="pagination"></div>
            </div>
        </div>
    `;

    // Toggle user active status
    $$('.btn-toggle-user', main).forEach(btn => {
        btn.addEventListener('click', async () => {
            const userId = btn.dataset.userId;
            const newActive = btn.dataset.active !== 'true';
            try {
                await api(`/api/admin/users/${userId}`, {
                    method: 'PUT',
                    body: JSON.stringify({ is_active: newActive }),
                });
                toast(`Account ${newActive ? 'enabled' : 'disabled'}`, 'success');
                route();
            } catch (err) {
                toast(err.message, 'error');
            }
        });
    });

    // Edit user
    $$('.btn-edit-user', main).forEach(btn => {
        btn.addEventListener('click', () => {
            const u = JSON.parse(btn.dataset.user);
            openModal('Edit Staff Account', `
                <form id="form-edit-user">
                    <div class="input-group">
                        <label for="eu-name">Name</label>
                        <input type="text" id="eu-name" value="${escapeHtml(u.name)}">
                    </div>
                    <div class="input-group">
                        <label for="eu-email">Email</label>
                        <input type="email" id="eu-email" value="${escapeHtml(u.email)}">
                    </div>
                    <div class="input-group">
                        <label for="eu-role">Role</label>
                        <select id="eu-role">
                            <option value="staff" ${u.role === 'staff' ? 'selected' : ''}>Staff</option>
                            <option value="admin" ${u.role === 'admin' ? 'selected' : ''}>Admin</option>
                        </select>
                    </div>
                    <div class="input-group">
                        <label for="eu-password">New Password (leave blank to keep current)</label>
                        <input type="password" id="eu-password" placeholder="New password">
                    </div>
                    <div id="eu-error" class="error-msg" style="display:none;"></div>
                    <button type="submit" class="btn btn-primary btn-full mt-4">Save Changes</button>
                </form>
            `);

            $('#form-edit-user').addEventListener('submit', async (e) => {
                e.preventDefault();
                const body = {
                    name: $('#eu-name').value.trim(),
                    email: $('#eu-email').value.trim(),
                    role: $('#eu-role').value,
                };
                const pw = $('#eu-password').value;
                if (pw) body.password = pw;
                try {
                    await api(`/api/admin/users/${u.id}`, { method: 'PUT', body: JSON.stringify(body) });
                    closeModal();
                    toast('Account updated', 'success');
                    route();
                } catch (err) {
                    const errEl = $('#eu-error');
                    errEl.textContent = err.message;
                    errEl.style.display = '';
                }
            });
        });
    });

    // Delete user
    $$('.btn-delete-user', main).forEach(btn => {
        btn.addEventListener('click', async () => {
            const userName = btn.dataset.userName;
            if (!confirm(`Delete user "${userName}"? This cannot be undone.`)) return;
            try {
                await api(`/api/admin/users/${btn.dataset.userId}`, { method: 'DELETE' });
                toast(`User ${userName} deleted`, 'success');
                route();
            } catch (err) {
                toast(err.message, 'error');
            }
        });
    });

    // Create user
    $('#btn-create-user').addEventListener('click', () => {
        openModal('Create Staff Account', `
            <form id="form-create-user">
                <div class="input-group">
                    <label for="cu-name">Full Name *</label>
                    <input type="text" id="cu-name" required placeholder="Staff member name">
                </div>
                <div class="input-group">
                    <label for="cu-email">Email *</label>
                    <input type="email" id="cu-email" required placeholder="email@clinic.com">
                </div>
                <div class="input-group">
                    <label for="cu-password">Password *</label>
                    <input type="password" id="cu-password" required placeholder="Minimum 6 characters" minlength="6">
                </div>
                <div class="input-group">
                    <label for="cu-role">Role *</label>
                    <select id="cu-role" required>
                        <option value="">Select role…</option>
                        <option value="staff">Staff</option>
                        <option value="admin">Admin</option>
                    </select>
                </div>
                <div id="cu-error" class="error-msg" style="display:none;"></div>
                <button type="submit" class="btn btn-primary btn-full mt-4">Create Account</button>
            </form>
        `);

        $('#form-create-user').addEventListener('submit', async (e) => {
            e.preventDefault();
            const body = {
                name: $('#cu-name').value.trim(),
                email: $('#cu-email').value.trim(),
                password: $('#cu-password').value,
                role: $('#cu-role').value,
            };
            try {
                await api('/api/admin/users', { method: 'POST', body: JSON.stringify(body) });
                closeModal();
                toast('Staff account created!', 'success');
                route();
            } catch (err) {
                const errEl = $('#cu-error');
                errEl.textContent = err.message;
                errEl.style.display = '';
            }
        });
    });

    // Load audit log
    loadAuditLog(1);

    $('#btn-refresh-audit').addEventListener('click', () => loadAuditLog(1));
});

async function loadAuditLog(page) {
    const body = $('#audit-log-body');
    const pagEl = $('#audit-pagination');
    if (!body) return;

    try {
        const data = await api(`/api/admin/audit-log?page=${page}&per_page=20`);
        const entries = data?.entries || [];

        if (entries.length === 0) {
            body.innerHTML = '<div class="empty-state"><p>No audit log entries yet</p></div>';
            pagEl.innerHTML = '';
            return;
        }

        body.innerHTML = `
            <table>
                <thead>
                    <tr>
                        <th>Timestamp</th>
                        <th>User ID</th>
                        <th>Action</th>
                        <th>Detail</th>
                        <th>IP</th>
                    </tr>
                </thead>
                <tbody>
                    ${entries.map(e => `
                        <tr>
                            <td>${formatDate(e.timestamp)} ${e.timestamp ? new Date(e.timestamp).toLocaleTimeString() : ''}</td>
                            <td>${e.user_id ?? '—'}</td>
                            <td><span class="badge badge-tag">${escapeHtml(e.action)}</span></td>
                            <td class="truncate" style="max-width:250px;" title="${escapeHtml(e.detail || '')}">${escapeHtml(e.detail || '—')}</td>
                            <td>${escapeHtml(e.ip_address || '—')}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;

        // Pagination
        const totalPages = data.pages || 1;
        let pagHtml = '';
        pagHtml += `<button ${page <= 1 ? 'disabled' : ''} onclick="window._auditPage(${page - 1})">← Prev</button>`;
        for (let i = 1; i <= totalPages; i++) {
            pagHtml += `<button class="${i === page ? 'active' : ''}" onclick="window._auditPage(${i})">${i}</button>`;
        }
        pagHtml += `<button ${page >= totalPages ? 'disabled' : ''} onclick="window._auditPage(${page + 1})">Next →</button>`;
        pagEl.innerHTML = pagHtml;

    } catch (err) {
        body.innerHTML = `<div class="empty-state"><p>Failed to load audit log</p></div>`;
    }
}

// Expose audit pagination to onclick handlers
window._auditPage = loadAuditLog;

// ════════════════════════════════════════════════════════════════════
//  INIT
// ════════════════════════════════════════════════════════════════════

if (loadSession()) {
    showApp();
} else {
    showLogin();
}

})();
