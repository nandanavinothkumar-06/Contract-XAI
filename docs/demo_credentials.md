# CONTRACTRISK-XAI: Local Evaluation Demo Credentials

> [!WARNING]
> **LOCAL EVALUATION ONLY — NOT PRODUCTION SECRETS**  
> These credentials correspond to the pre-seeded SQLite/PostgreSQL development environment initialized automatically by `seed_demo_environment()` in `src/dashboard/app.py`. They are intended strictly for local verification and academic demonstration.

---

## Pre-Seeded Development Accounts

| Role | Name | Email | Password | Status / Credentials |
| :--- | :--- | :--- | :--- | :--- |
| **Lawyer / Advocate** | Adv. Priya Sharma | `advocate@legal.in` | `LegalTech2026!` | Verified Advocate (Bar ID: `D/1429/2014`, Bar Council of Delhi) |
| **Enterprise Client** | Vikram Patel (General Counsel) | `client@enterprise.in` | `ClientTech2026!` | Client Tenant (TechCorp India) |
| **Supervising Lawyer** | Adv. Rajeshwar Rao (Senior Partner) | `supervisor@legal.in` | `SuperTech2026!` | Supervising Counsel (Bar ID: `MH/3811/2005`, Bar Council of Maharashtra & Goa) |
| **Auditor** | Deepa Narayanan | `auditor@governance.in` | `AuditTech2026!` | Compliance & Algorithmic Auditor (Read-only access to tamper-evident audit logs) |

---

## Pre-Seeded Demo Contract Record

Upon application launch, the database automatically initializes a sample commercial agreement (`doc_demo_agreement_01`) containing:
1. Five structured clauses (Scope, Non-Compete / Restraint of Trade, Data Protection under DPDP 2023, Indemnity, Arbitration under ACA 1996).
2. A pre-generated AI risk finding on Clause 2 (5-year post-termination non-compete flagged under Section 27, Indian Contract Act, 1872).
3. A logged advocate review decision accepting the AI observation with statutory legal rationale citing *Percept D'Mark v. Zaheer Khan*.
