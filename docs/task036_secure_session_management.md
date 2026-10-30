# TASK 036 — PERSISTENT AUTHENTICATION AND SECURE SESSION MANAGEMENT

**Project:** CONTRACTRISK-XAI  
**Status:** COMPLETE  
**Date:** 2026-10-15  
**Evaluation Scope:** Persistent browser sessions, HttpOnly cookie authentication, database session registry, Double-Submit CSRF protection, RBAC integrity, cascade revocation, and tamper-evident audit logging.

---

## 1. Existing Authentication Architecture Prior to Task 036

Task 031 introduced foundational role-based access control and JWT token generation using Argon2id password hashing and cryptographic JSON Web Tokens signed with HMAC-SHA256 (`HS256`).
Task 035 developed the modernized LegalTech user interface, incorporating branding, responsive tab navigation, and client/lawyer workbenches.

However, the Task 035 post-implementation verification report documented that the frontend client (`dashboard.js`) stored raw JWT access tokens in `localStorage` under the key `'contractrisk_token'`. On every API call, the client read the raw JWT from `localStorage` and attached it as an `Authorization: Bearer <token>` header.

Session revocation was managed solely via an in-memory `set` (`TokenManager.revoked_jtis`) residing in process memory, lacking database persistence across server restarts or multi-worker deployments.

---

## 2. Identified Security Risks of Prior Implementation

1. **XSS Token Exfiltration (`localStorage` Storage):**
   Raw JWTs stored in `localStorage` are accessible to any JavaScript executing in the origin's context. A single cross-site scripting vulnerability or rogue third-party dependency could compromise all client credentials.
2. **Ephemeral In-Memory Revocation:**
   Logged-out JWTs were tracked only in Python process RAM. If the application process restarted or scaled across multiple worker threads/processes, previously logged-out or revoked tokens could be replayed successfully.
3. **Lack of Invalidation on Account Status / Password Changes:**
   Changing passwords or suspending accounts did not automatically invalidate outstanding JWT tokens issued prior to the security event.
4. **Absence of CSRF Protection for Cookie Sessions:**
   When cookies were evaluated in Task 031, there was no Double-Submit Cookie pattern or server-side CSRF validation for state-changing HTTP requests.
5. **No Idle or Sliding Expiration Window:**
   Sessions were strictly bound to a static 60-minute JWT `exp` timestamp without support for sliding activity refresh or persistent "Remember Me" controls.

---

## 3. Chosen Session Architecture

We selected a **Hybrid Dual-Mode Authentication Architecture**:
1. **Browser Clients (Web Application):**
   - **Credential Storage:** Transported and stored strictly via secure, `HttpOnly` session cookies (`contractrisk_session`).
   - **Zero Client-Side Token Exposure:** JavaScript running in the browser never has access to the raw JWT access token or session secrets.
   - **CSRF Defense:** State-changing requests (`POST`, `PUT`, `DELETE`, `PATCH`) require OWASP Double-Submit Cookie validation (`contractrisk_csrf` cookie + `X-CSRF-Token` header) coupled with Origin/Referer header verification.
2. **Non-Browser API Clients (Automated Services / CLI):**
   - Retains support for `Authorization: Bearer <token>` headers.
   - Bearer token requests are explicitly exempted from CSRF checks because custom headers cannot be set cross-origin by arbitrary browser forms or fetch requests without explicit CORS preflight permission.
3. **Precedence Policy:**
   If an explicit `Authorization: Bearer <token>` header is present, it is evaluated first. If absent, the server extracts credentials from the `contractrisk_session` cookie.

---

## 4. Authentication Flow

```mermaid
sequenceDiagram
    autonumber
    actor User as Legal Practitioner / Client
    participant Browser as Web Browser (DOM / JS)
    participant Flask as Flask Application & Middleware
    participant Auth as AuthService & TokenManager
    participant DB as SQLite / PostgreSQL (user_sessions)
    participant Audit as Hash-Chained Audit Store

    User->>Browser: Submit Email & Password (+ optional Remember Me)
    Browser->>Flask: POST /api/auth/login {email, password, remember_me}
    Flask->>Auth: authenticate_user(email, password, remember_me, ip, ua)
    Auth->>Auth: Verify Argon2id hash & verify AccountStatus == ACTIVE
    Auth->>Auth: Generate signed JWT (HS256) with unique jti
    Auth->>DB: Persist UserSessionRecord (SHA-256 hash of jti, expires_at)
    Auth->>Audit: Record LOGIN_SUCCESS and SESSION_CREATED events
    Auth-->>Flask: (user, token, session_rec)
    Flask->>Flask: Generate CSRF token (64 hex chars)
    Flask-->>Browser: Set-Cookie: contractrisk_session (HttpOnly, SameSite=Lax)<br/>Set-Cookie: contractrisk_csrf (SameSite=Lax)<br/>JSON: {user, access_token, csrf_token}

    Note over Browser,Flask: Subsequent Protected Request (e.g. POST /api/review/upload)
    Browser->>Flask: POST /api/review/upload<br/>Cookie: contractrisk_session; contractrisk_csrf<br/>X-CSRF-Token: <csrf_token>
    Flask->>Flask: @app.before_request: validate_csrf_request()
    Flask->>Flask: @require_auth: extract_current_user_from_request()
    Flask->>DB: Query UserSessionRecord by SHA-256(jti)
    DB-->>Flask: session_rec (is_revoked=False, expires_at > now)
    Flask->>DB: Update last_activity_at (sliding window)
    Flask->>DB: Check UserRecord.account_status == ACTIVE
    Flask-->>Browser: HTTP 200 / 201 Authorized Response
```

---

## 5. Cookie Configuration

All cookies issued by `CONTRACTRISK-XAI` adhere to modern browser security standards:

| Cookie Name | Purpose | HttpOnly | Secure | SameSite | Path | Max-Age / Lifetime |
|---|---|---|---|---|---|---|
| `contractrisk_session` | Primary Authentication Credential | `True` | `True` in prod, configurable in dev | `Lax` | `/` | 60 mins (standard) / 14 days (Remember Me) |
| `contractrisk_csrf` | CSRF Double-Submit Token | `False` (JS accessible) | `True` in prod, configurable in dev | `Lax` | `/` | Matches session lifetime |

* **Host-Only Scope:** Cookies are scoped strictly to the origin without broad domain wildcards.
* **SameSite=Lax:** Selected over `Strict` to allow top-level incoming navigations (e.g., following bookmarks or email links) while completely preventing cross-site form submissions or image tag triggers from sending authenticated cookies.
* **Path=/:** Restricted to application root.

---

## 6. Server-Side Session Persistence

Session state is persisted using SQLAlchemy in a dedicated database table: `user_sessions`.

### Schema (`UserSessionRecord`)
* `id` (`String(36)`, PK): UUIDv4 primary identifier.
* `user_id` (`String(36)`, FK -> `users.id` on delete cascade, indexed): Owning user identifier.
* `session_token_hash` (`String(64)`, unique, indexed): SHA-256 cryptographic digest of the JWT `jti` claim. **Raw JWT tokens and passwords are never stored in the database.**
* `is_revoked` (`Boolean`, default `False`, indexed): Server-side revocation flag.
* `revoked_at` (`DateTime`, timezone-aware UTC): Timestamp when revocation occurred.
* `revocation_reason` (`String(64)`): Audit reason (`LOGOUT`, `EXPIRED`, `PASSWORD_CHANGED`, `ACCOUNT_SUSPENDED`, etc.).
* `remember_me` (`Boolean`, default `False`): Distinguishes persistent workstations from standard sessions.
* `ip_address` (`String(45)`): Client IP address recorded at login.
* `user_agent` (`String(255)`): Client browser User-Agent recorded at login.
* `created_at` (`DateTime`, timezone-aware UTC): Session creation timestamp.
* `last_activity_at` (`DateTime`, timezone-aware UTC): Last observed authenticated request timestamp.
* `expires_at` (`DateTime`, timezone-aware UTC, indexed): Absolute server-side session expiration deadline.

---

## 7. Session Expiration and Persistent Login

1. **Standard Sessions:** Default lifetime is 60 minutes (`access_token_expire_minutes = 60`).
2. **Remember Me Sessions:** When explicitly opted into by checking *"Remember me on this workstation (14 days)"*, lifetime is extended to 14 days (`remember_me_days = 14`).
3. **Sliding Activity Tracking:** On every authenticated request, if more than 60 seconds have elapsed since `last_activity_at`, the server updates `last_activity_at` to track user activity without database write thrashing.
4. **Server-Side Enforcement:** Even if a client browser attempts to reuse a cookie, the server inspects `session_rec.expires_at`. If `expires_at <= now()`, the session is automatically marked revoked with reason `"EXPIRED"` and HTTP 401 Unauthorized is returned.

---

## 8. Revocation Strategy

Session revocation is immediately effective across all processes and workers:

* **Explicit User Logout (`POST /api/auth/logout`):**
  - Session is marked `is_revoked = True` with reason `"LOGOUT"` in the database.
  - In-memory `TokenManager.revoked_jtis` cache is updated.
  - Both `contractrisk_session` and `contractrisk_csrf` cookies are cleared via `Set-Cookie` with `Max-Age=0`.
* **Password Change (`POST /api/auth/password/change`):**
  - Verifies current password using Argon2id.
  - Re-hashes new password using Argon2id.
  - Executes cascade revocation of **all** active sessions belonging to the user (`revoke_all_user_sessions(user_id, reason="PASSWORD_CHANGED")`).
  - Clears caller cookies.
* **Account Suspension / Deactivation:**
  - When an account's `account_status` changes to `SUSPENDED` or `DEACTIVATED`, any subsequent request using an existing session immediately triggers session revocation with reason `"ACCOUNT_SUSPENDED"` and returns HTTP 401 Unauthorized.
* **Process Restarts & Multi-Instance:**
  - Because revocation is stored as a SHA-256 hash in the database, newly spawned Flask worker processes immediately respect revoked sessions without relying on in-memory caches.

---

## 9. CSRF Protection Architecture

Implemented via `src/auth/csrf.py` and hooked into Flask's `@app.before_request`:

1. **Double-Submit Pattern:**
   - Server issues a cryptographically random 64-character hexadecimal token (`secrets.token_hex(32)`) in the `contractrisk_csrf` cookie.
   - Frontend `dashboard.js` reads `contractrisk_csrf` and attaches it in the custom request header `X-CSRF-Token`.
   - On state-changing methods (`POST`, `PUT`, `DELETE`, `PATCH`), the middleware performs constant-time verification (`hmac.compare_digest`).
2. **Origin & Referer Validation:**
   - Verifies that incoming `Origin` or `Referer` headers match the application's expected host, defending against DNS rebinding and cross-site fetch attempts.
3. **Exemptions:**
   - Safe read-only HTTP methods (`GET`, `HEAD`, `OPTIONS`, `TRACE`).
   - Public authentication endpoints (`/api/auth/login`, `/api/auth/register`, `/api/auth/csrf`, `/api/health`).
   - Programmatic API requests carrying explicit `Authorization: Bearer <token>` headers (cross-origin browser attacks cannot forge custom `Authorization` headers).

---

## 10. Role and Account-Status Enforcement

Authorization remains centralized on the backend through Flask route decorators:
- `@require_auth`: Derives identity strictly from database-verified sessions.
- `@require_roles(*roles)`: Enforces role boundaries (`CLIENT`, `LAWYER`, `SUPERVISING_LAWYER`, `AUDITOR`).
- `@require_verified_advocate`: Gated by `advocate_status == VERIFIED` on Bar Council records.
- `@require_contract_access`: Enforces strict tenant and assignment boundaries:
  - Clients access only their owned contracts (`document.owner_id == user.id`).
  - Lawyers access only assigned contracts (`document.assigned_lawyer_id == user.id`).
  - Supervisors access contracts for supervisory oversight.
  - Auditors can view metadata and audit logs, but full confidential clause contents are strictly denied.

**Tamper Prevention:** The frontend role switcher changes only local UI display preferences; every single backend route independently checks the cryptographic identity and current database account state. Modifying browser memory or storage grants zero access.

---

## 11. Audit-Event Integration

Integrated with `CONTRACTRISK-XAI`'s SHA-256 hash-chained provenance trail:
- `SESSION_CREATED`: Logged upon successful user login with session metadata (session ID, user ID, remember-me flag, IP, User-Agent).
- `SESSION_REVOKED`: Logged upon explicit logout, password change, account suspension, or session expiration.
- `CSRF_VALIDATION_FAILED`: Logged when a cross-origin or mismatched CSRF request is rejected.
- `LOGIN_SUCCESS` / `LOGIN_FAILED`: Recorded on authentication attempts.

**Zero Secret Leakage:** Audit payloads strictly exclude passwords, raw JWT tokens, session signing secrets, and CSRF secrets. Cryptographic hash-chain continuity is verified using `AuditVerifier` (`IntegrityStatus.VALID`).

---

## 12. Configuration Requirements

Session configuration options are declared in `AuthConfig` ([src/auth/config.py](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/src/auth/config.py)):

| Setting | Default Value | Description |
|---|---|---|
| `jwt_secret` | Safe dev default | Production requires high-entropy secret (>= 32 chars) |
| `jwt_algorithm` | `HS256` | HMAC signing algorithm |
| `access_token_expire_minutes` | `60` | Standard session lifetime |
| `remember_me_days` | `14` | Extended persistent login duration |
| `session_idle_timeout_minutes` | `30` | Idle timeout threshold |
| `session_cookie_name` | `contractrisk_session` | Name of HttpOnly authentication cookie |
| `csrf_cookie_name` | `contractrisk_csrf` | Name of Double-Submit CSRF cookie |
| `csrf_header_name` | `X-CSRF-Token` | Name of expected CSRF HTTP header |
| `cookie_httponly` | `True` | Disallows JavaScript access to session cookie |
| `cookie_secure` | `False` (dev) / `True` (prod) | Requires HTTPS in production |
| `cookie_samesite` | `Lax` | SameSite cookie policy |
| `cookie_path` | `/` | Cookie URL scope |

---

## 13. Required Environment Variables

| Variable | Required In | Purpose |
|---|---|---|
| `CONTRACTRISK_JWT_SECRET` | Production | 256-bit signing key for JWT token issuance |
| `CONTRACTRISK_ENV` or `FLASK_ENV` | Production | Set to `production` to activate strict fail-safe validation |
| `CONTRACTRISK_COOKIE_SECURE` | Production | Force `True` to require HTTPS for session cookies |
| `CONTRACTRISK_DB_URL` | Optional | Custom PostgreSQL or SQLite connection string |

**Fail-Safe Enforcement:** If `FLASK_ENV=production` or `CONTRACTRISK_ENV=production` is detected and default/short signing secrets are used, `AuthConfig.__post_init__` raises an immediate `ValueError` and prevents server startup.

---

## 14. Database Changes or Migrations

Added table `user_sessions` to the declarative SQLAlchemy metadata in [src/persistence/models.py](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/src/persistence/models.py):

```sql
CREATE TABLE user_sessions (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_token_hash VARCHAR(64) UNIQUE NOT NULL,
    is_revoked BOOLEAN NOT NULL DEFAULT 0,
    revoked_at DATETIME,
    revocation_reason VARCHAR(64),
    remember_me BOOLEAN NOT NULL DEFAULT 0,
    ip_address VARCHAR(45),
    user_agent VARCHAR(255),
    created_at DATETIME NOT NULL,
    last_activity_at DATETIME,
    expires_at DATETIME NOT NULL
);

CREATE INDEX ix_user_sessions_user_active ON user_sessions (user_id, is_revoked);
CREATE INDEX ix_user_sessions_session_token_hash ON user_sessions (session_token_hash);
CREATE INDEX ix_user_sessions_expires_at ON user_sessions (expires_at);
```

---

## 15. Dependencies Added or Changed

No new external packages were required. All capabilities were implemented using existing, approved packages:
- `argon2-cffi` (existing): Argon2id password hashing.
- `PyJWT` (existing): JWT encoding and validation.
- `SQLAlchemy` (existing): Database persistence and indexing.
- `Flask` (existing): Request handling, cookie management, and hooks.
- Python standard library (`hashlib`, `secrets`, `hmac`, `datetime`, `urllib.parse`).

---

## 16. Files Created and Modified

### Created Files
- [src/auth/csrf.py](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/src/auth/csrf.py): Double-Submit Cookie CSRF protection and Origin/Referer verification.
- [tests/test_session_management.py](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/tests/test_session_management.py): 15 comprehensive unit and regression tests.
- [docs/task036_secure_session_management.md](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/docs/task036_secure_session_management.md): This architectural documentation report.

### Modified Files
- [src/auth/config.py](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/src/auth/config.py): Hardened configuration and fail-safe production checks.
- [src/audit/provenance.py](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/src/audit/provenance.py): Added `SESSION_CREATED`, `SESSION_REVOKED`, `CSRF_VALIDATION_FAILED` event types.
- [src/persistence/models.py](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/src/persistence/models.py): Added `UserSessionRecord` and relational cascade to `UserRecord`.
- [src/persistence/__init__.py](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/src/persistence/__init__.py): Exported `UserSessionRecord`.
- [src/persistence/repository.py](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/src/persistence/repository.py): Implemented session creation, token hash query, sliding activity, and revocation methods.
- [src/auth/service.py](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/src/auth/service.py): Integrated DB session persistence, logout revocation, password change cascade revocation, and account suspension cascade revocation.
- [src/auth/rbac.py](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/src/auth/rbac.py): Upgraded `extract_current_user_from_request` to validate persistent DB session records and track sliding activity.
- [src/auth/routes.py](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/src/auth/routes.py): Configured HttpOnly cookie issuance on login, cookie deletion on logout, added `/api/auth/csrf` and `/api/auth/password/change`.
- [src/dashboard/app.py](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/src/dashboard/app.py): Hooked `@app.before_request` CSRF validation and `@app.after_request` cookie setup; added remember-me checkbox.
- [src/dashboard/static/js/dashboard.js](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/src/dashboard/static/js/dashboard.js): Removed `localStorage` token storage, configured `credentials: 'same-origin'`, attached `X-CSRF-Token` on state-changing requests, and updated `initAuth` to verify session state via `/api/auth/me`.

---

## 17. Tests Executed and Actual Results

All tests executed with 100% pass rate:

### 1. New Session Management Suite (`pytest tests/test_session_management.py -v`)
- `test_01_login_sets_httponly_and_csrf_cookies`: **PASSED**
- `test_02_remember_me_extends_session_lifetime`: **PASSED**
- `test_03_invalid_login_credentials_rejected_without_account_enumeration`: **PASSED**
- `test_04_cookie_authenticated_get_succeeds`: **PASSED**
- `test_05_csrf_validation_blocks_cookie_post_without_token`: **PASSED**
- `test_06_csrf_validation_blocks_cookie_post_with_mismatched_token`: **PASSED**
- `test_07_csrf_validation_accepts_valid_double_submit_tokens`: **PASSED**
- `test_08_bearer_token_requests_exempt_from_csrf`: **PASSED**
- `test_09_logout_revokes_server_side_session_and_clears_cookies`: **PASSED**
- `test_10_revocation_persists_across_fresh_token_manager`: **PASSED**
- `test_11_expired_session_rejected_and_marked_revoked`: **PASSED**
- `test_12_password_change_cascades_session_revocation`: **PASSED**
- `test_13_suspended_account_invalidates_active_session`: **PASSED**
- `test_14_horizontal_isolation_client_cannot_access_foreign_contract`: **PASSED**
- `test_15_audit_events_recorded_with_chain_integrity`: **PASSED**
**Result: 15 passed in 2.95s**

### 2. Full Regression Suite (146 Tests Total)
```bash
pytest tests/test_ui_modernization.py tests/test_dashboard.py tests/test_ingestion_persistence.py tests/test_auth_rbac.py tests/test_indian_legal_sources.py tests/test_lawyer_workbench.py tests/test_final_reports_feedback.py tests/test_session_management.py -v
```
- `tests/test_ui_modernization.py`: 11 passed
- `tests/test_dashboard.py`: 6 passed
- `tests/test_ingestion_persistence.py`: 18 passed
- `tests/test_auth_rbac.py`: 23 passed
- `tests/test_indian_legal_sources.py`: 27 passed
- `tests/test_lawyer_workbench.py`: 24 passed
- `tests/test_final_reports_feedback.py`: 22 passed
- `tests/test_session_management.py`: 15 passed
**Total: 146 passed in 12.63s, 0 failures, 0 warnings**

---

## 18. Known Limitations

1. **No Distributed Cache (e.g. Redis):** Persistent sessions rely directly on SQLAlchemy database queries. While optimized with compound indexes (`ix_user_sessions_user_active`) and a 60-second sliding update debounce, extremely high concurrency environments would benefit from a Redis layer.
2. **Double-Submit vs Synchronizer Token Pattern:** Double-Submit Cookie pattern protects against cross-origin CSRF, but if a subdomain of the application is vulnerable to sub-domain cookie injection, an attacker could theoretically overwrite the CSRF cookie. For single-domain architectures, this is secure.
3. **Multi-Factor Authentication (MFA) & Email Delivery:** MFA (TOTP/WebAuthn) and transactional email verification are not implemented as no email delivery service is configured. These remain documented as future work.

---

## 19. Local Development Instructions

1. **Starting the Dashboard Server:**
   ```powershell
   python -m src.dashboard.app
   ```
2. **Accessing the Application:**
   Open `http://127.0.0.1:5000` in any modern web browser.
3. **Testing Login & Personas:**
   Click "Sign In / Role Access" to select demo accounts:
   - Advocate: `advocate@legal.in` / `LegalTech2026!`
   - Client: `client@enterprise.in` / `ClientTech2026!`
   - Supervisor: `supervisor@legal.in` / `SuperTech2026!`
   - Auditor: `auditor@governance.in` / `AuditTech2026!`
4. **Running Automated Tests:**
   ```powershell
   pytest tests/test_session_management.py -v
   ```

---

## 20. Production Deployment Considerations

1. **HTTPS Enforcement:** Production deployments MUST enable HTTPS and set `CONTRACTRISK_COOKIE_SECURE=true` so that browsers refuse to transmit session cookies over plaintext HTTP.
2. **Reverse Proxy Configuration:** When deploying behind Nginx or AWS ALB, ensure `X-Forwarded-For` and `X-Forwarded-Proto` are configured so `request.remote_addr` correctly reflects client IP addresses.
3. **Signing Secret Rotation:** Ensure `CONTRACTRISK_JWT_SECRET` is generated via a cryptographically secure random generator (e.g. `openssl rand -hex 32`) and stored in a secure secret manager.
