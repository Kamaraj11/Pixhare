/**
 * app.js — Pixhare Frontend Logic
 *
 * Handles:
 *  - JWT auth (localStorage)
 *  - Page routing (hash-based)
 *  - API calls with helpers
 *  - Toast notifications
 *  - Dashboard (events, photos, guests)
 *  - Photographer auth (register, OTP, login)
 */

'use strict';

// ────────────────────────────────────────────────────────────
// Config
// ────────────────────────────────────────────────────────────
const API = '';   // same origin; change to 'http://localhost:5000' for dev

// ────────────────────────────────────────────────────────────
// State
// ────────────────────────────────────────────────────────────
const state = {
  token:        localStorage.getItem('px_token') || null,
  photographer: JSON.parse(localStorage.getItem('px_user') || 'null'),
  currentEvent: null,
};

// ────────────────────────────────────────────────────────────
// API Helpers
// ────────────────────────────────────────────────────────────
async function apiFetch(path, opts = {}) {
  const headers = { 'Content-Type': 'application/json', ...opts.headers };
  if (state.token) headers['Authorization'] = `Bearer ${state.token}`;
  const res = await fetch(API + path, { ...opts, headers });
  const data = await res.json().catch(() => ({}));
  return { ok: res.ok, status: res.status, data };
}

async function apiUpload(path, formData) {
  const headers = {};
  if (state.token) headers['Authorization'] = `Bearer ${state.token}`;
  const res = await fetch(API + path, { method: 'POST', headers, body: formData });
  const data = await res.json().catch(() => ({}));
  return { ok: res.ok, status: res.status, data };
}

// ────────────────────────────────────────────────────────────
// Toast
// ────────────────────────────────────────────────────────────
function toast(msg, type = 'info', duration = 4000) {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    document.body.appendChild(container);
  }
  const icons = { success: '✅', error: '❌', info: '💜', warning: '⚠️' };
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.innerHTML = `<span>${icons[type] || '💬'}</span><span>${msg}</span>`;
  container.appendChild(el);
  setTimeout(() => el.remove(), duration);
}

// ────────────────────────────────────────────────────────────
// Auth helpers
// ────────────────────────────────────────────────────────────
function saveAuth(token, photographer) {
  state.token = token;
  state.photographer = photographer;
  localStorage.setItem('px_token', token);
  localStorage.setItem('px_user', JSON.stringify(photographer));
}

function clearAuth() {
  state.token = null;
  state.photographer = null;
  localStorage.removeItem('px_token');
  localStorage.removeItem('px_user');
}

function isLoggedIn() { return !!state.token; }

// ────────────────────────────────────────────────────────────
// Loading button helper
// ────────────────────────────────────────────────────────────
function setLoading(btn, loading, originalText) {
  if (loading) {
    btn.dataset.originalText = btn.innerHTML;
    btn.innerHTML = `<span class="spinner"></span> Loading…`;
    btn.disabled = true;
  } else {
    btn.innerHTML = originalText || btn.dataset.originalText || 'Submit';
    btn.disabled = false;
  }
}

// ────────────────────────────────────────────────────────────
// Page Router (hash-based)
// ────────────────────────────────────────────────────────────
const pages = {};

function registerPage(hash, renderFn) { pages[hash] = renderFn; }

function navigate(hash) {
  window.location.hash = hash;
}

function router() {
  const hash = window.location.hash.replace('#', '') || 'home';
  const render = pages[hash] || pages['404'] || (() => '<p>Page not found.</p>');

  // Guard dashboard pages
  if (['dashboard', 'events', 'upload', 'guests', 'settings'].includes(hash) && !isLoggedIn()) {
    navigate('login');
    return;
  }

  const root = document.getElementById('app');
  if (root) {
    root.innerHTML = render();
    root.classList.add('fade-in');
    setTimeout(() => root.classList.remove('fade-in'), 600);
    if (typeof window[`onPage_${hash}`] === 'function') window[`onPage_${hash}`]();
  }
}

window.addEventListener('hashchange', router);
window.addEventListener('DOMContentLoaded', router);

// ────────────────────────────────────────────────────────────
// Register Page
// ────────────────────────────────────────────────────────────
registerPage('register', () => `
<div class="bg-orbs">
  <div class="orb orb-1"></div><div class="orb orb-2"></div><div class="orb orb-3"></div>
</div>
<div style="min-height:100vh;display:flex;align-items:center;justify-content:center;padding:var(--space-5);position:relative;z-index:1;">
  <div style="width:100%;max-width:460px;" class="slide-up">
    <div class="text-center mb-3">
      <div style="width:56px;height:56px;background:var(--grad-primary);border-radius:16px;display:flex;align-items:center;justify-content:center;font-size:1.8rem;margin:0 auto var(--space-3);box-shadow:var(--shadow-glow);">📸</div>
      <h1 style="font-size:1.8rem;">Create Account</h1>
      <p class="mt-1">Join Pixhare as a photographer</p>
    </div>
    <div class="card" style="margin-top:var(--space-5);">
      <form id="register-form" style="display:flex;flex-direction:column;gap:var(--space-4);">
        <div class="form-group">
          <label class="form-label">Full Name</label>
          <input id="reg-name" type="text" class="form-input" placeholder="Your name" autocomplete="name" required>
        </div>
        <div class="form-group">
          <label class="form-label">Studio Name</label>
          <input id="reg-studio" type="text" class="form-input" placeholder="Your studio or business name" required>
        </div>
        <div class="form-group">
          <label class="form-label">Email</label>
          <input id="reg-email" type="email" class="form-input" placeholder="you@email.com" autocomplete="email" required>
        </div>
        <div class="form-group">
          <label class="form-label">Password</label>
          <input id="reg-password" type="password" class="form-input" placeholder="Min 8 chars, include a number" required>
        </div>
        <button id="reg-btn" type="submit" class="btn btn-primary btn-full btn-lg">Create Account</button>
      </form>
      <p class="text-center mt-3" style="font-size:0.9rem;">Already have an account? <a href="#login" style="color:var(--clr-primary);font-weight:600;">Sign in</a></p>
    </div>
  </div>
</div>
`);

window.onPage_register = function() {
  document.getElementById('register-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('reg-btn');
    setLoading(btn, true);
    const { ok, data } = await apiFetch('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({
        name:        document.getElementById('reg-name').value,
        studio_name: document.getElementById('reg-studio').value,
        email:       document.getElementById('reg-email').value,
        password:    document.getElementById('reg-password').value,
      }),
    });
    setLoading(btn, false);
    if (ok) {
      localStorage.setItem('px_pending_email', document.getElementById('reg-email').value);
      toast('Account created! Check your email for the OTP.', 'success');
      navigate('verify-otp');
    } else {
      const err = data.error;
      if (err?.details) {
        Object.values(err.details).forEach(msg => toast(msg, 'error'));
      } else {
        toast(err?.message || 'Registration failed.', 'error');
      }
    }
  });
};

// ────────────────────────────────────────────────────────────
// Verify OTP Page
// ────────────────────────────────────────────────────────────
registerPage('verify-otp', () => `
<div class="bg-orbs"><div class="orb orb-1"></div><div class="orb orb-2"></div></div>
<div style="min-height:100vh;display:flex;align-items:center;justify-content:center;padding:var(--space-5);position:relative;z-index:1;">
  <div style="width:100%;max-width:420px;" class="slide-up">
    <div class="text-center mb-3">
      <div style="font-size:3rem;margin-bottom:var(--space-3);">📬</div>
      <h1 style="font-size:1.8rem;">Check Your Email</h1>
      <p class="mt-1">Enter the 6-digit code we sent to <strong id="otp-email-display" style="color:var(--clr-primary);"></strong></p>
    </div>
    <div class="card" style="margin-top:var(--space-5);">
      <div class="otp-inputs" id="otp-inputs">
        ${[0,1,2,3,4,5].map(i => `<input id="otp-${i}" type="text" maxlength="1" class="otp-digit" inputmode="numeric" autocomplete="one-time-code">`).join('')}
      </div>
      <button id="otp-btn" class="btn btn-primary btn-full btn-lg" style="margin-top:var(--space-5);">Verify Code</button>
      <p class="text-center mt-2" style="font-size:0.85rem;color:var(--clr-text-2);">Didn't get it? <button id="resend-otp-btn" class="btn btn-ghost btn-sm" style="display:inline;">Resend</button></p>
    </div>
  </div>
</div>
`);

window.onPage_verifyotp = function() {}; // alias handled below
window['onPage_verify-otp'] = function() {
  const email = localStorage.getItem('px_pending_email') || '';
  const display = document.getElementById('otp-email-display');
  if (display) display.textContent = email;

  // OTP digit navigation
  const inputs = document.querySelectorAll('.otp-digit');
  inputs.forEach((inp, i) => {
    inp.addEventListener('input', () => {
      inp.value = inp.value.replace(/\D/, '');
      if (inp.value && i < inputs.length - 1) inputs[i+1].focus();
    });
    inp.addEventListener('keydown', (e) => {
      if (e.key === 'Backspace' && !inp.value && i > 0) inputs[i-1].focus();
    });
  });

  document.getElementById('otp-btn')?.addEventListener('click', async () => {
    const otp = [...inputs].map(i => i.value).join('');
    if (otp.length !== 6) { toast('Please enter all 6 digits.', 'error'); return; }
    const btn = document.getElementById('otp-btn');
    setLoading(btn, true);
    const { ok, data } = await apiFetch('/api/auth/verify-otp', {
      method: 'POST',
      body: JSON.stringify({ email, otp }),
    });
    setLoading(btn, false);
    if (ok) {
      saveAuth(data.token, data.photographer);
      localStorage.removeItem('px_pending_email');
      toast('Email verified! Welcome to Pixhare 🎉', 'success');
      navigate('dashboard');
    } else {
      toast(data.error?.message || 'Invalid OTP.', 'error');
    }
  });

  document.getElementById('resend-otp-btn')?.addEventListener('click', async () => {
    const { ok } = await apiFetch('/api/auth/resend-otp', { method: 'POST', body: JSON.stringify({ email }) });
    if (ok) toast('New OTP sent!', 'success');
    else toast('Failed to resend OTP.', 'error');
  });
};

// ────────────────────────────────────────────────────────────
// Login Page
// ────────────────────────────────────────────────────────────
registerPage('login', () => `
<div class="bg-orbs"><div class="orb orb-1"></div><div class="orb orb-2"></div><div class="orb orb-3"></div></div>
<div style="min-height:100vh;display:flex;align-items:center;justify-content:center;padding:var(--space-5);position:relative;z-index:1;">
  <div style="width:100%;max-width:420px;" class="slide-up">
    <div class="text-center mb-3">
      <div style="width:56px;height:56px;background:var(--grad-primary);border-radius:16px;display:flex;align-items:center;justify-content:center;font-size:1.8rem;margin:0 auto var(--space-3);box-shadow:var(--shadow-glow);">📸</div>
      <h1 style="font-size:1.8rem;">Welcome Back</h1>
      <p class="mt-1">Sign in to your Pixhare account</p>
    </div>
    <div class="card" style="margin-top:var(--space-5);">
      <form id="login-form" style="display:flex;flex-direction:column;gap:var(--space-4);">
        <div class="form-group">
          <label class="form-label">Email</label>
          <input id="login-email" type="email" class="form-input" placeholder="you@email.com" autocomplete="email" required>
        </div>
        <div class="form-group">
          <label class="form-label">Password</label>
          <input id="login-password" type="password" class="form-input" placeholder="••••••••" autocomplete="current-password" required>
        </div>
        <button id="login-btn" type="submit" class="btn btn-primary btn-full btn-lg">Sign In</button>
      </form>
      <p class="text-center mt-3" style="font-size:0.9rem;">No account? <a href="#register" style="color:var(--clr-primary);font-weight:600;">Create one</a></p>
    </div>
  </div>
</div>
`);

window.onPage_login = function() {
  if (isLoggedIn()) { navigate('dashboard'); return; }
  document.getElementById('login-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('login-btn');
    setLoading(btn, true);
    const { ok, data } = await apiFetch('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({
        email:    document.getElementById('login-email').value,
        password: document.getElementById('login-password').value,
      }),
    });
    setLoading(btn, false);
    if (ok) {
      saveAuth(data.token, data.photographer);
      toast(`Welcome back, ${data.photographer.name}! 👋`, 'success');
      navigate('dashboard');
    } else {
      toast(data.error?.message || 'Login failed.', 'error');
    }
  });
};

// ────────────────────────────────────────────────────────────
// Dashboard Page
// ────────────────────────────────────────────────────────────
registerPage('dashboard', () => `
<div style="min-height:100vh;padding-top:68px;">
  ${renderNavbar()}
  <div class="layout">
    ${renderSidebar('dashboard')}
    <main class="main-content">
      <div class="slide-up">
        <h2>Welcome back, <span style="color:var(--clr-primary);">${state.photographer?.name || 'Photographer'}</span> 👋</h2>
        <p class="mt-1">Here's an overview of your Pixhare account.</p>
        <div class="grid grid-4 gap-4" style="margin-top:var(--space-6);" id="stats-grid">
          <div class="stat-card"><div class="stat-value" id="stat-events">—</div><div class="stat-label">Events</div></div>
          <div class="stat-card"><div class="stat-value" id="stat-photos">—</div><div class="stat-label">Photos</div></div>
          <div class="stat-card"><div class="stat-value" id="stat-guests">—</div><div class="stat-label">Guests</div></div>
          <div class="stat-card"><div class="stat-value" id="stat-matched">—</div><div class="stat-label">Matched</div></div>
        </div>
        <div style="margin-top:var(--space-7);">
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:var(--space-5);">
            <h3>Recent Events</h3>
            <button class="btn btn-primary btn-sm" onclick="navigate('events')">View All Events</button>
          </div>
          <div id="recent-events">
            <div style="text-align:center;padding:var(--space-7);color:var(--clr-text-3);">
              <div class="spinner" style="margin:0 auto var(--space-3);"></div>
              <p>Loading events…</p>
            </div>
          </div>
        </div>
      </div>
    </main>
  </div>
</div>
`);

window.onPage_dashboard = async function() {
  const { ok, data } = await apiFetch('/api/events');
  if (!ok) { clearAuth(); navigate('login'); return; }

  const events = data.events || [];
  let totalPhotos = 0, totalGuests = 0;
  events.forEach(e => { totalPhotos += e.photo_count || 0; });

  document.getElementById('stat-events').textContent = events.length;
  document.getElementById('stat-photos').textContent = totalPhotos;
  document.getElementById('stat-guests').textContent = '—';
  document.getElementById('stat-matched').textContent = '—';

  const container = document.getElementById('recent-events');
  if (events.length === 0) {
    container.innerHTML = `
      <div class="card" style="text-align:center;padding:var(--space-7);">
        <div style="font-size:3rem;margin-bottom:var(--space-3);">🎉</div>
        <h3>No events yet</h3>
        <p class="mt-1">Create your first event to get started.</p>
        <button class="btn btn-primary mt-3" onclick="showCreateEventModal()">Create Event</button>
      </div>`;
  } else {
    container.innerHTML = events.slice(0, 3).map(e => renderEventCard(e)).join('');
  }
};

function renderEventCard(e) {
  return `
  <div class="card card-sm" style="margin-bottom:var(--space-3);display:flex;align-items:center;justify-content:space-between;gap:var(--space-4);">
    <div>
      <h4>${e.name}</h4>
      <div style="display:flex;gap:var(--space-3);margin-top:var(--space-2);">
        <span class="badge badge-primary">📅 ${e.date}</span>
        ${e.venue ? `<span class="badge badge-primary">📍 ${e.venue}</span>` : ''}
        <span class="badge badge-success">📷 ${e.photo_count} photos</span>
      </div>
    </div>
    <div style="display:flex;gap:var(--space-3);flex-shrink:0;">
      <button class="btn btn-secondary btn-sm" onclick="viewEventPhotos('${e.name}')">Photos</button>
      <button class="btn btn-outline btn-sm" onclick="downloadQR(${e.id})">QR Code</button>
    </div>
  </div>`;
}

// ────────────────────────────────────────────────────────────
// Events Page
// ────────────────────────────────────────────────────────────
registerPage('events', () => `
<div style="min-height:100vh;padding-top:68px;">
  ${renderNavbar()}
  <div class="layout">
    ${renderSidebar('events')}
    <main class="main-content">
      <div class="slide-up">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:var(--space-6);">
          <div>
            <h2>Events</h2>
            <p class="mt-1">Manage your events and QR codes</p>
          </div>
          <button class="btn btn-primary" id="create-event-btn" onclick="showCreateEventModal()">+ New Event</button>
        </div>
        <div id="events-list">
          <div class="spinner" style="margin:var(--space-7) auto;display:block;"></div>
        </div>
      </div>
    </main>
  </div>
</div>
<!-- Create Event Modal -->
<div class="modal-overlay" id="create-event-modal">
  <div class="modal">
    <div class="modal-header">
      <h3>Create New Event</h3>
      <button class="modal-close" onclick="closeModal('create-event-modal')">✕</button>
    </div>
    <form id="create-event-form" style="display:flex;flex-direction:column;gap:var(--space-4);">
      <div class="form-group">
        <label class="form-label">Event Name *</label>
        <input id="ev-name" type="text" class="form-input" placeholder="e.g. Raj & Priya Wedding 2026" required>
      </div>
      <div class="grid grid-2 gap-4">
        <div class="form-group">
          <label class="form-label">Date *</label>
          <input id="ev-date" type="date" class="form-input" required>
        </div>
        <div class="form-group">
          <label class="form-label">Time</label>
          <input id="ev-time" type="time" class="form-input">
        </div>
      </div>
      <div class="form-group">
        <label class="form-label">Venue</label>
        <input id="ev-venue" type="text" class="form-input" placeholder="e.g. Grand Ballroom, Chennai">
      </div>
      <div class="form-group">
        <label class="form-label">Description</label>
        <textarea id="ev-desc" class="form-input" rows="3" placeholder="Optional event details…" style="resize:vertical;"></textarea>
      </div>
      <button id="create-ev-btn" type="submit" class="btn btn-primary btn-full">Create Event</button>
    </form>
  </div>
</div>
`);

window.onPage_events = async function() {
  const { ok, data } = await apiFetch('/api/events');
  const container = document.getElementById('events-list');
  if (!ok) { container.innerHTML = '<p>Failed to load events.</p>'; return; }
  const events = data.events || [];
  if (events.length === 0) {
    container.innerHTML = `<div class="card" style="text-align:center;padding:var(--space-7);">
      <div style="font-size:3rem;margin-bottom:var(--space-3);">📅</div>
      <h3>No events yet</h3><p class="mt-1">Create your first event to generate a QR code.</p>
    </div>`;
  } else {
    container.innerHTML = events.map(e => renderEventCard(e)).join('');
  }

  document.getElementById('create-event-form')?.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const btn = document.getElementById('create-ev-btn');
    setLoading(btn, true);
    const { ok, data } = await apiFetch('/api/events', {
      method: 'POST',
      body: JSON.stringify({
        name:        document.getElementById('ev-name').value,
        date:        document.getElementById('ev-date').value,
        event_time:  document.getElementById('ev-time').value,
        venue:       document.getElementById('ev-venue').value,
        description: document.getElementById('ev-desc').value,
      }),
    });
    setLoading(btn, false);
    if (ok) { toast('Event created!', 'success'); closeModal('create-event-modal'); window.onPage_events(); }
    else toast(data.error?.message || 'Failed to create event.', 'error');
  });
};

window.showCreateEventModal = function() {
  document.getElementById('create-event-modal')?.classList.add('open');
};

window.downloadQR = function(eventId) {
  window.open(`${API}/api/events/${eventId}/qr`, '_blank');
};

window.viewEventPhotos = function(eventName) {
  state.currentEvent = eventName;
  navigate('upload');
};

// ────────────────────────────────────────────────────────────
// Upload / Photos Page
// ────────────────────────────────────────────────────────────
registerPage('upload', () => `
<div style="min-height:100vh;padding-top:68px;">
  ${renderNavbar()}
  <div class="layout">
    ${renderSidebar('upload')}
    <main class="main-content">
      <div class="slide-up">
        <h2>Upload Photos</h2>
        <p class="mt-1" id="upload-event-label">Select an event to upload photos</p>
        <div style="margin:var(--space-5) 0;">
          <select id="event-select" class="form-input" style="max-width:320px;">
            <option value="">— Select Event —</option>
          </select>
        </div>
        <div class="upload-zone" id="upload-zone">
          <div class="upload-icon">📤</div>
          <h3>Drag & Drop Photos Here</h3>
          <p class="mt-1">or click to browse — JPG, JPEG, PNG — max 16 MB each</p>
          <input type="file" id="photo-file-input" accept=".jpg,.jpeg,.png" multiple style="display:none;">
          <button class="btn btn-primary mt-3" onclick="document.getElementById('photo-file-input').click()">Browse Files</button>
        </div>
        <div id="upload-progress" class="hidden" style="margin-top:var(--space-4);">
          <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
            <span style="font-size:0.9rem;" id="progress-label">Uploading…</span>
            <span style="font-size:0.9rem;" id="progress-pct">0%</span>
          </div>
          <div class="progress"><div class="progress-bar" id="progress-bar"></div></div>
        </div>
        <div id="photo-grid-section" style="margin-top:var(--space-7);">
          <h3 style="margin-bottom:var(--space-4);">Uploaded Photos</h3>
          <div class="photo-grid" id="photos-grid"></div>
        </div>
      </div>
    </main>
  </div>
</div>
`);

window.onPage_upload = async function() {
  const { ok, data } = await apiFetch('/api/events');
  const sel = document.getElementById('event-select');
  if (ok) {
    (data.events || []).forEach(e => {
      const o = document.createElement('option');
      o.value = e.name; o.textContent = e.name;
      if (e.name === state.currentEvent) o.selected = true;
      sel.appendChild(o);
    });
  }

  if (state.currentEvent) loadPhotos(state.currentEvent);

  sel.addEventListener('change', () => {
    state.currentEvent = sel.value;
    if (sel.value) loadPhotos(sel.value);
  });

  // Drag & Drop
  const zone = document.getElementById('upload-zone');
  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('dragover'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
  zone.addEventListener('drop', e => {
    e.preventDefault(); zone.classList.remove('dragover');
    uploadFiles(e.dataTransfer.files);
  });

  document.getElementById('photo-file-input').addEventListener('change', e => uploadFiles(e.target.files));
};

async function loadPhotos(eventName) {
  const grid = document.getElementById('photos-grid');
  grid.innerHTML = '<div class="spinner" style="margin:0 auto;"></div>';
  const { ok, data } = await apiFetch(`/api/events/${encodeURIComponent(eventName)}/photos`);
  if (!ok) { grid.innerHTML = '<p>Failed to load photos.</p>'; return; }
  const photos = data.photos || [];
  if (photos.length === 0) { grid.innerHTML = '<p style="color:var(--clr-text-3);">No photos yet.</p>'; return; }
  grid.innerHTML = photos.map(p => `
    <div class="photo-item">
      <img src="${p.url}" alt="${p.filename}" loading="lazy" onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%22200%22 height=%22150%22><rect fill=%22%23111%22 width=%22200%22 height=%22150%22/><text fill=%22%23555%22 x=%2250%%22 y=%2250%%22 text-anchor=%22middle%22 dy=%22.3em%22>📷</text></svg>'">
      <div class="photo-overlay">
        <span class="badge badge-${p.status === 'processed' ? 'success' : 'warning'}">${p.status}</span>
      </div>
    </div>`).join('');
}

async function uploadFiles(files) {
  const eventName = document.getElementById('event-select').value;
  if (!eventName) { toast('Please select an event first.', 'error'); return; }
  if (!files || files.length === 0) return;

  const bar     = document.getElementById('progress-bar');
  const pct     = document.getElementById('progress-pct');
  const label   = document.getElementById('progress-label');
  const section = document.getElementById('upload-progress');
  section.classList.remove('hidden');

  const form = new FormData();
  [...files].forEach(f => form.append('photos', f));
  label.textContent = `Uploading ${files.length} photo(s)…`;
  bar.style.width = '30%'; pct.textContent = '30%';

  const { ok, data } = await apiUpload(`/api/events/${encodeURIComponent(eventName)}/photos`, form);
  bar.style.width = '100%'; pct.textContent = '100%';

  if (ok) {
    toast(`${data.uploaded} photo(s) uploaded! Face detection running in background ⚡`, 'success', 6000);
    setTimeout(() => { section.classList.add('hidden'); loadPhotos(eventName); }, 1500);
  } else {
    toast(data.error?.message || 'Upload failed.', 'error');
    section.classList.add('hidden');
  }
}

// ────────────────────────────────────────────────────────────
// Home / Landing Page
// ────────────────────────────────────────────────────────────
registerPage('home', () => `
<div class="bg-orbs"><div class="orb orb-1"></div><div class="orb orb-2"></div><div class="orb orb-3"></div></div>
${renderNavbar(true)}
<section style="min-height:100vh;display:flex;align-items:center;justify-content:center;padding:calc(68px + var(--space-7)) var(--space-5) var(--space-7);position:relative;z-index:1;text-align:center;">
  <div style="max-width:720px;" class="slide-up">
    <span class="badge badge-primary" style="font-size:0.8rem;margin-bottom:var(--space-4);display:inline-flex;">✨ AI-Powered Event Photography</span>
    <h1 class="text-gradient">Every Guest Finds<br>Their Moments</h1>
    <p style="font-size:1.15rem;max-width:520px;margin:var(--space-5) auto;color:var(--clr-text-2);">
      Pixhare uses AI face recognition to automatically match event photos to every guest — delivered straight to their inbox.
    </p>
    <div style="display:flex;gap:var(--space-4);justify-content:center;flex-wrap:wrap;margin-top:var(--space-6);">
      <a href="#register" class="btn btn-primary btn-lg">Get Started Free →</a>
      <a href="#login" class="btn btn-secondary btn-lg">Sign In</a>
    </div>
    <div class="grid grid-3 gap-5" style="margin-top:var(--space-8);">
      <div class="card" style="text-align:center;">
        <div style="font-size:2.5rem;margin-bottom:var(--space-3);">🤳</div>
        <h4>Scan & Register</h4>
        <p class="mt-1" style="font-size:0.85rem;">Guests scan your QR code and take a quick selfie</p>
      </div>
      <div class="card" style="text-align:center;">
        <div style="font-size:2.5rem;margin-bottom:var(--space-3);">🧠</div>
        <h4>AI Face Match</h4>
        <p class="mt-1" style="font-size:0.85rem;">RetinaFace + ArcFace finds every photo of them instantly</p>
      </div>
      <div class="card" style="text-align:center;">
        <div style="font-size:2.5rem;margin-bottom:var(--space-3);">📧</div>
        <h4>Auto Gallery</h4>
        <p class="mt-1" style="font-size:0.85rem;">Personal gallery link delivered to their email automatically</p>
      </div>
    </div>
  </div>
</section>
`);

// ────────────────────────────────────────────────────────────
// Shared UI Renderers
// ────────────────────────────────────────────────────────────
function renderNavbar(landing = false) {
  const loggedIn = isLoggedIn();
  return `
  <nav class="navbar">
    <a href="#home" class="navbar-brand">
      <div class="logo-icon">📸</div>
      <span>Pixhare</span>
    </a>
    <div class="navbar-links">
      ${landing ? '<a href="#home" class="nav-link">Home</a>' : ''}
      ${loggedIn
        ? `<a href="#events" class="nav-link">Events</a>
           <a href="#upload" class="nav-link">Upload</a>
           <span style="color:var(--clr-text-3);font-size:0.85rem;">${state.photographer?.name || ''}</span>
           <button class="btn btn-outline btn-sm" onclick="logout()">Sign Out</button>`
        : `<a href="#login" class="btn btn-secondary btn-sm">Sign In</a>
           <a href="#register" class="btn btn-primary btn-sm">Get Started</a>`}
    </div>
  </nav>`;
}

function renderSidebar(active) {
  const items = [
    { id: 'dashboard', icon: '🏠', label: 'Dashboard' },
    { id: 'events',    icon: '📅', label: 'Events' },
    { id: 'upload',    icon: '📤', label: 'Upload Photos' },
    { id: 'guests',    icon: '👥', label: 'Guests' },
  ];
  return `
  <aside class="sidebar">
    <div class="sidebar-section">Navigation</div>
    ${items.map(item => `
      <a href="#${item.id}" class="sidebar-item ${active === item.id ? 'active' : ''}">
        ${item.icon} ${item.label}
      </a>`).join('')}
    <div class="sidebar-section" style="margin-top:var(--space-6);">Account</div>
    <div class="sidebar-item" onclick="logout()">🚪 Sign Out</div>
  </aside>`;
}

// ────────────────────────────────────────────────────────────
// Modal helpers
// ────────────────────────────────────────────────────────────
window.closeModal = function(id) {
  document.getElementById(id)?.classList.remove('open');
};

// Close modal on overlay click
document.addEventListener('click', e => {
  if (e.target.classList.contains('modal-overlay')) e.target.classList.remove('open');
});

// ────────────────────────────────────────────────────────────
// Logout
// ────────────────────────────────────────────────────────────
window.logout = function() {
  clearAuth();
  toast('Signed out.', 'info');
  navigate('home');
};

// ────────────────────────────────────────────────────────────
// 404 fallback
// ────────────────────────────────────────────────────────────
registerPage('404', () => `
<div style="min-height:100vh;display:flex;align-items:center;justify-content:center;text-align:center;">
  <div class="slide-up">
    <div style="font-size:5rem;margin-bottom:var(--space-4);">🔍</div>
    <h1 style="font-size:2rem;">Page not found</h1>
    <p class="mt-2">The page you're looking for doesn't exist.</p>
    <a href="#home" class="btn btn-primary mt-4">Go Home</a>
  </div>
</div>
`);
