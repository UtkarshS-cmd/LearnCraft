# LearnCraft

LearnCraft is an offline-first learning platform with a Flask backend, SQLite persistence, and server-rendered templates.

## Quick start

### Simple method (recommended) - Just double-click to run!

The easiest way to run LearnCraft is to use the provided runner scripts. They handle everything automatically:

- **Windows (Batch)**: Double-click `run_server.bat` or run `run_server.bat` from Command Prompt
- **Windows (PowerShell)**: Run `.\run_server.ps1` from PowerShell

That's it! The script will:
1. Create a virtual environment if it doesn't exist
2. Install dependencies automatically
3. Generate a secure secret key (saved locally, never committed to git)
4. Start the Flask server on http://localhost:5000

```powershell
# Option 1: Run from project root (CMD or PowerShell)
.\run_server.bat

# Option 2: Run with PowerShell
.\run_server.ps1
```

### Manual method

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python server.py
```

## Desktop application

Run the same local-first application in an app-style browser window:

```powershell
.venv\Scripts\python.exe desktop.py
```

The launcher selects an available loopback port, starts the Flask server
without the debug reloader, and opens Microsoft Edge or Chrome in app mode.
If neither browser is installed, it opens the default browser instead. Stop
the desktop application with `Ctrl+C`.

## Password reset (offline, no OTP needed)

On an incorrect login, users can set a new password directly from the "Forgot password?" link — email + new password, no OTP code required. The app works fully offline without SMTP. Optionally configure SMTP to also email a one-time code (best-effort); a direct reset always works as fallback:

```powershell
$env:LEARNCRAFT_MAIL_HOST = "smtp.example.com"
$env:LEARNCRAFT_MAIL_PORT = "587"
$env:LEARNCRAFT_MAIL_USERNAME = "smtp-user"
$env:LEARNCRAFT_MAIL_PASSWORD = "smtp-password"
$env:LEARNCRAFT_MAIL_FROM = "no-reply@example.com"
```

When an OTP is emailed, it expires after 10 minutes and is stored only as a hash. Direct (OTP-free) resets are always available offline.

## Project structure

```
LearnCraft/
├── backend/                 # Backend application code
│   ├── app/                 # Flask application package
│   │   ├── api/             # API endpoints
│   │   ├── core/            # Core utilities (security, config, middleware)
│   │   ├── database/        # Database connection and models
│   │   ├── dependencies/    # Dependency injection
│   │   ├── models/          # Data models
│   │   ├── repositories/    # Data access layer
│   │   ├── routes/          # Web routes
│   │   ├── schemas/         # Pydantic schemas
│   │   ├── services/        # Business logic
│   │   └── utils/           # Utility functions
│   ├── data/                # SQLite DB and seed assets
│   │   ├── curriculum/      # CBSE/NCERT structured seed packages
│   │   ├── seed/            # Seed data (lessons, mock data)
│   │   └── ...              # Other data directories
│   ├── docs/                # Architecture and API documentation
│   ├── scripts/             # Utility scripts (tests, validation, imports)
│   ├── tests/               # Unit, integration, and e2e tests
│   ├── desktop.py           # Desktop app launcher
│   ├── requirements.txt     # Python dependencies
│   ├── server.py            # Server entry point
│   └── logs/                # Application logs
├── docker/                  # Docker configuration
│   ├── Dockerfile           # Docker image definition
│   ├── docker-compose.yml   # Docker Compose orchestration
│   ├── .dockerignore        # Files excluded from Docker build
│   └── .env.docker.example  # Environment variable template
├── frontend/                # Frontend templates and static assets
│   ├── templates/           # Jinja2 HTML templates
│   │   ├── components/      # Reusable template components
│   │   └── pages/           # Page templates
│   └── static/              # Static files (CSS, JS, images)
│       ├── sandbox-games/   # Offline games (circuits, coding)
│       └── ...              # Other static assets
├── .env.example             # Environment variable example (root)
├── .gitignore               # Git ignore rules
├── OFFLINE_FIRST.md         # Offline-first architecture notes
└── README.md                # This file
```

Key directories:
- `backend/app/` — application package with core, API, services, repositories, models, and utilities
- `backend/data/` — SQLite DB and seed assets
- `backend/data/curriculum/` — versioned CBSE/NCERT structured seed packages
- `backend/data/curriculum/ncert_class10_syllabus.json` — extracted Class 10 NCERT Science and Social Studies question bank used by Ask AI for exact offline answers
- `frontend/` — templates and static frontend assets
- `frontend/static/sandbox-games/circuits/` — bundled offline electrical circuits lab integrated from the Simulations project
- `frontend/static/sandbox-games/coding/` — bundled offline Coding Adventure with guided JavaScript missions
- `backend/tests/` — unit, integration, and e2e tests
- `backend/docs/` — architecture and API documentation
- `backend/scripts/validate_content.py` — fail-fast content validation
- `backend/scripts/import_content.py` — transactional catalog import
- `backend/scripts/ingest_sources.py` — official-source download/checksum helper
- `backend/scripts/smoke_test.py` — boots the app and checks every page and read API
- `backend/scripts/route_sweep.py` — hits every registered route as anonymous, student and teacher
- `backend/scripts/functional_test.py` — exercises every write endpoint (student + teacher flows)
- `backend/scripts/live_http_test.py` — starts a real server process and tests it over HTTP
- `backend/scripts/check_assets.py` — flags `/static/...` references that do not exist on disk
- `docker/` — Docker configuration files

## Docker

### Build and run with Docker Compose

```powershell
# Copy the environment template
copy docker\.env.docker.example .env

# Edit .env and set LEARNCRAFT_SECRET_KEY

# Build and start (from project root)
docker-compose -f docker\docker-compose.yml up --build -d

# View logs
docker-compose -f docker\docker-compose.yml logs -f

# Stop
docker-compose -f docker\docker-compose.yml down
```

### Build and run with Docker directly

```powershell
# Build the image
docker build -t learncraft:latest -f docker\Dockerfile .

# Run the container
docker run -d --name learncraft -p 5000:5000 `
  -v ${PWD}\backend\data:/app/data `
  -v ${PWD}\frontend:/app/frontend `
  -e LEARNCRAFT_SECRET_KEY="your-secret-key" `
  learncraft:latest
```

### Environment variables

The application requires these environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `LEARNCRAFT_SECRET_KEY` | (required) | Secret key for session encryption |
| `LEARNCRAFT_DB_PATH` | `/app/data/learncraft.db` | SQLite database path |
| `LEARNCRAFT_NETWORK_MODE` | `OFFLINE` | Network mode: OFFLINE, ONLINE, or AUTO |
| `LEARNCRAFT_MASTER_URL` | (empty) | Master server URL for multi-instance setups |

Optional AI configuration:
- `LEARNCRAFT_AI_MODE` - AUTO, ONLINE, or OFFLINE
- `OPENAI_API_KEY`, `GROQ_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY` - Cloud API keys

Optional email configuration (for password reset OTPs):
- `LEARNCRAFT_MAIL_HOST`, `LEARNCRAFT_MAIL_PORT`, `LEARNCRAFT_MAIL_USERNAME`, `LEARNCRAFT_MAIL_PASSWORD`, `LEARNCRAFT_MAIL_FROM`

## Verification

Run these before shipping a change. Each script exits non-zero on failure.

```powershell
.venv\Scripts\python.exe -m pytest tests -q
.venv\Scripts\python.exe scripts\validate_content.py
.venv\Scripts\python.exe scripts\smoke_test.py
.venv\Scripts\python.exe scripts\route_sweep.py
.venv\Scripts\python.exe scripts\functional_test.py
.venv\Scripts\python.exe scripts\live_http_test.py
.venv\Scripts\python.exe scripts\check_assets.py
```

## Notes

The project is intentionally built to stay compatible with the existing Flask application while exposing a more structured architecture for future expansion.
