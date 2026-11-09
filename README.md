# ⚡ TaskPulse (Trackly)

> **Operational Task Management & Delegation Platform** built with **FastAPI**, **SQLAlchemy 2.0 (Async)**, **PostgreSQL**, and **Pydantic v2**, tailored for production deployment on **Render**.

[![Render](https://img.shields.io/badge/Render-Ready-46E3B7?style=flat&logo=render)](https://render.com)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=flat&logo=python)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 🌟 Key Features

1. **Read Receipts & Acknowledgment:**
   - When an assigned team member opens a task, its status automatically transitions from `TODO` to `SEEN`, stamping an immutable `seen_at` timestamp.
   - Eliminates "I didn't see the assignment" excuses.

2. **Activity & Audit Trail:**
   - Persistent timeline on every task: $\text{Created} \rightarrow \text{Seen} \rightarrow \text{In Progress} \rightarrow \text{Pending Review} \rightarrow \text{Completed}$.
   - Team members and leaders can post progress updates, notes, deliverables, and attachment URLs.

3. **Leader Verification Loop:**
   - Members cannot arbitrarily mark tasks complete; they transition tasks to `PENDING_REVIEW` with completion notes.
   - The team leader reviews the deliverables, inspects work, and either signs off as `COMPLETED` or requests revisions with feedback notes.

4. **Priority & SLA Badges:**
   - Prioritize work using `LOW`, `MEDIUM`, `HIGH`, or `CRITICAL` levels.
   - Visual overdue and approaching deadline indicators.

5. **Dual Notification Engine:**
   - **In-App Persistent Notifications:** Notification bell with live unread counter and mark-as-read controls.
   - **Asynchronous SMTP Email Dispatch:** HTML notifications dispatched in the background via FastAPI `BackgroundTasks`.

6. **Executive Dashboard:**
   - Modern dark/light UI built with Tailwind CSS and Alpine.js, served directly from FastAPI at `/`.
   - Interactive Swagger UI at `/docs` and ReDoc at `/redoc`.

---

## 🏗️ Architecture & Relational Schema

```text
trackly/
├── backend/                  # FastAPI Application Service
│   ├── alembic/              # Database migration versions & env
│   ├── alembic.ini           # Alembic config
│   ├── app/                  # Application source
│   │   ├── api/              # REST API v1 endpoints
│   │   ├── core/             # Configuration & security
│   │   ├── db/               # Async database session & engine
│   │   ├── models/           # SQLAlchemy models
│   │   ├── schemas/          # Pydantic v2 schemas
│   │   ├── services/         # Email & notifications
│   │   └── main.py           # FastAPI entrypoint
│   ├── Dockerfile            # Container configuration
│   ├── requirements.txt      # Python dependencies
│   └── .env.example          # Environment template
│
├── frontend/                 # Static Site SPA
│   ├── index.html            # Executive Dashboard HTML
│   ├── app.js                # Alpine.js reactive app logic
│   ├── config.js             # Runtime Backend API configuration
│   └── README.md             # Frontend dev notes
│
├── render.yaml               # Render Blueprint (Backend Web + Frontend Static + PostgreSQL)
└── README.md
```

---

## 🏗️ Relational Schema

```text
users
├── id (UUID, PK)
├── email (Unique, Indexed)
├── hashed_password (Bcrypt)
├── full_name
├── role ('LEADER' | 'MEMBER')
└── created_at

tasks
├── id (UUID, PK)
├── title
├── description
├── priority ('LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL')
├── status ('TODO' | 'SEEN' | 'IN_PROGRESS' | 'PENDING_REVIEW' | 'COMPLETED')
├── leader_id (FK -> users.id, CASCADE)
├── assignee_id (FK -> users.id, SET NULL)
├── due_date (Nullable)
├── seen_at (Timestamp, Nullable)
├── created_at
└── updated_at

task_updates
├── id (UUID, PK)
├── task_id (FK -> tasks.id, CASCADE)
├── user_id (FK -> users.id, CASCADE)
├── message (Text)
├── attachment_url (Nullable)
└── created_at

notifications
├── id (UUID, PK)
├── user_id (FK -> users.id, CASCADE)
├── task_id (FK -> tasks.id, CASCADE)
├── message (Text)
├── is_read (Boolean)
└── created_at
```

---

## 🚀 Quick Start (Local Development)

### 1. Backend Setup
```bash
cd backend

# Create virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env

# Run database migrations
alembic upgrade head

# Start FastAPI server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
Backend API will be accessible at:
- **API Spec & Interactive Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check:** [http://localhost:8000/healthz](http://localhost:8000/healthz)

### 2. Frontend Setup
In a new terminal:
```bash
cd frontend

# Serve frontend using any static server:
# Using Python:
python -m http.server 3000

# Or using Node:
# npx serve .
```
Open [http://localhost:3000](http://localhost:3000) in your browser.
The frontend is already configured to connect to `http://localhost:8000` or can be adjusted anytime via the **API Settings** button in the header.

---

## 🐳 Docker Deployment

Build and run the backend using Docker:
```bash
cd backend
docker build -t taskpulse-backend .

docker run -p 8000:8000 \
  -e DATABASE_URL="postgresql+asyncpg://user:password@host:5432/dbname" \
  -e SECRET_KEY="your-production-secret-key" \
  taskpulse-backend
```

---

## ☁️ Deploying to Render (Blueprint)

This repository includes a monorepo [`render.yaml`](render.yaml) Blueprint that automatically provisions:
1. **`taskpulse-db`**: A managed PostgreSQL database (free tier).
2. **`taskpulse-backend`**: A Python Web Service hosting FastAPI, automatically running `alembic upgrade head` and connected to the database.
3. **`taskpulse-frontend`**: A Render Static Site hosting the Alpine.js/Tailwind SPA with SPA rewrite routes.

### Deployment Steps:
1. Push this repository to GitHub or GitLab.
2. In the Render Dashboard, click **New +** $\rightarrow$ **Blueprint**.
3. Select this repository.
4. Render will detect the database, backend Web Service, and frontend Static Site in [`render.yaml`](render.yaml).
5. Click **Apply**.
6. Once deployed:
   - Your frontend URL will be: `https://taskpulse-frontend.onrender.com`
   - Your backend URL will be: `https://taskpulse-backend.onrender.com`
   - Enter your backend URL in `frontend/config.js` or directly click the **API Status** pill in the frontend header to connect.

---

## 📡 API Endpoints Overview

| Method | Endpoint | Role | Description |
|---|---|---|---|
| `POST` | `/api/v1/auth/register` | Public | Register as `LEADER` or `MEMBER` |
| `POST` | `/api/v1/auth/login` | Public | OAuth2 password token login |
| `POST` | `/api/v1/auth/login/json`| Public | JSON credentials login |
| `GET`  | `/api/v1/auth/me` | Authenticated | Current user profile |
| `GET`  | `/api/v1/users/members` | Authenticated | List registered members for assignment |
| `POST` | `/api/v1/tasks/` | Leader | Create task, assign member, trigger email |
| `GET`  | `/api/v1/tasks/` | Authenticated | List tasks (filtered by status/priority) |
| `GET`  | `/api/v1/tasks/metrics` | Authenticated | Aggregate status counts |
| `GET`  | `/api/v1/tasks/{id}` | Authenticated | Inspect task (triggers `seen_at` read receipt) |
| `PATCH`| `/api/v1/tasks/{id}` | Leader | Update task details or reassign |
| `PATCH`| `/api/v1/tasks/{id}/status` | Authenticated | Update status (`IN_PROGRESS`, `PENDING_REVIEW`, `COMPLETED`) |
| `DELETE`| `/api/v1/tasks/{id}` | Leader | Delete task |
| `POST` | `/api/v1/tasks/{id}/updates` | Authenticated | Post comment / deliverable note |
| `GET`  | `/api/v1/tasks/{id}/updates` | Authenticated | Activity & audit trail |
| `GET`  | `/api/v1/notifications/` | Authenticated | List persistent notifications & unread count |
| `PATCH`| `/api/v1/notifications/{id}/read` | Authenticated | Mark notification read |
| `POST` | `/api/v1/notifications/read-all` | Authenticated | Mark all notifications read |
| `GET`  | `/healthz` | Public | Readiness and database probe |

