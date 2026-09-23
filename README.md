# Clinic EMR & Management System

A modern, cloud-connected Electronic Medical Records (EMR) and clinic management system built with Flask, Vanilla JS, Google Gemini AI, and Neon Serverless PostgreSQL.

---

## 🌟 Key Features

- **Role-Based Access Control**:
  - `Admin`: Full access including user management, audit logging, and change approvals.
  - `Staff`: Daily clinical operations (manage patients, treatment entries, schedule follow-ups).
- **Staff Approval Workflow**:
  - Edits or deletions requested by staff require admin approval before applying to the database.
- **AI-Powered Clinical Assistant**:
  - Integrated with **Google Gemini 3.6 Flash** tool-calling to query patients, follow-ups, and financial collections in natural language.
- **Multi-Format Reports & Exports**:
  - Standardized 8-column exports in Excel (`.xlsx`), Word (`.docx`), and PDF (`.pdf`).
- **Cloud Database Ready**:
  - Native integration with **Neon Serverless PostgreSQL** with pooled connection strings.
- **Serverless Ready**:
  - Pre-configured for deployment on **Vercel** with automatic WSGI routing and `/tmp` filesystem compatibility.

---

## 🛠️ Tech Stack

- **Backend**: Python 3.10+, Flask 3.1.1, SQLAlchemy, PyJWT, Google GenAI SDK, Psycopg2
- **Frontend**: Vanilla HTML5, Modern CSS Design System, Responsive SPA JavaScript
- **Database**: Neon Serverless PostgreSQL (or local SQLite)
- **Deployment**: Vercel Serverless Functions

---

## 🚀 Getting Started

### 1. Clone & Setup

```bash
git clone https://github.com/midhun2386/CLINIC-MANAGEMENT.git
cd CLINIC-MANAGEMENT
pip install -r requirements.txt
```

### 2. Environment Variables

Copy `.env.example` to `.env` and fill in your keys:

```bash
cp .env.example .env
```

```env
SECRET_KEY=your-production-secret-key
DATABASE_URL=postgresql://user:pass@ep-xyz-pooler.region.neon.tech/neondb?sslmode=require
GEMINI_API_KEY=your-gemini-api-key
```

### 3. Initialize & Seed Database

```bash
python backend/seed.py
```

- **Default Admin**: `admin@clinic.com` / `admin123`
- **Default Staff**: `staff1@clinic.com` / `staff123`

### 4. Run Development Server

```bash
python run.py
```

Visit [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

---

## ☁️ Deployment on Vercel

1. Import this repository into Vercel.
2. In **Project Settings > Environment Variables**, add:
   - `DATABASE_URL` (Neon PostgreSQL pooled connection string)
   - `SECRET_KEY` (Secret string for JWT tokens)
   - `GEMINI_API_KEY` (Google Gemini API key)
3. Deploy! Vercel automatically detects `run:app` via `pyproject.toml` and `index.py`.
