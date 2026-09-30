# LearnCraft networking — local, LAN, hotspot, online link, Docker, Internet
#
# TL;DR: double-click `run_server.bat` (or `./run_server.ps1`) for this laptop
# only; add `lan` / `-Lan` for phones/tablets on the same Wi-Fi or hotspot;
# add `share` / `-Share` for a temporary PUBLIC https link + QR code that any
# phone can open from any network (4G, guest Wi-Fi, home).
# The server prints the exact URLs — copy the LAN line to the other device.
# Everything is same-origin: the same build works on localhost, any LAN IP,
# any hotspot IP, a tunnel URL, and any deployed domain with zero rebuilds.

## 1. Local mode (this laptop only, default)

```powershell
.\run_server.bat
# or
.\run_server.ps1
```

- Binds `127.0.0.1:5000` — nothing leaves the laptop.
- Open `http://localhost:5000` (or `http://127.0.0.1:5000`).
- Env overrides: `APP_HOST` (default `127.0.0.1`), `APP_PORT` (default `5000`).

## 2. LAN mode (other devices on the same Wi-Fi)

```powershell
.\run_server.bat lan
# or
.\run_server.ps1 -Lan
# custom port:
.\run_server.ps1 -Lan -Port 8080
```

1. Start with the `lan` flag (binds `0.0.0.0`, i.e. every local interface).
2. Read the startup banner, e.g.:
   `Local: http://localhost:5000` + `LAN: http://192.168.1.42:5000`.
3. On the phone/tablet (same Wi-Fi), open the LAN URL.
4. Windows Firewall: on first LAN start Windows asks
   "Allow Python to communicate on these networks?" — tick
   **Private networks** and Allow. Manual fallback (admin PowerShell):
   `netsh advfirewall firewall add rule name="LearnCraft TCP 5000" dir=in action=allow protocol=TCP localport=5000`

Do NOT hard-code the IP anywhere: it changes per network. The banner
detects all private IPv4 addresses (Wi-Fi + Ethernet + hotspot) every start.

## 3. Hotspot mode (laptop shares Internet; phone joins the hotspot)

Same as LAN — a hotspot is just another LAN whose DHCP address changes often:

1. Windows Settings → Network → Mobile hotspot → turn On (Wi-Fi or USB).
2. Connect the phone to the hotspot network.
3. `.\run_server.bat lan` (or `-Lan`) on the laptop.
4. Copy the freshly printed `LAN: http://<hotspot-IP>:5000` to the phone.
   (Typically `192.168.137.1` on Windows, but always use the banner value.)
5. Same firewall prompt as LAN mode (allow TCP port once per network type).

If the phone shows "site can't be reached": re-check the banner IP (it may
have changed when the hotspot restarted), confirm both devices show the same
hotspot name, and confirm the firewall rule covers the active profile.

## 4. Offline-first mode (no Internet at all)

Disconnect Wi-Fi / unplug Ethernet — everything below keeps working:

- Startup needs nothing from the network (stdlib `.env` parsing, local
  SQLite at `backend/data/learncraft.db`, bundled `/static` assets).
- Lessons, quizzes, notes, progress, practical/assignment work persist to
  the local API (`/api/local/state`) and queue into SQLite `sync_queue`.
- Bundled sandboxes (Math, Physics, Circuits, Coding) run fully offline;
  external providers (PhET, GeoGebra, …) are labelled online-only and are
  disabled while `navigator.onLine` is false.
- AI: cloud providers are optional and isolated — `LEARNCRAFT_AI_MODE=OFFLINE`
  (or simply no API key / no network) uses the built-in local tutor and any
  detected local LLM (Ollama/LM Studio); core learning never needs the cloud.
- PWA service worker caches shell + static assets for revisit, but NEVER
  caches `/api/*` or auth pages, so no stale/private data is served.

## 5. Online link — phone on ANY network (temporary public URL + QR)

Same Wi-Fi is not always possible: students are at home, phones are on 4G, or
guest Wi-Fi blocks device-to-device traffic. This mode opens a **temporary
public HTTPS link** through a tunnel — no router port forwarding, no static IP,
no VPS, no DNS:

```powershell
.\run_server.bat share                 # Windows cmd  (add a port: share 8080)
.\run_server.ps1 -Share                # PowerShell   (-Share -Tool ssh)
python backend\scripts\share_online.py --port 5000   # any OS, direct
```

1. The server starts bound to `0.0.0.0` (LAN **and** tunnel); the tunnel client
   is auto-detected in this order:

   | tool | account needed | public link looks like | install |
   |---|---|---|---|
   | `cloudflared` | none | `https://<random>.trycloudflare.com` | `winget install --id Cloudflare.cloudflared` |
   | `ngrok` | free token | `https://<random>.ngrok-free.app` | `winget install ngrok.ngrok`, then `ngrok config add-authtoken <token>` |
   | `ssh` | none | `https://<random>.lhr.life` | already included in Windows 10+/macOS/Linux |

2. The banner prints the public link **and a scannable QR code** — point a phone
   camera at the screen to open it. The LAN URL is printed too: use it when the
   phone is in the same room (faster, no relay).
3. Several devices can use the link at the same time; each browser gets its own
   login session.
4. `Ctrl+C` closes the public link and stops the server.

Notes and limits:

- The link is **public**: anyone who has it reaches the login page. Use real
  account passwords, share it only for the lesson, and close the window after.
- Free tiers give a **new random URL every start**; the previous URL stops
  working as soon as the window closes.
- School/office firewalls sometimes block tunnels. If no URL appears within a
  minute, try the other provider (`-Tool ssh` / `--tool cloudflared`) or use
  LAN/hotspot mode.
- Options: `--no-qr` (narrow terminals), `--no-server` (tunnel an already
  running server), `--host 127.0.0.1` (tunnel only, no LAN exposure),
  `--timeout` seconds to wait for the URL. Environment: `LEARNCRAFT_SHARE_*`
  (see the table below).
- This is a **temporary lesson link**, not a deployment: for a permanent HTTPS
  site (own domain, always-on) follow §7.

## 6. Docker (same behaviour, production server inside)

```powershell
copy docker\.env.docker.example docker\.env
# edit docker\.env → set LEARNCRAFT_SECRET_KEY (and APP_PORT if you want :8080)
# NOTE: Compose reads .env from the compose file's folder (docker/.env); a
# root-level .env needs "docker compose --env-file .env -f ..." instead.
# Starting without a key fails fast instead of using a known default.
docker compose -f docker\docker-compose.yml up --build -d
# open http://localhost:5000  (or http://localhost:8080 with APP_PORT=8080)
docker compose -f docker\docker-compose.yml logs -f
```

- Container listens on `0.0.0.0:${APP_PORT:-5000}` via gunicorn (4 workers);
  host mapping follows the same `APP_PORT` so same-origin keeps working.
- Liveness probe: `GET /api/health` (used by Dockerfile + compose).
- Local dev still works: `backend/data` and `frontend` are mounted volumes.

## 7. Internet / remote mode (permanent VPS deployment)

Never expose `python server.py` (the Flask dev server) publicly. Deploy the
gunicorn container behind Caddy/nginx which terminates HTTPS — full steps,
configs, and the security checklist are in
[`docs/deployment/production.md`](production.md) (Caddy automatic-TLS option
+ nginx+certbot option).

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `APP_HOST` | `127.0.0.1` | Bind interface. `0.0.0.0` = LAN + hotspot. |
| `APP_PORT` / `PORT` | `5000` | Bind + advertised port (Docker + PaaS aware). |
| `APP_ENV` | `development` | `development` or `production` (Secure cookies, ProxyFix, no debug, strict CORS). |
| `CORS_ORIGINS` | (empty) | Comma-separated extra frontend origins. Empty = same-origin only (normal). `*` allowed in dev only. |
| `APP_TRUST_PROXY` | auto | `1` behind a reverse proxy (compose sets it). Production defaults on. |
| `FLASK_DEBUG` / `APP_DEBUG` | off | Debugger opt-in, local only — never in production. |
| `LEARNCRAFT_SECRET_KEY` | (required) | Session signing key. Auto-created by `run_server.*` into `backend/.secret_key`. Never commit. |
| `LEARNCRAFT_DB_PATH` | `data/learncraft.db` | SQLite file (local-first, offline). |
| `LEARNCRAFT_NETWORK_MODE` | `OFFLINE` | Content mode (`OFFLINE` default). |
| `LEARNCRAFT_MASTER_URL` | (empty) | Reserved for a future local master server. |
| `LEARNCRAFT_SHARE_TOOL` | auto | §5 tunnel provider: `auto`, `cloudflared`, `ngrok`, `ssh`. |
| `LEARNCRAFT_SHARE_HOST` | `0.0.0.0` | §5 bind address (`127.0.0.1` = tunnel only, no LAN). |
| `LEARNCRAFT_SHARE_QR` | `1` | Print the scannable QR code in the share banner (`0` = off). |
| `LEARNCRAFT_SHARE_TIMEOUT` | `60` | Seconds to wait for the provider to report its public URL. |
| AI / mail | see `.env.example` | Optional cloud AI keys + SMTP OTP (both degrade offline-safe). |

`APP_HOST`/`APP_PORT`/`APP_ENV` win over the legacy `LEARNCRAFT_HOST` /
`LEARNCRAFT_PORT` / `FLASK_ENV` when both are set.
