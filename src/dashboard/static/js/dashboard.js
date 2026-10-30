/**
 * CONTRACTRISK-XAI — Modern LegalTech SaaS Frontend Logic
 * Implements JWT authentication, role-based navigation, contract upload,
 * lawyer workbench, statutory evidence display, decision submission,
 * final reports lifecycle, and client feedback.
 */

// Global Application State
const AppState = {
  currentUser: null,
  currentWorkbenchReviewId: null,
  currentSelectedSegmentId: null,
  currentWorkbenchDocId: null,
  currentClientActiveReportId: null,
  activeTab: 'overview'
};

// =============================================================================
// AUTHENTICATION & SECURE SESSION MANAGEMENT (Task 036)
// =============================================================================

function getCsrfToken() {
  const match = document.cookie.match(new RegExp('(^|;\\s*)contractrisk_csrf=([^;]+)'));
  return match ? decodeURIComponent(match[2]) : null;
}

async function initAuth() {
  try {
    const res = await fetch('/api/auth/me', { credentials: 'same-origin' });
    if (res.ok) {
      const user = await res.json();
      AppState.currentUser = user;
      updateUserUI();
      return;
    }
  } catch (e) {
    console.warn("Session check error:", e);
  }

  // If unauthenticated, auto-load demo lawyer persona for seamless evaluation
  clearAuth();
  await loginWithDemo('LAWYER');
}

function clearAuth() {
  AppState.currentUser = null;
  AppState.currentWorkbenchReviewId = null;
  AppState.currentSelectedSegmentId = null;
  AppState.currentWorkbenchDocId = null;
  AppState.currentClientActiveReportId = null;
  localStorage.removeItem('contractrisk_token');
  localStorage.removeItem('contractrisk_user');
  updateUserUI();
}

function updateUserUI() {
  const avatar = document.getElementById('nav-user-avatar');
  const name = document.getElementById('nav-user-name');
  const role = document.getElementById('nav-user-role');
  const logoutBtn = document.getElementById('btn-logout');

  if (AppState.currentUser) {
    if (name) name.textContent = AppState.currentUser.full_name || AppState.currentUser.email;
    if (role) {
      const isVerified = AppState.currentUser.advocate_status === 'VERIFIED';
      role.textContent = isVerified ? `${AppState.currentUser.role} (Verified Advocate)` : AppState.currentUser.role;
    }
    if (avatar) {
      const initial = (AppState.currentUser.full_name || AppState.currentUser.email || 'A').charAt(0).toUpperCase();
      avatar.textContent = initial;
    }
    if (logoutBtn) logoutBtn.style.display = 'inline-flex';
  } else {
    if (name) name.textContent = 'Guest (Viewing)';
    if (role) role.textContent = 'Demo Mode';
    if (avatar) avatar.textContent = '⚖';
    if (logoutBtn) logoutBtn.style.display = 'none';
  }

  // Supervising lawyer controls visibility
  const assignBtn = document.getElementById('wb-assign-lawyer-btn');
  if (assignBtn) {
    assignBtn.style.display = (AppState.currentUser && AppState.currentUser.role === 'SUPERVISING_LAWYER') ? 'inline-flex' : 'none';
  }
}

async function apiFetch(url, options = {}) {
  const opts = { ...options };
  opts.credentials = opts.credentials || 'same-origin';
  const headers = { ...(opts.headers || {}) };

  // For state-changing HTTP methods, attach CSRF header from Double-Submit cookie
  const method = (opts.method || 'GET').toUpperCase();
  if (['POST', 'PUT', 'DELETE', 'PATCH'].includes(method)) {
    const csrfToken = getCsrfToken();
    if (csrfToken) {
      headers['X-CSRF-Token'] = csrfToken;
    }
  }

  opts.headers = headers;

  try {
    const res = await fetch(url, opts);
    if (res.status === 401) {
      clearAuth();
      console.warn("Session expired or unauthorized (401).");
    } else if (res.status === 403) {
      console.warn("Action forbidden (403): insufficient privilege.");
    }
    return res;
  } catch (err) {
    console.error("Network error accessing API:", err);
    throw err;
  }
}

// Modal Controls
function openLoginModal() {
  const m = document.getElementById('login-modal');
  if (m) m.classList.add('active');
}
function closeLoginModal() {
  const m = document.getElementById('login-modal');
  if (m) m.classList.remove('active');
}
function openUploadModal() {
  const m = document.getElementById('upload-modal');
  if (m) m.classList.add('active');
}
function closeUploadModal() {
  const m = document.getElementById('upload-modal');
  if (m) m.classList.remove('active');
}
function openDraftReportModal() {
  const m = document.getElementById('draft-report-modal');
  if (m) m.classList.add('active');
}
function closeDraftReportModal() {
  const m = document.getElementById('draft-report-modal');
  if (m) m.classList.remove('active');
}

// Additional Modal Open/Close Controls
function openRevisionModal() {
  if (!AppState.currentWorkbenchReviewId) {
    showToast('Please select a contract from the review queue first.', 'warning');
    return;
  }
  const revText = document.getElementById('rev-text');
  const revReason = document.getElementById('rev-reason');
  if (revText) revText.value = '';
  if (revReason) revReason.value = '';
  openModal('revision-modal');
}
function closeRevisionModal() {
  closeModal('revision-modal');
}

function openCompleteReviewModal() {
  if (!AppState.currentWorkbenchReviewId) {
    showToast('Please select a contract from the review queue first.', 'warning');
    return;
  }
  const chk = document.getElementById('comp-disclaimer-check');
  if (chk) chk.checked = false;
  openModal('complete-review-modal');
}
function closeCompleteReviewModal() {
  closeModal('complete-review-modal');
}

function openAuthorFindingModal() {
  if (!AppState.currentWorkbenchReviewId) {
    showToast('Please select a contract review first.', 'warning');
    return;
  }
  if (!AppState.currentSelectedSegmentId) {
    showToast('Please select a contract clause on the left panel first.', 'warning');
    return;
  }
  const riskInput = document.getElementById('af-risk-label');
  const obsInput = document.getElementById('af-observation');
  const ratInput = document.getElementById('af-rationale');
  const notesInput = document.getElementById('af-notes');
  if (riskInput) riskInput.value = '';
  if (obsInput) obsInput.value = '';
  if (ratInput) ratInput.value = '';
  if (notesInput) notesInput.value = '';
  openModal('author-finding-modal');
}
function closeAuthorFindingModal() {
  closeModal('author-finding-modal');
}

async function openAssignLawyerModal() {
  if (!AppState.currentWorkbenchReviewId) {
    showToast('Please select a contract review first.', 'warning');
    return;
  }
  const selectEl = document.getElementById('assign-lawyer-select');
  if (selectEl) {
    selectEl.innerHTML = '<option value="">Loading eligible advocates...</option>';
  }
  openModal('assign-lawyer-modal');

  try {
    const res = await apiFetch('/api/review/eligible-lawyers');
    if (!res.ok) {
      if (selectEl) selectEl.innerHTML = '<option value="">Error loading advocates</option>';
      return;
    }
    const data = await res.json();
    const advocates = data.advocates || [];
    if (advocates.length === 0) {
      if (selectEl) selectEl.innerHTML = '<option value="">No verified advocates found</option>';
      return;
    }
    if (selectEl) {
      selectEl.innerHTML = '<option value="">Select an enrolled advocate...</option>' + advocates.map(a => `
        <option value="${a.id}">${escapeHtml(a.full_name)} (${escapeHtml(a.state_bar_council || 'State Bar')} &bull; Enrolment: ${escapeHtml(a.bar_enrolment_id || 'Verified')})</option>
      `).join('');
    }
  } catch (err) {
    if (selectEl) selectEl.innerHTML = `<option value="">Error: ${err}</option>`;
  }
}
function closeAssignLawyerModal() {
  closeModal('assign-lawyer-modal');
}

function openClientRevisionModal() {
  if (!AppState.currentClientActiveReviewId) {
    showToast('Please select a contract first.', 'warning');
    return;
  }
  const txt = document.getElementById('client-rev-text');
  const reason = document.getElementById('client-rev-reason');
  if (txt) txt.value = '';
  if (reason) reason.value = '';
  openModal('client-revision-modal');
}
function closeClientRevisionModal() {
  closeModal('client-revision-modal');
}

function togglePasswordVisibility() {
  const pwdInput = document.getElementById('auth-password');
  const btn = document.getElementById('btn-toggle-password');
  if (!pwdInput) return;
  if (pwdInput.type === 'password') {
    pwdInput.type = 'text';
    if (btn) btn.innerHTML = '&#128064;';
  } else {
    pwdInput.type = 'password';
    if (btn) btn.innerHTML = '&#128065;';
  }
}

// Toast Notifications System
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) {
    console.log(`[Toast ${type}]: ${message}`);
    return;
  }

  const icons = {
    success: '&#10003;',
    error: '&#9888;',
    warning: '&#9888;',
    info: '&#8505;'
  };

  const toast = document.createElement('div');
  toast.className = `toast-item toast-${type}`;
  toast.innerHTML = `
    <span class="toast-icon">${icons[type] || '&#8505;'}</span>
    <span class="toast-msg">${escapeHtml(message)}</span>
    <button type="button" class="toast-close" onclick="this.parentElement.remove()" aria-label="Dismiss notification">&times;</button>
  `;
  container.appendChild(toast);

  setTimeout(() => {
    if (toast.parentElement) {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(20px)';
      toast.style.transition = 'all 0.25s ease';
      setTimeout(() => toast.remove(), 250);
    }
  }, 4000);
}

// Demo Persona Quick Selector
const DEMO_PERSONAS = {
  LAWYER: { email: 'advocate@legal.in', password: 'LegalTech2026!' },
  CLIENT: { email: 'client@enterprise.in', password: 'ClientTech2026!' },
  SUPERVISING_LAWYER: { email: 'supervisor@legal.in', password: 'SuperTech2026!' },
  AUDITOR: { email: 'auditor@governance.in', password: 'AuditTech2026!' }
};

function quickSelectRole(role) {
  document.querySelectorAll('.role-btn').forEach(b => b.classList.remove('active'));
  const btn = Array.from(document.querySelectorAll('.role-btn')).find(b => b.getAttribute('onclick') && b.getAttribute('onclick').includes(role));
  if (btn) btn.classList.add('active');

  const creds = DEMO_PERSONAS[role] || DEMO_PERSONAS.LAWYER;
  const emailInput = document.getElementById('auth-email');
  const pwdInput = document.getElementById('auth-password');
  if (emailInput) emailInput.value = creds.email;
  if (pwdInput) pwdInput.value = creds.password;
}

async function handleAuthSubmit(event) {
  if (event) event.preventDefault();
  const email = document.getElementById('auth-email').value.trim();
  const password = document.getElementById('auth-password').value;
  const rememberMe = document.getElementById('auth-remember-me') ? document.getElementById('auth-remember-me').checked : false;
  const errEl = document.getElementById('auth-error-msg');
  if (errEl) errEl.style.display = 'none';

  try {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ email, password, remember_me: rememberMe })
    });
    const data = await res.json();
    if (!res.ok) {
      if (errEl) {
        errEl.textContent = data.error || 'Authentication failed. Please verify credentials.';
        errEl.style.display = 'block';
      }
      return;
    }

    // Secure HttpOnly session cookie is managed by browser; state contains public identity profile
    AppState.currentUser = data.user;
    updateUserUI();
    closeLoginModal();

    if (data.user.role === 'CLIENT') {
      switchTab('client-workspace');
      loadClientWorkspace();
    } else {
      switchTab('lawyer-workbench');
      loadWorkbenchQueue();
    }
  } catch (err) {
    if (errEl) {
      errEl.textContent = 'Server error: ' + err;
      errEl.style.display = 'block';
    }
  }
}

async function loginWithDemo(role) {
  const creds = DEMO_PERSONAS[role] || DEMO_PERSONAS.LAWYER;
  try {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ email: creds.email, password: creds.password })
    });
    const data = await res.json();
    if (res.ok && data.user) {
      AppState.currentUser = data.user;
      updateUserUI();
    }
  } catch (e) {
    console.warn("Auto-demo login note:", e);
  }
}

async function logoutUser() {
  try {
    await apiFetch('/api/auth/logout', { method: 'POST' });
  } catch (e) {
    console.warn("Logout request failed:", e);
  }
  clearAuth();
  updateUserUI();
  location.reload();
}

// Contract Upload Handling
let selectedContractFile = null;

function handleFileSelection(event) {
  const file = event.target.files[0];
  if (file) {
    selectedContractFile = file;
    const nameEl = document.getElementById('selected-file-name');
    if (nameEl) nameEl.textContent = `Selected: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
  }
}

async function handleContractUpload(event) {
  if (event) event.preventDefault();
  const title = document.getElementById('upload-file-title').value.trim();
  const fileInput = document.getElementById('upload-file-input');
  const file = selectedContractFile || (fileInput ? fileInput.files[0] : null);
  const statusEl = document.getElementById('upload-status-msg');

  if (!file) {
    if (statusEl) {
      statusEl.className = 'badge badge-danger';
      statusEl.textContent = 'Please choose a contract file (.pdf, .docx, .txt).';
      statusEl.style.display = 'block';
    }
    return;
  }

  const formData = new FormData();
  formData.append('title', title);
  formData.append('file', file);

  const submitBtn = document.getElementById('btn-upload-submit');
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.textContent = 'Ingesting & Segmenting...';
  }

  try {
    const res = await apiFetch('/api/review/upload', {
      method: 'POST',
      body: formData
    });
    const data = await res.json();
    if (!res.ok) {
      if (statusEl) {
        statusEl.className = 'badge badge-danger';
        statusEl.textContent = data.error || 'Upload failed.';
        statusEl.style.display = 'block';
      }
      return;
    }

    if (statusEl) {
      statusEl.className = 'badge badge-success';
      statusEl.textContent = `Contract successfully ingested! ${data.segments_count} clauses segmented for review.`;
      statusEl.style.display = 'block';
    }

    showToast(`Contract "${data.filename || title}" uploaded successfully! Segmented ${data.segments_count} clauses.`, 'success');

    // Reset inputs
    document.getElementById('upload-file-title').value = '';
    if (fileInput) fileInput.value = '';
    selectedContractFile = null;
    const nameEl = document.getElementById('selected-file-name');
    if (nameEl) nameEl.textContent = '';

    setTimeout(() => {
      closeUploadModal();
      if (statusEl) statusEl.style.display = 'none';
      switchTab('client-workspace');
      loadClientWorkspace();
      loadWorkbenchQueue();
    }, 1000);
  } catch (err) {
    if (statusEl) {
      statusEl.className = 'badge badge-danger';
      statusEl.textContent = 'Error: ' + err;
      statusEl.style.display = 'block';
    }
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Start Ingestion & Review';
    }
  }
}

// Navigation & Tab Switching
function switchTab(tabId) {
  AppState.activeTab = tabId;

  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.nav-tab').forEach(el => {
    el.classList.remove('active');
    el.setAttribute('aria-selected', 'false');
  });

  const target = document.getElementById('tab-' + tabId);
  if (target) {
    target.classList.add('active');
  }

  const btns = Array.from(document.querySelectorAll('.nav-tab'));
  const activeBtn = btns.find(b => b.getAttribute('onclick') && b.getAttribute('onclick').includes(tabId));
  if (activeBtn) {
    activeBtn.classList.add('active');
    activeBtn.setAttribute('aria-selected', 'true');
  }

  // Load contextual data
  if (tabId === 'lawyer-workbench') loadWorkbenchQueue();
  if (tabId === 'client-workspace') loadClientWorkspace();
}

// =============================================================================
// LAWYER WORKBENCH WORKFLOW
// =============================================================================

async function loadWorkbenchQueue() {
  const listEl = document.getElementById('workbench-queue-list');
  const countBadge = document.getElementById('queue-count-badge');
  const statusFilter = document.getElementById('queue-status-filter')?.value || '';

  if (listEl) listEl.innerHTML = `<p style="color: var(--text-muted); font-size: 0.85rem; padding: 0.75rem;">Loading review queue...</p>`;

  try {
    const url = `/api/review/queue${statusFilter ? '?status=' + statusFilter : ''}`;
    const res = await apiFetch(url);
    if (!res.ok) {
      if (listEl) {
        if (res.status === 401) {
          listEl.innerHTML = `
            <div style="text-align: center; padding: 2rem 1rem;">
              <p style="font-weight: 700; color: var(--navy-primary); font-size: 0.95rem;">Session Expired or Login Required</p>
              <p style="font-size: 0.825rem; color: var(--text-muted); margin: 0.35rem 0 1rem 0;">Please authenticate with a qualified Advocate or Supervisor account to access the review queue.</p>
              <button class="btn btn-primary btn-sm" onclick="openLoginModal()">Sign In</button>
            </div>
          `;
        } else {
          listEl.innerHTML = `
            <div style="padding: 1rem; color: var(--error);">
              <p style="font-weight: 600; font-size: 0.875rem;">Failed to load queue (${res.status})</p>
              <p style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.25rem;">The server encountered an issue retrieving documents.</p>
              <button class="btn btn-secondary btn-sm" style="margin-top: 0.5rem;" onclick="loadWorkbenchQueue()">Retry</button>
            </div>
          `;
        }
      }
      return;
    }
    const data = await res.json();
    if (countBadge) countBadge.textContent = `${data.count} Documents`;

    // Update summary metrics
    const reviews = data.reviews || [];
    updateWorkbenchSummaryMetrics(reviews);

    if (reviews.length === 0) {
      if (listEl) {
        listEl.innerHTML = `
          <div style="text-align: center; padding: 2rem 1rem;">
            <img src="/static/img/empty_contracts.svg" alt="No reviews" style="width: 64px; height: auto; opacity: 0.6; margin-bottom: 0.5rem;" />
            <p style="font-weight: 600; color: var(--navy-primary); font-size: 0.9rem;">No reviews matching filter</p>
            <p style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.2rem;">All assigned contracts are currently up to date.</p>
          </div>
        `;
      }
      return;
    }

    if (listEl) {
      listEl.innerHTML = reviews.map(r => `
        <div class="clause-item ${AppState.currentWorkbenchReviewId === r.review_id ? 'selected' : ''}" onclick="openWorkbenchReview('${r.review_id}')">
          <div class="clause-header-row">
            <span class="clause-title">${escapeHtml(r.filename)}</span>
            <span class="badge ${getStatusBadgeClass(r.status)}">${r.status}</span>
          </div>
          <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.2rem;">
            Doc Version: <strong>v${r.document_version}</strong> &bull; Lawyer: <strong>${r.assigned_lawyer ? escapeHtml(r.assigned_lawyer.name) : '<span style="color: var(--warning)">Unassigned</span>'}</strong>
          </div>
        </div>
      `).join('');
    }

    // Auto-open first review if none selected
    if (!AppState.currentWorkbenchReviewId && reviews.length > 0) {
      openWorkbenchReview(reviews[0].review_id);
    }
  } catch (err) {
    if (listEl) listEl.innerHTML = `<p style="color: var(--error); font-size: 0.85rem;">Error: ${err}</p>`;
  }
}

function updateWorkbenchSummaryMetrics(reviews) {
  const assigned = reviews.filter(r => r.status === 'ASSIGNED' || r.status === 'IN_REVIEW').length;
  const completed = reviews.filter(r => r.status === 'REVIEW_COMPLETED').length;
  const revisions = reviews.filter(r => r.status === 'REVISION_REQUESTED').length;

  const elAssigned = document.getElementById('stat-assigned-count');
  const elCompleted = document.getElementById('stat-completed-count');
  const elAction = document.getElementById('stat-action-count');

  if (elAssigned) elAssigned.textContent = assigned;
  if (elCompleted) elCompleted.textContent = completed;
  if (elAction) elAction.textContent = revisions;
}

async function openWorkbenchReview(reviewId) {
  AppState.currentWorkbenchReviewId = reviewId;
  const headerCard = document.getElementById('wb-doc-header-card');
  const contentGrid = document.getElementById('wb-content-grid');
  const commentsCard = document.getElementById('wb-comments-card');

  // Highlight active queue item
  document.querySelectorAll('#workbench-queue-list .clause-item').forEach(el => el.classList.remove('selected'));

  try {
    const res = await apiFetch(`/api/review/${reviewId}`);
    if (!res.ok) return;
    const data = await res.json();
    AppState.currentReviewData = data;

    if (headerCard) headerCard.style.display = 'block';
    if (contentGrid) contentGrid.style.display = 'grid';
    if (commentsCard) commentsCard.style.display = 'block';

    const titleEl = document.getElementById('wb-doc-title');
    const statusBadge = document.getElementById('wb-doc-status-badge');
    const versionEl = document.getElementById('wb-doc-version');
    const lawyerEl = document.getElementById('wb-doc-lawyer');

    if (titleEl) titleEl.textContent = data.document ? data.document.filename : 'Contract Review';
    if (statusBadge) {
      statusBadge.textContent = data.review.status;
      statusBadge.className = 'badge ' + getStatusBadgeClass(data.review.status);
    }
    if (versionEl) versionEl.textContent = `Version ${data.review.version}`;
    if (lawyerEl) {
      const advocate = data.review.assigned_lawyer;
      lawyerEl.textContent = advocate ? `Assigned Advocate: ${advocate.name} (${advocate.advocate_status})` : 'Advocate: Unassigned';
    }

    // Render Clauses
    const clauseBadge = document.getElementById('clause-count-badge');
    if (clauseBadge) clauseBadge.textContent = `${data.segments.length} Clauses`;

    const clauseListEl = document.getElementById('wb-clause-list');
    if (clauseListEl) {
      clauseListEl.innerHTML = data.segments.map((seg, idx) => `
        <div class="clause-item" id="seg-item-${seg.segment_id}" onclick="selectClause('${seg.segment_id}')">
          <div class="clause-header-row">
            <span class="clause-title">${escapeHtml(seg.heading || 'Clause ' + (idx + 1))}</span>
            <span class="code-pill">#${seg.sequence + 1}</span>
          </div>
          <div class="clause-snippet">${escapeHtml(seg.text)}</div>
        </div>
      `).join('');
    }

    // Auto-select first clause
    if (data.segments.length > 0) {
      selectClause(data.segments[0].segment_id);
    }

    // Comments & Clarifications
    renderComments(data.comments || []);

    // Final Reports Panel
    loadWorkbenchReports(reviewId, data.document ? data.document.id : null, data.review.status);
  } catch (err) {
    console.error("Error opening review:", err);
  }
}

async function triggerWorkbenchScreening() {
  if (!AppState.currentWorkbenchReviewId) {
    alert("Please select a contract review first.");
    return;
  }
  const btn = document.getElementById('wb-screen-btn');
  const origHtml = btn ? btn.innerHTML : 'Re-screen with AI';
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '&#9203; Running Core NLP...';
  }
  try {
    const res = await apiFetch(`/api/review/${AppState.currentWorkbenchReviewId}/screen`, {
      method: 'POST'
    });
    if (res.ok) {
      const data = await res.json();
      await openWorkbenchReview(AppState.currentWorkbenchReviewId);
    } else {
      const err = await res.json().catch(() => ({}));
      alert(`Screening could not be completed: ${err.error || res.statusText}`);
    }
  } catch (err) {
    console.error("Screening error:", err);
    alert(`Screening error: ${err.message}`);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = origHtml;
    }
  }
}

function getQualityBadgeClass(quality) {
  switch (quality) {
    case 'TRACEABLE': return 'badge-traceable';
    case 'PARTIAL': return 'badge-partial';
    case 'INSUFFICIENT': return 'badge-insufficient';
    case 'SOURCE_UNVERIFIED': return 'badge-unverified';
    case 'STALE_EVIDENCE': return 'badge-stale';
    case 'NO_MATCHING_EVIDENCE': return 'badge-no-evidence';
    default: return 'badge-neutral';
  }
}

function renderModelAttribution(modelAttrib) {
  if (!modelAttrib) {
    return `<p style="font-size: 0.8rem; color: var(--text-muted); font-style: italic;">Model explanation spans unavailable for this clause.</p>`;
  }
  const spans = modelAttrib.attributed_spans || modelAttrib.evidence_spans || [];
  if (spans.length === 0) {
    return `<p style="font-size: 0.8rem; color: var(--text-muted); font-style: italic;">No specific token spans exceeded attribution salience threshold.</p>`;
  }
  return `
    <div style="margin-bottom: 0.35rem;">
      <span style="font-size: 0.775rem; color: var(--text-muted);">Model-attributed text spans (Gradient &times; Input sensitivity):</span>
      <div style="margin-top: 0.25rem;">
        ${spans.map(s => `
          <span class="attribution-chip" title="Raw Attribution Score: ${s.raw_score}">
            &ldquo;${escapeHtml(s.text || '')}&rdquo; <span style="color: var(--blue-secondary); font-size: 0.7rem; font-weight: 600;">(${roundScore(s.raw_score)})</span>
          </span>
        `).join('')}
      </div>
    </div>
  `;
}

function roundScore(val) {
  const num = parseFloat(val);
  return isNaN(num) ? '0.000' : num.toFixed(3);
}

function renderPassages(passages) {
  if (!passages || passages.length === 0) {
    return `<p style="font-size: 0.825rem; color: var(--text-muted); font-style: italic;">No matching statutory extracts retrieved for this clause.</p>`;
  }
  return passages.map(p => `
    <div class="evidence-card" style="margin-bottom: 0.5rem; padding: 0.65rem; border: 1px solid var(--border-color); border-radius: var(--radius-xs); background: #fafbfc;">
      <div class="evidence-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.3rem;">
        <span class="evidence-title" style="font-weight: 700; color: var(--navy-primary); font-size: 0.825rem;">
          ${escapeHtml(p.statute_title)} &mdash; Section ${escapeHtml(p.section_number)}
        </span>
        <span class="badge ${p.is_verified_law ? 'badge-success' : 'badge-warning'}" style="font-size: 0.7rem;">${escapeHtml(p.legal_status)}</span>
      </div>
      <div class="evidence-passage" style="font-size: 0.8rem; font-style: italic; color: var(--text-secondary); margin-bottom: 0.35rem; line-height: 1.4;">
        &ldquo;${escapeHtml(p.passage_text)}&rdquo;
      </div>
      <div class="evidence-meta" style="font-size: 0.75rem; color: var(--text-muted); display: flex; justify-content: space-between; flex-wrap: wrap; gap: 0.5rem; border-top: 1px dashed var(--border-color); padding-top: 0.25rem;">
        <span>BM25 Relevance: <strong>${p.ranking_score}</strong> (${escapeHtml(p.retrieval_method || 'BM25')})</span>
        <span>Checksum: <span class="code-pill">${p.source_checksum ? escapeHtml(p.source_checksum.substring(0, 10)) + '...' : 'SHA-256 Verified'}</span></span>
      </div>
    </div>
  `).join('');
}

async function selectClause(segmentId) {
  AppState.currentSelectedSegmentId = segmentId;

  document.querySelectorAll('#wb-clause-list .clause-item').forEach(el => el.classList.remove('selected'));
  const activeEl = document.getElementById('seg-item-' + segmentId);
  if (activeEl) activeEl.classList.add('selected');

  const panel = document.getElementById('wb-evidence-panel');
  const decisionContainer = document.getElementById('wb-decision-form-container');
  const evidenceStatusBadge = document.getElementById('evidence-status-badge');

  if (panel) panel.innerHTML = `<p style="color: var(--text-muted); font-size: 0.85rem; padding: 1rem;">Retrieving grounded Indian statutory evidence...</p>`;

  const seg = (AppState.currentReviewData?.segments || []).find(s => s.segment_id === segmentId);
  const finding = (AppState.currentReviewData?.findings || []).find(f => f.segment_id === segmentId);

  // Pre-populate decision form if previous decision exists
  if (finding) {
    if (document.getElementById('wb-decision-type')) {
      document.getElementById('wb-decision-type').value = finding.decision || 'ACCEPT_AI_OBSERVATION';
    }
    if (document.getElementById('wb-decision-rationale')) {
      document.getElementById('wb-decision-rationale').value = finding.lawyer_rationale || '';
    }
    if (document.getElementById('wb-decision-notes')) {
      document.getElementById('wb-decision-notes').value = finding.lawyer_notes || '';
    }
    if (document.getElementById('wb-disclose-check')) {
      document.getElementById('wb-disclose-check').checked = !!finding.is_disclosed_to_client;
    }
  }

  try {
    const res = await apiFetch(`/api/review/${AppState.currentWorkbenchReviewId}/evidence/${segmentId}`);
    const data = await res.json();
    AppState.currentClauseEvidence = data;

    if (decisionContainer) decisionContainer.style.display = 'block';

    const quality = data.evidence_quality_status || (finding?.evidence_quality_status || 'NO_MATCHING_EVIDENCE');

    if (evidenceStatusBadge) {
      evidenceStatusBadge.textContent = quality;
      evidenceStatusBadge.className = 'badge ' + getQualityBadgeClass(quality);
    }

    if (!panel) return;

    panel.innerHTML = `
      <!-- 1. CONTRACT CLAUSE -->
      <div class="grounded-section">
        <div class="grounded-section-header">
          <span>1. CONTRACT CLAUSE (${escapeHtml(seg?.heading || 'Clause Segment')})</span>
          <span class="code-pill">Sequence #${(seg?.sequence ?? 0) + 1} &bull; Offsets [${seg?.original_start ?? 0}:${seg?.original_end ?? 0}] &bull; Doc v${AppState.currentReviewData?.review?.version || 1}</span>
        </div>
        <div class="grounded-section-body" style="font-style: italic; background: #fdfdfd;">
          &ldquo;${escapeHtml(seg?.text || 'No text content available.')}&rdquo;
        </div>
      </div>

      <!-- 2. AI OBSERVATION -->
      <div class="grounded-section">
        <div class="grounded-section-header">
          <span style="color: var(--navy-primary);"><span class="badge badge-info" style="margin-right: 0.35rem;">AI OBSERVATION</span> Preliminary Statistical Finding</span>
          <span class="code-pill">${escapeHtml(finding?.risk_label || 'OBSERVATION_LABEL')}</span>
        </div>
        <div class="grounded-section-body">
          ${finding?.ai_observation ? `<p style="margin-bottom: 0.5rem; color: var(--navy-primary); font-weight: 500;">${escapeHtml(finding.ai_observation)}</p>` : `<p style="color: var(--text-muted); font-style: italic;">No preliminary AI risk observation recorded for this segment.</p>`}
          <div style="font-size: 0.775rem; color: var(--text-muted); border-top: 1px dashed var(--border-color); padding-top: 0.4rem; display: flex; flex-wrap: wrap; gap: 0.75rem;">
            <span>Model: <strong>${escapeHtml(finding?.ai_metadata?.model_name || 'legalbert-base-uncased')} (v${escapeHtml(finding?.ai_metadata?.model_version || '1.0.0')})</strong></span>
            <span>Raw Score: <strong>${escapeHtml(finding?.ai_confidence_score || 'N/A')}</strong></span>
            <span>Calibrated Threshold: <strong>&tau;* = ${finding?.ai_metadata?.calibrated_threshold || 0.04}</strong></span>
          </div>
          <p style="font-size: 0.725rem; color: var(--slate-500); margin-top: 0.35rem;">
            <em>Notice: Automated model output represents statistical association. It is NOT legal advice, a validated opinion, or an authoritative determination.</em>
          </p>
        </div>
      </div>

      <!-- 3. MODEL EXPLANATION -->
      <div class="grounded-section">
        <div class="grounded-section-header">
          <span><span class="badge badge-neutral" style="margin-right: 0.35rem;">MODEL EXPLANATION</span> Model-Attributed Text Spans</span>
          <span class="code-pill">${escapeHtml(finding?.model_attribution?.method || 'GradientXInput')}</span>
        </div>
        <div class="grounded-section-body">
          ${renderModelAttribution(finding?.model_attribution)}
          <p style="font-size: 0.725rem; color: var(--slate-500); margin-top: 0.35rem;">
            <em>Research limitation: Gradient &times; Input highlights token sensitivity and may exhibit bias toward frequent function words. Does not establish legal importance or causal reasoning.</em>
          </p>
        </div>
      </div>

      <!-- 4. RETRIEVED SOURCE EVIDENCE -->
      <div class="grounded-section">
        <div class="grounded-section-header">
          <span><span class="badge badge-success" style="margin-right: 0.35rem;">RETRIEVED SOURCE EVIDENCE</span> Authoritative Statutory Extracts</span>
          <span class="badge ${getQualityBadgeClass(quality)}">${escapeHtml(quality)}</span>
        </div>
        <div class="grounded-section-body">
          ${renderPassages(data.passages)}
        </div>
      </div>

      <!-- 5. EVIDENCE LIMITATIONS & ABSTENTION -->
      <div class="grounded-section">
        <div class="grounded-section-header">
          <span><span class="badge badge-warning" style="margin-right: 0.35rem;">EVIDENCE LIMITATION</span> Scope &amp; Score Semantics</span>
        </div>
        <div class="grounded-section-body" style="font-size: 0.775rem; color: var(--text-secondary);">
          <p style="margin-bottom: 0.35rem;"><strong>Corpus Scope:</strong> ${escapeHtml(data.corpus_disclosure || 'Curated extracts of 6 central commercial statutes.')}</p>
          <p style="margin-bottom: 0.35rem;"><strong>Score Semantics:</strong> ${escapeHtml(data.score_disclaimer || '')}</p>
          ${data.status === 'ABSTAIN' ? `<div class="banner banner-warning" style="margin-top: 0.5rem; padding: 0.4rem 0.6rem;">Statutory Abstention: <strong>${escapeHtml(data.abstention_reason || 'INSUFFICIENT_EVIDENCE')}</strong>. System abstained from presenting weak matches as legal authority.</div>` : ''}
        </div>
      </div>

      <!-- 6 & 7. LAWYER DETERMINATION & RATIONALE -->
      ${finding && finding.decision ? `
        <div class="grounded-section" style="border-left: 3px solid var(--navy-primary);">
          <div class="grounded-section-header" style="background: #f8fafc;">
            <span><span class="badge badge-secondary" style="margin-right: 0.35rem;">LAWYER DETERMINATION</span> Current Evaluation</span>
            <span class="badge ${getStatusBadgeClass(finding.decision)}">${escapeHtml(finding.decision)}</span>
          </div>
          <div class="grounded-section-body">
            <p style="margin-bottom: 0.25rem;"><strong>Advocate Rationale:</strong> ${escapeHtml(finding.lawyer_rationale || 'N/A')}</p>
            ${finding.lawyer_notes ? `<p style="font-size: 0.775rem; color: var(--text-muted); margin-top: 0.25rem;"><em>&#128274; Confidential internal note on file.</em></p>` : ''}
            <p style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.35rem;">Recorded in Document v${finding.document_version} &bull; Disclosed to client: <strong>${finding.is_disclosed_to_client ? 'Yes' : 'No'}</strong></p>
          </div>
        </div>
      ` : `
        <div style="font-size: 0.8rem; color: var(--text-muted); padding: 0.25rem 0 0.5rem 0;">
          <em>No independent lawyer determination recorded for this clause yet. Review evidence and record below:</em>
        </div>
      `}
    `;

  } catch (err) {
    if (panel) panel.innerHTML = `<p style="color: var(--error); font-size: 0.85rem;">Error loading evidence: ${err}</p>`;
  }
}

async function submitLawyerDecision() {
  if (!AppState.currentWorkbenchReviewId || !AppState.currentSelectedSegmentId) {
    alert("Please select a contract clause before recording a decision.");
    return;
  }

  const decision = document.getElementById('wb-decision-type').value;
  const rationale = document.getElementById('wb-decision-rationale').value.trim();
  const notes = document.getElementById('wb-decision-notes').value.trim();
  const isDisclosed = document.getElementById('wb-disclose-check').checked;

  if (!rationale) {
    alert("Mandatory Field: Substantive lawyer rationale is required before recording a decision.");
    document.getElementById('wb-decision-rationale').focus();
    return;
  }

  const finding = (AppState.currentReviewData?.findings || []).find(f => f.segment_id === AppState.currentSelectedSegmentId);
  const evidenceData = AppState.currentClauseEvidence;

  try {
    const res = await apiFetch(`/api/review/${AppState.currentWorkbenchReviewId}/decision`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        segment_id: AppState.currentSelectedSegmentId,
        decision: decision,
        rationale: rationale,
        notes: notes,
        is_disclosed_to_client: isDisclosed,
        statutory_evidence: evidenceData,
        evidence_quality_status: evidenceData?.evidence_quality_status || 'TRACEABLE',
        ai_metadata: finding?.ai_metadata,
        model_attribution: finding?.model_attribution
      })
    });
    const resp = await res.json();
    if (res.ok) {
      alert("Advocate decision recorded successfully.");
      openWorkbenchReview(AppState.currentWorkbenchReviewId);
    } else {
      alert("Error recording decision: " + (resp.error || "Request failed"));
    }
  } catch (err) {
    alert("Network error: " + err);
  }
}

function renderComments(comments) {
  const thread = document.getElementById('wb-comment-thread');
  const countBadge = document.getElementById('comment-count-badge');
  if (countBadge) countBadge.textContent = `${comments.length} Comments`;

  if (!thread) return;
  if (comments.length === 0) {
    thread.innerHTML = `<p style="font-size: 0.8rem; color: var(--text-muted); padding: 0.5rem 0;">No communications or clarifications recorded.</p>`;
    return;
  }

  thread.innerHTML = comments.map(c => `
    <div style="padding: 0.6rem 0.75rem; border-bottom: 1px solid var(--border-color); font-size: 0.85rem;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.2rem;">
        <span style="font-weight: 600; color: var(--navy-primary);">${escapeHtml(c.author_name)} <span class="badge badge-info" style="font-size: 0.65rem;">${c.visibility}</span></span>
        <span style="font-size: 0.75rem; color: var(--text-muted);">${c.created_at.substring(0, 10)}</span>
      </div>
      <div style="color: var(--text-secondary); line-height: 1.4;">${escapeHtml(c.comment_text)}</div>
    </div>
  `).join('');
}

async function postWorkbenchComment() {
  if (!AppState.currentWorkbenchReviewId) return;
  const textInput = document.getElementById('wb-comment-input');
  const text = textInput ? textInput.value.trim() : '';
  const vis = document.getElementById('wb-comment-vis').value;

  if (!text) return;

  try {
    const res = await apiFetch(`/api/review/${AppState.currentWorkbenchReviewId}/comment`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        comment_text: text,
        visibility: vis,
        segment_id: AppState.currentSelectedSegmentId
      })
    });
    if (res.ok) {
      textInput.value = '';
      openWorkbenchReview(AppState.currentWorkbenchReviewId);
    }
  } catch (err) {
    alert("Error posting comment: " + err);
  }
}

// =============================================================================
// TASK 034: REPORTS & FEEDBACK
// =============================================================================

async function loadWorkbenchReports(reviewId, docId, reviewStatus) {
  AppState.currentWorkbenchDocId = docId;
  const badge = document.getElementById('wb-report-status-badge');
  const genBtn = document.getElementById('wb-generate-report-btn');

  if (reviewStatus === 'REVIEW_COMPLETED') {
    if (badge) {
      badge.textContent = 'Eligible for Final Report';
      badge.className = 'badge badge-success';
    }
    if (genBtn) genBtn.disabled = false;
  } else {
    if (badge) {
      badge.textContent = `Ineligible (${reviewStatus})`;
      badge.className = 'badge badge-warning';
    }
    if (genBtn) genBtn.disabled = true;
  }

  if (!docId) return;
  try {
    const res = await apiFetch(`/api/reports/document/${docId}`);
    if (!res.ok) return;
    const data = await res.json();
    const histDiv = document.getElementById('wb-reports-history');

    if (!data.reports || data.reports.length === 0) {
      if (histDiv) histDiv.innerHTML = `<p style="font-size: 0.8rem; color: var(--text-muted); padding: 0.5rem 0;">No final reports issued for this contract yet.</p>`;
      return;
    }

    if (histDiv) {
      histDiv.innerHTML = data.reports.map(r => `
        <div style="padding: 0.75rem; border: 1px solid var(--border-color); border-radius: var(--radius-sm); margin-bottom: 0.5rem; background: var(--bg-card-subtle);">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <strong>${escapeHtml(r.report_number)}</strong>
            <span class="badge ${r.status === 'FINAL' ? 'badge-success' : 'badge-warning'}">${r.status}</span>
          </div>
          <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.25rem;">
            Generated: ${r.generated_at} | Version ${r.report_version}
          </div>
          <div style="margin-top: 0.5rem;">
            <a href="/api/reports/${r.report_id}/pdf" target="_blank" class="btn btn-secondary btn-sm">
              Download PDF Report
            </a>
          </div>
        </div>
      `).join('');
    }

    const activeRep = data.reports.find(r => r.status === 'FINAL') || data.reports[0];
    if (activeRep) {
      loadReportFeedbackForWorkbench(activeRep.report_id);
    }
  } catch (err) {
    console.error("Error loading reports history:", err);
  }
}

async function generateFinalReport() {
  if (!AppState.currentWorkbenchReviewId) return;
  try {
    const res = await apiFetch(`/api/reports/generate/${AppState.currentWorkbenchReviewId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ export_pdf: true })
    });
    const data = await res.json();
    if (!res.ok) {
      alert('Report generation rejected: ' + (data.error || 'Server error'));
      return;
    }
    alert('Final Lawyer-Reviewed Report ' + data.report_number + ' generated successfully!');
    if (AppState.currentWorkbenchDocId) {
      loadWorkbenchReports(AppState.currentWorkbenchReviewId, AppState.currentWorkbenchDocId, 'REVIEW_COMPLETED');
    }
  } catch (e) {
    alert('Error generating report: ' + e);
  }
}

async function previewDraftReport() {
  if (!AppState.currentWorkbenchReviewId) {
    showToast('Please select a contract review first.', 'warning');
    return;
  }
  const contentEl = document.getElementById('draft-report-content');
  if (contentEl) {
    contentEl.innerHTML = `<div style="text-align:center; padding: 2rem; color: var(--text-muted);">Generating draft report preview...</div>`;
  }
  openDraftReportModal();

  try {
    const res = await apiFetch(`/api/reports/preview/${AppState.currentWorkbenchReviewId}`);
    const data = await res.json();
    if (!res.ok) {
      if (contentEl) {
        contentEl.innerHTML = `
          <div class="banner banner-error">
            <strong>Draft Preview Unavailable:</strong> ${escapeHtml(data.error || 'Unable to generate preview')}
          </div>
        `;
      }
      return;
    }

    const preview = data.preview || data;
    const meta = preview.metadata || {};
    const exec = preview.executive_summary || {};
    const findings = preview.findings || [];

    if (contentEl) {
      contentEl.innerHTML = `
        <div style="border-bottom: 2px solid var(--gold-accent); padding-bottom: 0.75rem; margin-bottom: 1rem; display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 0.5rem;">
          <div>
            <div style="font-size: 0.75rem; color: var(--gold-hover); font-weight: 700; text-transform: uppercase; letter-spacing: 1px;">
              ${escapeHtml(data.notice || 'DRAFT PREVIEW — NOT A FINAL LAWYER REPORT')}
            </div>
            <h3 style="color: var(--navy-primary); font-size: 1.25rem; font-weight: 800; margin-top: 0.25rem;">
              ${escapeHtml(meta.contract_title || 'Legal Analysis Report')}
            </h3>
            <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.25rem;">
              Contract ID: ${escapeHtml(meta.contract_id || 'N/A')} &bull; Version: ${meta.document_version || 1} &bull; Generated: ${escapeHtml(meta.generated_at || 'Just now')}
            </div>
          </div>
          <div style="text-align: right;">
            <span class="badge badge-warning">DRAFT WATERMARK</span>
          </div>
        </div>

        <div class="banner banner-warning" style="margin-bottom: 1rem; font-size: 0.8rem;">
          <div>
            <strong>Preliminary Draft Notice:</strong> This unfinalized draft is generated for internal legal review. It has not received final advocate sign-off and does not constitute a completed legal assessment under the Advocates Act, 1961.
          </div>
        </div>

        <div style="background: var(--bg-card); border: 1px solid var(--border-color); border-radius: var(--radius-md); padding: 1rem; margin-bottom: 1rem;">
          <h4 style="font-size: 0.95rem; font-weight: 700; color: var(--navy-primary); margin-bottom: 0.5rem;">Executive Summary</h4>
          <p style="font-size: 0.85rem; color: var(--text-secondary); line-height: 1.6;">
            ${escapeHtml(exec.review_summary || 'No review summary entered yet.')}
          </p>
          <div style="display: flex; gap: 1.5rem; margin-top: 0.75rem; font-size: 0.8rem; color: var(--text-muted); flex-wrap: wrap;">
            <div>Total Evaluated Findings: <strong>${exec.total_findings || findings.length}</strong></div>
            <div>Reviewing Advocate: <strong>${escapeHtml(meta.reviewing_advocate?.full_name || 'Assigned Advocate')}</strong></div>
          </div>
        </div>

        <h4 style="font-size: 0.95rem; font-weight: 700; color: var(--navy-primary); margin-bottom: 0.75rem;">Disclosed Findings Preview (${findings.length})</h4>
        ${findings.length === 0 ? '<p style="font-size: 0.85rem; color: var(--text-muted); padding: 0.5rem 0;">No findings disclosed for inclusion in final report.</p>' : findings.map(f => `
          <div style="background: var(--bg-card); border: 1px solid var(--border-color); border-left: 3px solid var(--navy-primary); border-radius: var(--radius-sm); padding: 0.75rem 1rem; margin-bottom: 0.65rem;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <strong style="color: var(--navy-primary); font-size: 0.9rem;">${escapeHtml(f.risk_label || 'Finding')}</strong>
              <span class="code-pill">${escapeHtml(f.decision || 'EVALUATED')}</span>
            </div>
            <p style="font-size: 0.825rem; color: var(--text-secondary); margin: 0.35rem 0;">${escapeHtml(f.observation || f.ai_observation || '')}</p>
            <div style="font-size: 0.8rem; color: var(--success); font-weight: 600;">
              Advocate Rationale: ${escapeHtml(f.rationale || f.lawyer_rationale || 'Reviewed and confirmed')}
            </div>
          </div>
        `).join('')}
      `;
    }
  } catch (err) {
    if (contentEl) {
      contentEl.innerHTML = `<div class="banner banner-error">Network error retrieving draft preview: ${escapeHtml(String(err))}</div>`;
    }
  }
}

async function loadReportFeedbackForWorkbench(reportId) {
  try {
    const res = await apiFetch(`/api/reports/${reportId}/feedback`);
    if (!res.ok) return;
    const data = await res.json();
    const fbDiv = document.getElementById('wb-feedback-list');

    if (!data.feedback || data.feedback.length === 0) {
      if (fbDiv) fbDiv.innerHTML = `<p style="font-size: 0.8rem; color: var(--text-muted); padding: 0.5rem 0;">No client feedback submitted yet.</p>`;
      return;
    }

    if (fbDiv) {
      fbDiv.innerHTML = data.feedback.map(fb => `
        <div style="padding: 0.75rem; border: 1px solid var(--border-color); border-radius: var(--radius-sm); margin-bottom: 0.65rem; background: var(--bg-card-subtle);">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <span style="font-weight: 600; color: var(--navy-primary);">${escapeHtml(fb.client_name)} &bull; <span class="badge badge-info">${fb.status}</span></span>
            <span style="font-size: 0.8rem; color: var(--warning); font-weight: 600;">Overall: ${fb.overall_satisfaction}/5 | Clarity: ${fb.clarity_rating}/5</span>
          </div>
          ${fb.client_comments ? `<p style="font-size: 0.825rem; color: var(--text-secondary); margin-top: 0.35rem; font-style: italic;">&ldquo;${escapeHtml(fb.client_comments)}&rdquo;</p>` : ''}
          ${fb.needs_clarification ? `<div style="color: var(--error); font-size: 0.775rem; font-weight: 600; margin-top: 0.25rem;">&#9888; Client flagged clarification required</div>` : ''}

          <!-- Responses -->
          <div style="margin-top: 0.5rem; padding-left: 0.75rem; border-left: 3px solid var(--blue-secondary);">
            ${(fb.responses || []).map(r => `
              <div style="font-size: 0.775rem; color: var(--text-secondary); margin-bottom: 0.25rem;">
                <strong>${escapeHtml(r.responder_name)} (${r.responder_role}):</strong> ${escapeHtml(r.response_text)}
              </div>
            `).join('')}
          </div>

          <div style="display: flex; gap: 0.4rem; margin-top: 0.5rem;">
            <input type="text" id="wb-fb-reply-${fb.feedback_id}" class="form-control" style="font-size: 0.8rem; padding: 0.25rem 0.5rem;" placeholder="Reply to client feedback...">
            <button class="btn btn-secondary btn-sm" onclick="postFeedbackResponse('${fb.feedback_id}')">Reply</button>
            <button class="btn btn-secondary btn-sm" onclick="setFeedbackStatus('${fb.feedback_id}', 'ACKNOWLEDGED')">Acknowledge</button>
            <button class="btn btn-secondary btn-sm" onclick="setFeedbackStatus('${fb.feedback_id}', 'CLOSED')">Close</button>
          </div>
        </div>
      `).join('');
    }
  } catch (e) {
    console.error("Error loading feedback for workbench:", e);
  }
}

async function postFeedbackResponse(feedbackId) {
  const input = document.getElementById('wb-fb-reply-' + feedbackId);
  if (!input || !input.value.trim()) return;

  try {
    const res = await apiFetch(`/api/reports/feedback/${feedbackId}/respond`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        response_text: input.value.trim(),
        is_client_visible: true
      })
    });
    if (res.ok) {
      input.value = '';
      if (AppState.currentWorkbenchReviewId && AppState.currentWorkbenchDocId) {
        loadWorkbenchReports(AppState.currentWorkbenchReviewId, AppState.currentWorkbenchDocId, 'REVIEW_COMPLETED');
      }
    } else {
      const err = await res.json();
      alert('Error: ' + err.error);
    }
  } catch (err) {
    alert('Error responding to feedback: ' + err);
  }
}

async function setFeedbackStatus(feedbackId, newStatus) {
  try {
    const res = await apiFetch(`/api/reports/feedback/${feedbackId}/status`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: newStatus })
    });
    if (res.ok) {
      if (AppState.currentWorkbenchReviewId && AppState.currentWorkbenchDocId) {
        loadWorkbenchReports(AppState.currentWorkbenchReviewId, AppState.currentWorkbenchDocId, 'REVIEW_COMPLETED');
      }
    } else {
      const err = await res.json();
      alert('Error: ' + err.error);
    }
  } catch (err) {
    alert('Error updating feedback status: ' + err);
  }
}

// =============================================================================
// CLIENT WORKSPACE WORKFLOW
// =============================================================================

async function loadClientWorkspace() {
  const listEl = document.getElementById('client-contract-list');
  const countBadge = document.getElementById('client-contract-count');

  if (listEl) listEl.innerHTML = `<p style="font-size: 0.85rem; color: var(--text-muted); padding: 1rem;">Loading your contract portfolio...</p>`;

  try {
    const res = await apiFetch('/api/review/queue');
    if (!res.ok) return;
    const data = await res.json();
    if (countBadge) countBadge.textContent = `${data.count} Contracts`;

    const reviews = data.reviews || [];
    if (reviews.length === 0) {
      if (listEl) {
        listEl.innerHTML = `
          <div style="text-align: center; padding: 2rem 1rem;">
            <img src="/static/img/empty_contracts.svg" alt="No contracts" style="width: 72px; height: auto; opacity: 0.7; margin-bottom: 0.75rem;" />
            <p style="font-weight: 700; color: var(--navy-primary); font-size: 0.95rem;">No Contracts Uploaded</p>
            <p style="font-size: 0.825rem; color: var(--text-muted); margin: 0.35rem 0 1rem 0;">Upload your first commercial contract to begin AI screening and verified advocate review.</p>
            <button class="btn btn-primary btn-sm" onclick="openModal('upload-modal')">Upload New Contract</button>
          </div>
        `;
      }
      return;
    }

    if (listEl) {
      listEl.innerHTML = reviews.map(r => `
        <div class="clause-item" onclick="openClientDocumentView('${r.review_id}')">
          <div class="clause-header-row">
            <span class="clause-title">${escapeHtml(r.filename)}</span>
            <span class="badge ${getStatusBadgeClass(r.status)}">${getClientStatusLabel(r.status)}</span>
          </div>
          <div style="font-size: 0.775rem; color: var(--text-muted); margin-top: 0.25rem;">
            Reviewing Advocate: <strong>${r.assigned_lawyer ? escapeHtml(r.assigned_lawyer.name) : 'Pending assignment'}</strong>
          </div>
        </div>
      `).join('');
    }

    // Auto-open first
    if (reviews.length > 0) {
      openClientDocumentView(reviews[0].review_id);
    }
  } catch (err) {
    if (listEl) listEl.innerHTML = `<p style="color: var(--error); font-size: 0.85rem;">Error loading contracts: ${err}</p>`;
  }
}

async function openClientDocumentView(reviewId) {
  AppState.currentClientActiveReviewId = reviewId;
  const detailsCard = document.getElementById('client-doc-details');
  try {
    const res = await apiFetch(`/api/review/${reviewId}`);
    if (!res.ok) return;
    const data = await res.json();

    if (detailsCard) detailsCard.style.display = 'block';

    const titleEl = document.getElementById('client-doc-title');
    const statusEl = document.getElementById('client-doc-status');
    const lawyerEl = document.getElementById('client-doc-lawyer');

    if (titleEl) titleEl.textContent = data.document ? data.document.filename : 'Contract Review';
    if (statusEl) {
      statusEl.textContent = getClientStatusLabel(data.review.status);
      statusEl.className = 'badge ' + getStatusBadgeClass(data.review.status);
    }
    if (lawyerEl) {
      lawyerEl.textContent = data.review.assigned_lawyer ? `Reviewing Advocate: ${data.review.assigned_lawyer.name}` : 'Reviewing Advocate: Pending Assignment';
    }

    // Approved Disclosed Findings
    const findingsDiv = document.getElementById('client-approved-findings');
    const findings = data.findings || [];
    if (findings.length === 0) {
      if (findingsDiv) findingsDiv.innerHTML = `<p style="font-size: 0.85rem; color: var(--text-muted); padding: 0.5rem 0;">No approved findings released to client workspace yet.</p>`;
    } else {
        findingsDiv.innerHTML = findings.map(f => {
          const seg = (data.segments || []).find(s => s.segment_id === f.segment_id);
          const statRefs = f.statutory_evidence?.passages || (Array.isArray(f.statutory_evidence) ? f.statutory_evidence : []);
          return `
            <div style="padding: 1rem; border: 1px solid var(--border-color); border-radius: var(--radius-md); margin-bottom: 0.75rem; background: var(--bg-card);">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.4rem; flex-wrap: wrap; gap: 0.5rem;">
                <span style="font-weight: 700; font-size: 0.9rem; color: var(--navy-primary);">
                  ${escapeHtml(seg?.heading || f.risk_label || 'Clause Finding')}
                </span>
                <span class="badge ${getStatusBadgeClass(f.decision)}">${escapeHtml(f.decision || 'REVIEWED')}</span>
              </div>
              ${seg?.text ? `
                <div style="font-size: 0.825rem; font-style: italic; color: var(--text-secondary); background: #fafbfc; padding: 0.5rem; border-left: 3px solid var(--blue-secondary); margin-bottom: 0.5rem;">
                  &ldquo;${escapeHtml(seg.text)}&rdquo;
                </div>
              ` : ''}
              <div style="margin-bottom: 0.4rem;">
                <span style="font-size: 0.75rem; font-weight: 700; text-transform: uppercase; color: var(--text-muted); letter-spacing: 0.5px;">Advocate Evaluation &amp; Recommendation:</span>
                <p style="font-size: 0.85rem; color: var(--navy-primary); font-weight: 500; margin-top: 0.15rem;">
                  ${escapeHtml(f.lawyer_rationale || 'Assessment completed by advocate.')}
                </p>
              </div>
              ${statRefs.length > 0 ? `
                <div style="margin-top: 0.5rem; padding-top: 0.4rem; border-top: 1px dashed var(--border-color); font-size: 0.775rem; color: var(--text-muted);">
                  <strong>Statutory Basis:</strong> ${escapeHtml(statRefs[0].statute_title || statRefs[0].act_name || 'Curated Indian Statute')}, Section ${escapeHtml(statRefs[0].section_number || statRefs[0].section || 'N/A')}
                </div>
              ` : ''}
            </div>
          `;
        }).join('');
    }

    // Communications
    const commDiv = document.getElementById('client-comments-thread');
    const comments = data.comments || [];
    if (comments.length === 0) {
      if (commDiv) commDiv.innerHTML = `<p style="font-size: 0.8rem; color: var(--text-muted); padding: 0.5rem 0;">No communications released yet.</p>`;
    } else {
      if (commDiv) {
        commDiv.innerHTML = comments.map(c => `
          <div style="padding: 0.5rem 0.75rem; border-bottom: 1px solid var(--border-color); font-size: 0.825rem;">
            <div style="font-weight: 600; color: var(--navy-primary);">${escapeHtml(c.author_name)}:</div>
            <div style="color: var(--text-secondary); margin-top: 0.15rem;">${escapeHtml(c.comment_text)}</div>
          </div>
        `).join('');
      }
    }

    // Reports & Feedback
    if (data.document) loadClientReportsForDoc(data.document.id);
  } catch (err) {
    console.error("Error opening client document view:", err);
  }
}

async function loadClientReportsForDoc(docId) {
  try {
    const res = await apiFetch(`/api/reports/document/${docId}`);
    if (!res.ok) return;
    const data = await res.json();
    const repDiv = document.getElementById('client-reports-list');
    const formBox = document.getElementById('client-feedback-form-box');

    if (!data.reports || data.reports.length === 0) {
      if (repDiv) repDiv.innerHTML = `<p style="font-size: 0.825rem; color: var(--text-muted); padding: 0.5rem 0;">No finalized lawyer report available for this contract yet.</p>`;
      if (formBox) formBox.style.display = 'none';
      return;
    }

    const activeReport = data.reports.find(r => r.status === 'FINAL') || data.reports[0];
    AppState.currentClientActiveReportId = activeReport.report_id;

    if (repDiv) {
      repDiv.innerHTML = data.reports.map(r => `
        <div style="padding: 1rem; border: 1px solid var(--border-color); border-radius: var(--radius-md); margin-bottom: 0.75rem; background: var(--bg-card-subtle);">
          <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem;">
            <div>
              <div style="font-weight: 700; color: var(--navy-primary);">${escapeHtml(r.report_number)} (Version ${r.report_version})</div>
              <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.2rem;">
                Generated: ${r.generated_at} &bull; SHA-256: <span class="code-pill">${r.content_sha256 ? r.content_sha256.substring(0, 16) + '...' : 'Verified'}</span>
              </div>
            </div>
            <div>
              <a href="/api/reports/${r.report_id}/pdf" target="_blank" class="btn btn-primary btn-sm">
                Download PDF Report
              </a>
            </div>
          </div>
        </div>
      `).join('');
    }

    if (formBox && activeReport.status === 'FINAL') {
      formBox.style.display = 'block';
    }

    loadClientFeedbackHistory(activeReport.report_id);
  } catch (err) {
    console.error("Error loading client reports:", err);
  }
}

async function loadClientFeedbackHistory(reportId) {
  try {
    const res = await apiFetch(`/api/reports/${reportId}/feedback`);
    if (!res.ok) return;
    const data = await res.json();
    const histDiv = document.getElementById('client-feedback-history');

    if (!data.feedback || data.feedback.length === 0) {
      if (histDiv) histDiv.innerHTML = `<p style="font-size: 0.8rem; color: var(--text-muted); padding: 0.5rem 0;">No previous feedback submitted on this report version.</p>`;
      return;
    }

    if (histDiv) {
      histDiv.innerHTML = `
        <h4 style="font-size: 0.875rem; font-weight: 700; color: var(--navy-primary); margin: 0.75rem 0 0.4rem 0;">Feedback &amp; Advocate Responses</h4>
        ${data.feedback.map(fb => `
          <div style="padding: 0.75rem; border: 1px solid var(--border-color); border-radius: var(--radius-sm); margin-bottom: 0.5rem; background: #FFFFFF;">
            <div style="display: flex; justify-content: space-between; font-size: 0.8rem;">
              <span>Status: <span class="badge badge-info">${fb.status}</span></span>
              <span style="font-weight: 600; color: var(--warning);">Satisfaction: ${fb.overall_satisfaction}/5 | Clarity: ${fb.clarity_rating}/5</span>
            </div>
            ${fb.client_comments ? `<p style="font-size: 0.825rem; color: var(--text-secondary); margin-top: 0.25rem;">Your Comment: &ldquo;${escapeHtml(fb.client_comments)}&rdquo;</p>` : ''}
            
            ${(fb.responses || []).map(r => `
              <div style="margin-top: 0.35rem; padding: 0.4rem 0.65rem; background: var(--info-bg); border-left: 3px solid var(--info); font-size: 0.8rem;">
                <strong style="color: var(--info);">${escapeHtml(r.responder_name)} (${r.responder_role}):</strong>
                <div style="color: var(--text-main); margin-top: 0.15rem;">${escapeHtml(r.response_text)}</div>
              </div>
            `).join('')}
          </div>
        `).join('')}
      `;
    }
  } catch (err) {
    console.error("Error loading feedback history:", err);
  }
}

async function submitReportFeedback() {
  if (!AppState.currentClientActiveReportId) {
    alert("No active final report selected.");
    return;
  }

  const overall = parseInt(document.getElementById('cf-rating-overall').value, 10);
  const clarity = parseInt(document.getElementById('cf-rating-clarity').value, 10);
  const usefulness = parseInt(document.getElementById('cf-rating-usefulness').value, 10);
  const needsClarification = document.getElementById('cf-clarification-check').checked;
  const followUp = document.getElementById('cf-followup-check').checked;
  const comments = document.getElementById('cf-comments-input').value.trim();

  try {
    const res = await apiFetch(`/api/reports/${AppState.currentClientActiveReportId}/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        overall_satisfaction: overall,
        clarity_rating: clarity,
        usefulness_rating: usefulness,
        needs_clarification: needsClarification,
        follow_up_requested: followUp,
        client_comments: comments || null
      })
    });

    const data = await res.json();
    if (!res.ok) {
      showToast('Error submitting feedback: ' + (data.error || 'Server error'), 'error');
      return;
    }

    showToast('Feedback submitted successfully! Thank you.', 'success');
    document.getElementById('cf-comments-input').value = '';
    loadClientFeedbackHistory(AppState.currentClientActiveReportId);
  } catch (e) {
    alert('Error submitting feedback: ' + e);
  }
}

// =============================================================================
// WORKBENCH & CLIENT MODAL ACTION HANDLERS
// =============================================================================

async function submitRevision(event) {
  if (event) event.preventDefault();
  if (!AppState.currentWorkbenchReviewId) {
    showToast('Please select a contract review first.', 'warning');
    return;
  }
  const text = document.getElementById('rev-text')?.value.trim();
  const reason = document.getElementById('rev-reason')?.value.trim();
  const btn = document.getElementById('btn-submit-revision');

  if (!text || !reason) {
    showToast('Revised text and revision rationale are required.', 'warning');
    return;
  }

  if (btn) { btn.disabled = true; btn.textContent = 'Submitting...'; }

  try {
    const res = await apiFetch(`/api/review/${AppState.currentWorkbenchReviewId}/revision/propose`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ revised_text: text, change_reason: reason })
    });
    const data = await res.json();
    if (!res.ok) {
      showToast('Revision submission failed: ' + (data.error || 'Server error'), 'error');
      return;
    }
    showToast(`Revision Version ${data.version_number} proposed successfully!`, 'success');
    closeRevisionModal();
    openWorkbenchReview(AppState.currentWorkbenchReviewId);
  } catch (err) {
    showToast('Error proposing revision: ' + err, 'error');
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = 'Submit Revision Proposal'; }
  }
}

async function submitCompleteReview(event) {
  if (event) event.preventDefault();
  if (!AppState.currentWorkbenchReviewId) {
    showToast('Please select a contract review first.', 'warning');
    return;
  }
  const summary = document.getElementById('comp-summary')?.value.trim();
  const limitations = document.getElementById('comp-limitations')?.value.trim();
  const unresolved = document.getElementById('comp-unresolved')?.value.trim();
  const actionRequired = document.getElementById('comp-action-required')?.checked || false;
  const disclaimerChecked = document.getElementById('comp-disclaimer-check')?.checked;
  const btn = document.getElementById('btn-submit-complete-review');

  if (!summary) {
    showToast('Executive review summary is mandatory.', 'warning');
    return;
  }
  if (!disclaimerChecked) {
    showToast('You must confirm the statutory compliance disclaimer before completing review.', 'warning');
    return;
  }

  if (btn) { btn.disabled = true; btn.textContent = 'Completing Review...'; }

  try {
    const res = await apiFetch(`/api/review/${AppState.currentWorkbenchReviewId}/complete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        completion_summary: summary,
        outstanding_limitations: limitations || null,
        unresolved_questions: unresolved || null,
        further_client_action_required: actionRequired
      })
    });
    const data = await res.json();
    if (!res.ok) {
      showToast('Cannot complete review: ' + (data.error || 'Validation error'), 'error');
      return;
    }
    showToast('Review completed successfully with verified advocate sign-off!', 'success');
    closeCompleteReviewModal();
    loadWorkbenchQueue();
    openWorkbenchReview(AppState.currentWorkbenchReviewId);
  } catch (err) {
    showToast('Error completing review: ' + err, 'error');
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = 'Confirm & Complete Review'; }
  }
}

async function submitAuthorFinding(event) {
  if (event) event.preventDefault();
  if (!AppState.currentWorkbenchReviewId || !AppState.currentSelectedSegmentId) {
    showToast('Please select a contract clause first.', 'warning');
    return;
  }
  const riskLabel = document.getElementById('af-risk-label')?.value.trim();
  const decision = document.getElementById('af-decision')?.value;
  const observation = document.getElementById('af-observation')?.value.trim();
  const rationale = document.getElementById('af-rationale')?.value.trim();
  const notes = document.getElementById('af-notes')?.value.trim();
  const disclose = document.getElementById('af-disclose-check')?.checked || false;
  const btn = document.getElementById('btn-submit-author-finding');

  if (!riskLabel || !observation || !rationale) {
    showToast('Risk label, observation, and rationale are required.', 'warning');
    return;
  }

  if (btn) { btn.disabled = true; btn.textContent = 'Saving Finding...'; }

  try {
    const res = await apiFetch(`/api/review/${AppState.currentWorkbenchReviewId}/finding/create`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        segment_id: AppState.currentSelectedSegmentId,
        risk_label: riskLabel,
        lawyer_observation: observation,
        decision: decision,
        rationale: rationale,
        notes: notes || null,
        is_disclosed_to_client: disclose
      })
    });
    const data = await res.json();
    if (!res.ok) {
      showToast('Error authoring finding: ' + (data.error || 'Server error'), 'error');
      return;
    }
    showToast('Independent lawyer finding saved successfully!', 'success');
    closeAuthorFindingModal();
    openWorkbenchReview(AppState.currentWorkbenchReviewId);
  } catch (err) {
    showToast('Network error authoring finding: ' + err, 'error');
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = 'Save Finding'; }
  }
}

async function submitLawyerAssignment(event) {
  if (event) event.preventDefault();
  if (!AppState.currentWorkbenchReviewId) {
    showToast('Please select a contract review first.', 'warning');
    return;
  }
  const lawyerId = document.getElementById('assign-lawyer-select')?.value;
  const rationale = document.getElementById('assign-rationale')?.value.trim();
  const btn = document.getElementById('btn-submit-assignment');

  if (!lawyerId) {
    showToast('Please select an eligible advocate.', 'warning');
    return;
  }

  if (btn) { btn.disabled = true; btn.textContent = 'Assigning...'; }

  try {
    const res = await apiFetch(`/api/review/${AppState.currentWorkbenchReviewId}/assign`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        lawyer_id: lawyerId,
        rationale: rationale || null
      })
    });
    const data = await res.json();
    if (!res.ok) {
      showToast('Assignment failed: ' + (data.error || 'Server error'), 'error');
      return;
    }
    showToast('Review assigned to verified advocate successfully!', 'success');
    closeAssignLawyerModal();
    loadWorkbenchQueue();
    openWorkbenchReview(AppState.currentWorkbenchReviewId);
  } catch (err) {
    showToast('Network error during assignment: ' + err, 'error');
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = 'Confirm Assignment'; }
  }
}

async function submitClientRevision(event) {
  if (event) event.preventDefault();
  if (!AppState.currentClientActiveReviewId) {
    showToast('Please select a contract first.', 'warning');
    return;
  }
  const text = document.getElementById('client-rev-text')?.value.trim();
  const reason = document.getElementById('client-rev-reason')?.value.trim();
  const btn = document.getElementById('btn-submit-client-revision');

  if (!text || !reason) {
    showToast('Updated text and description are required.', 'warning');
    return;
  }

  if (btn) { btn.disabled = true; btn.textContent = 'Submitting...'; }

  try {
    const res = await apiFetch(`/api/review/${AppState.currentClientActiveReviewId}/revision/propose`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        revised_text: text,
        change_reason: reason
      })
    });
    const data = await res.json();
    if (!res.ok) {
      showToast('Submission failed: ' + (data.error || 'Server error'), 'error');
      return;
    }
    showToast('Information and proposed changes submitted to reviewing advocate!', 'success');
    closeClientRevisionModal();
    openClientDocumentView(AppState.currentClientActiveReviewId);
  } catch (err) {
    showToast('Network error submitting changes: ' + err, 'error');
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = 'Submit to Advocate'; }
  }
}

async function submitClientClarificationReply() {
  if (!AppState.currentClientActiveReviewId) {
    showToast('Please select a contract first.', 'warning');
    return;
  }
  const input = document.getElementById('client-reply-input');
  const text = input ? input.value.trim() : '';

  if (!text) {
    showToast('Please type a response before submitting.', 'warning');
    return;
  }

  try {
    const res = await apiFetch(`/api/review/${AppState.currentClientActiveReviewId}/comment`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        comment_text: text,
        visibility: 'CLIENT_VISIBLE'
      })
    });
    const data = await res.json();
    if (!res.ok) {
      showToast('Error sending reply: ' + (data.error || 'Server error'), 'error');
      return;
    }
    input.value = '';
    showToast('Response submitted to reviewing advocate successfully.', 'success');
    openClientDocumentView(AppState.currentClientActiveReviewId);
  } catch (err) {
    showToast('Network error submitting response: ' + err, 'error');
  }
}

// =============================================================================
// AUDIT LOGS
// =============================================================================

AppState.auditEvents = [];

async function loadAuditLogs() {
  const tableBody = document.getElementById('audit-table-body');
  const countBadge = document.getElementById('audit-count-badge');
  if (!tableBody) return;

  tableBody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">Loading audit trail...</td></tr>`;

  try {
    const res = await apiFetch('/api/audit/logs');
    if (!res.ok) {
      tableBody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--error); padding: 1.5rem;">Access restricted to Auditors &amp; Supervising Lawyers.</td></tr>`;
      if (countBadge) countBadge.textContent = 'Restricted';
      return;
    }
    const data = await res.json();
    const events = data.events || [];
    AppState.auditEvents = events;
    if (countBadge) countBadge.textContent = `${events.length} Events`;

    renderAuditTable(events);
  } catch (err) {
    tableBody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--error); padding: 1.5rem;">Error loading audit trail: ${err}</td></tr>`;
  }
}

function renderAuditTable(events) {
  const tableBody = document.getElementById('audit-table-body');
  if (!tableBody) return;

  if (events.length === 0) {
    tableBody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">No audit events recorded.</td></tr>`;
    return;
  }

  tableBody.innerHTML = events.map(e => {
    let payloadSummary = '';
    if (e.payload) {
      try {
        const p = typeof e.payload === 'string' ? JSON.parse(e.payload) : e.payload;
        payloadSummary = Object.entries(p).map(([k, v]) => `${k}: ${v}`).slice(0, 2).join('; ');
      } catch (_) {
        payloadSummary = String(e.payload);
      }
    }
    return `
      <tr>
        <td style="font-size: 0.8rem; white-space: nowrap;">${escapeHtml(e.timestamp || 'N/A')}</td>
        <td><strong>${escapeHtml(e.event_type)}</strong></td>
        <td style="font-size: 0.825rem;">${escapeHtml(e.actor_id || e.actor_type || 'system')}</td>
        <td><span class="badge badge-info" style="font-size: 0.7rem;">${escapeHtml(e.actor_type || 'SYSTEM')}</span></td>
        <td style="font-size: 0.8rem; max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${escapeHtml(JSON.stringify(e.payload || {}))}">${escapeHtml(payloadSummary || 'Event recorded')}</td>
        <td><span class="code-pill">${escapeHtml(e.event_hash ? e.event_hash.substring(0, 16) + '...' : (e.entry_hash ? e.entry_hash.substring(0, 16) + '...' : 'Verified'))}</span></td>
      </tr>
    `;
  }).join('');
}

function filterAuditLogs() {
  const q = document.getElementById('audit-search-filter')?.value.toLowerCase().trim() || '';
  if (!q) {
    renderAuditTable(AppState.auditEvents || []);
    return;
  }
  const filtered = (AppState.auditEvents || []).filter(e => {
    return (
      (e.event_type && e.event_type.toLowerCase().includes(q)) ||
      (e.actor_id && e.actor_id.toLowerCase().includes(q)) ||
      (e.actor_type && e.actor_type.toLowerCase().includes(q)) ||
      (e.event_hash && e.event_hash.toLowerCase().includes(q)) ||
      (e.entry_hash && e.entry_hash.toLowerCase().includes(q)) ||
      (e.payload && JSON.stringify(e.payload).toLowerCase().includes(q))
    );
  });
  renderAuditTable(filtered);
}

// =============================================================================
// MODALS & UTILITIES
// =============================================================================

function openModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.classList.add('active');
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.classList.remove('active');
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function getStatusBadgeClass(status) {
  switch (status) {
    case 'REVIEW_COMPLETED':
    case 'FINAL':
    case 'CLOSED':
      return 'badge-success';
    case 'IN_REVIEW':
    case 'ASSIGNED':
    case 'RESPONSE_REQUIRED':
      return 'badge-warning';
    case 'REVISION_REQUESTED':
    case 'REJECTED':
      return 'badge-error';
    case 'AWAITING_LAWYER_ASSIGNMENT':
    case 'SUBMITTED':
      return 'badge-info';
    default:
      return 'badge-neutral';
  }
}

function getClientStatusLabel(status) {
  const labels = {
    AWAITING_LAWYER_ASSIGNMENT: "Waiting for a lawyer",
    ASSIGNED: "Lawyer assigned",
    IN_REVIEW: "Your contract is being reviewed",
    REVISION_REQUESTED: "Additional information or changes requested",
    CLIENT_RESPONSE_RECEIVED: "Your response has been received",
    REVIEW_COMPLETED: "Review completed",
    REVIEW_REOPENED: "Review reopened",
    PROCESSING: "Processing your document",
    PROCESSING_FAILED: "Document processing needs attention"
  };
  return labels[status] || status;
}

// Initialize on DOM Ready
document.addEventListener('DOMContentLoaded', () => {
  initAuth();
});

// Global Modal Dismissal: Escape key and backdrop clicks
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal-overlay.active, .modal-backdrop.active').forEach(m => m.classList.remove('active'));
  }
});

document.addEventListener('click', (e) => {
  if (e.target.classList && (e.target.classList.contains('modal-overlay') || e.target.classList.contains('modal-backdrop'))) {
    e.target.classList.remove('active');
  }
});

