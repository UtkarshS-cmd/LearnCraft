# LearnCraft production deployment (VPS / cloud server)
#
# Just need a phone (or several) to open LearnCraft for a lesson, right now?
# Use the temporary tunnel link instead — one command, no server, no DNS:
#     run_server.bat share     (or run_server.ps1 -Share)
# see docs/deployment/networking.md §5. This document is for a permanent,
# always-on deployment with your own domain and HTTPS.
#
# Architecture (never expose the Flask dev server to the Internet):
#
#   Internet
#     |
#   HTTPS (:443, cert via Caddy automatic TLS or certbot for nginx)
#     |
#   Reverse proxy (Caddy or nginx) — terminates TLS, forwards plain HTTP
#     |
#   LearnCraft container (gunicorn, 4 workers) on 127.0.0.1:${APP_PORT:-5000}
#     |  (repo layout preserved: /app/backend + /app/frontend, same as local)
#     |
#   SQLite at /app/backend/data/learncraft.db (Docker volume; backed up by operator)
#
# Same-origin note: the frontend is server-rendered by Flask and every
# fetch() uses a relative path (/api/..., /auth/...), so one public origin
# serves both UI and API. No frontend rebuild is needed per domain, LAN IP,
# or hotspot IP. CORS_ORIGINS stays empty unless you deploy a SECOND,
# separate frontend origin that calls this API.
#
# ---------------------------------------------------------------------------
# Option A — Caddy (simplest: automatic HTTPS, ~5 minutes)
# ---------------------------------------------------------------------------
# 1. Point DNS:  learn.example.com  ->  <server public IP>
# 2. On the server:
#
#      # docker/.env — same folder as docker-compose.yml (Compose loads it
#      # automatically; a repo-root .env needs --env-file .env)
#      LEARNCRAFT_SECRET_KEY=<python -c "import secrets; print(secrets.token_hex(32))">
#      APP_ENV=production
#      APP_PORT=5000
#      # CORS_ORIGINS=   (leave empty for same-origin)
#
#      docker compose -f docker/docker-compose.yml up --build -d
#      # A missing key aborts with an explicit message instead of starting
#      # with a publicly known development secret.
#
# 3. /etc/caddy/Caddyfile:
#
#      learn.example.com {
#          reverse_proxy 127.0.0.1:5000
#      }
#
#      # systemctl reload caddy
#
# Caddy fetches and renews the TLS certificate automatically. The app sees
# the real client scheme via X-Forwarded-Proto because APP_TRUST_PROXY=1
# (set in docker-compose.yml), so logins/cookies stay `https` + `Secure`.
#
# ---------------------------------------------------------------------------
# Option B — nginx + certbot (when you already run nginx)
# ---------------------------------------------------------------------------
# 1. Same DNS + compose steps as Option A.
# 2. /etc/nginx/sites-available/learncraft:
#
#      # Plain HTTP only proxies to the app; nothing else is exposed.
#      # (DB has no port mapping at all — SQLite lives inside the volume.)
#      upstream learncraft { server 127.0.0.1:5000; }
#      server {
#          listen 80;
#          server_name learn.example.com;
#          location / {
#              proxy_pass http://learncraft;
#              proxy_set_header Host $host;
#              proxy_set_header X-Real-IP $remote_addr;
#              proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
#              proxy_set_header X-Forwarded-Proto $scheme;
#              proxy_read_timeout 120s;
#          }
#      }
#
# 3. HTTPS:  certbot --nginx -d learn.example.com
#    (certbot adds the :443 block; the proxy headers above stay as-is.)
#
# ---------------------------------------------------------------------------
# Production checklist (security — do not skip)
# ---------------------------------------------------------------------------
# - LEARNCRAFT_SECRET_KEY: unique 64-hex chars, stored only in server .env,
#   never committed. Changing it signs everyone out (expected).
# - APP_ENV=production: enables Secure cookies, disables the Werkzeug
#   debugger unconditionally, and makes CORS "*" resolve to same-origin-only.
# - CORS_ORIGINS: leave empty (same-origin). Only add an explicit origin
#   (https://..., no trailing slash) for a separate frontend; never "*".
# - Firewall: allow 80/443 (and 22 for admin) ONLY. The app port (5000) must
#   NOT be public — bind/publish it on 127.0.0.1 or keep it inside the
#   Docker network. Example (ufw):  ufw allow 80,443/tcp   (and NOT 5000).
# - Backups: snapshot the Docker volume holding /app/backend/data/learncraft.db
#   (plus -wal/-shm sidecars) nightly; test restores.
# - Updates: docker compose pull/build + up -d; health endpoint for
#   monitoring/load-balancers:  GET /api/health  ->  {"status":"ok",...}
# - Debug: never set FLASK_DEBUG=1 / APP_DEBUG=1 in production. Debug mode
#   executes code from the network and must stay a local-only tool.
#
# ---------------------------------------------------------------------------
# Offline-first reminder
# ---------------------------------------------------------------------------
# Core learning (lessons, quizzes, sandboxes, progress, submissions into the
# local SQLite queue) works with zero Internet. Only optional features need
# it: cloud AI providers (isolated behind LEARNCRAFT_AI_MODE, falls back to
# the built-in local tutor), external link-out simulations (PhET, GeoGebra…,
# labelled data-online-only and disabled offline), and SMTP OTP email
# (offline direct password reset always still works).
