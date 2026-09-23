# Clinic EMR — Project Blueprint

## 1. Purpose
Move the clinic from paper records to a secure, web-based system where staff can
store, search, and export patient records, with a chatbot to quickly pull up
information instead of digging through files.

## 2. Users & Roles

| Role | Can do |
|---|---|
| **Admin** | Everything: manage staff accounts (create/disable), view the audit log, full patient & clinical record access, delete records |
| **Doctor** | Register/view patients, create & edit clinical records (diagnosis, notes, prescriptions), search, export, use the chatbot |
| **Receptionist** | Register patients, view basic (non-clinical) patient info — name, DOB, phone, address. **Cannot** see diagnoses/notes/prescriptions |

Every role must log in — there is no public/anonymous access to any patient data.

## 3. Architecture

```
Browser (HTML/CSS/JS)  --->  Flask REST API (Python)  --->  SQLite database
     |                              |
     | fetch() with JWT token       | bcrypt password hashing
     | in Authorization header      | JWT-based session tokens
                                     | role-based route guards
                                     | audit log of every sensitive action
```

- **Frontend:** plain HTML/CSS/JS (no framework), responsive layout, works on mobile browsers.
- **Backend:** Python (Flask), REST JSON API.
- **Database:** SQLite to start (free, zero setup, a single file). Built with SQLAlchemy ORM, so upgrading to PostgreSQL (e.g. via Supabase's free tier) later is a one-line config change, not a rewrite.
- **Hosting (when you're ready to go live):** backend can deploy free/cheap on Render, Railway, or PythonAnywhere; frontend as static files on Netlify/Vercel/GitHub Pages or served by the same backend.

## 4. Security, Authentication & Authorization

- **Passwords:** hashed with bcrypt — never stored or logged in plain text.
- **Authentication:** login returns a signed JWT token (expires after 60 min by default); every API request after that must include it.
- **Authorization:** every route is guarded by role — e.g. only Admin/Doctor can write clinical notes; only Admin can create staff accounts or view the audit log.
- **Audit log:** every login, record view/edit, export, and access-denied attempt is logged with who, what, and when.
- **Transport security:** designed to run behind HTTPS in production (required for real patient data — see deployment notes in README).
- **Input handling:** all database queries go through the ORM (no raw SQL), which prevents SQL injection.
- **Secrets:** the signing key and DB path live in environment variables (`.env`), never hard-coded.

> Note: this gets you strong baseline security. If this will hold real patient data, plan a proper compliance review (e.g. HIPAA or your local health-data regulation) before going live — things like data backups, breach-notification process, and encryption-at-rest for the database file are operational steps beyond the code itself.

## 5. Core Features

1. **Login/logout** with role-aware dashboard.
2. **Patient management** — register new patients, search by name.
3. **Clinical records** — add visit notes, diagnosis, prescription, tagged with searchable condition tags.
4. **Search & Chatbot** — ask things like *"records for John Smith"* or *"patients with diabetes this month"*; the chatbot parses it and runs the same search as the manual search bar. Built rule-based now (free, instant, no API key); structured so it can be swapped for an AI/LLM-powered version later without changing the rest of the app.
5. **Export** — any search result set can be downloaded as **Excel (.xlsx)**, **PDF**, or **Word (.docx)**.
6. **Admin panel** — create/disable staff accounts, view the audit log.
7. **Mobile-responsive UI** — collapsible sidebar, scrollable tables, touch-friendly chat widget.

## 6. Data Model (simplified)

- **User** — name, email, password hash, role, active flag
- **Patient** — name, DOB, gender, phone, address, who registered them
- **MedicalRecord** — linked to a patient, visit date, diagnosis, condition tags, notes, prescription, who created it
- **AuditLog** — user, action, detail, IP, timestamp

## 7. What's next after this prototype

- Deploy backend + database somewhere with HTTPS (Render/Railway free tiers work well to start).
- Set real environment variables (`SECRET_KEY`, etc.) — never use the defaults in production.
- Decide on a backup schedule for the database file (or move to managed PostgreSQL, which handles backups for you).
- When ready, swap the chatbot's rule-based parser for an LLM call (the code has a marked plug-in point for this already).