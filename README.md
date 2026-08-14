# Fetchr — YouTube & Instagram Downloader

A clean, modern media downloader with a web UI that also works as a **Telegram Mini App**.
Built with Flask + yt-dlp on the backend and a self-contained Tailwind + Motion + Lucide frontend.

## Features
- Download from YouTube & Instagram (best / MP4 video / MP3 audio).
- Persistent storage on a **Railway volume (500 MB)** — files survive restarts.
- **Web UI**: dark, glassy, animated (Motion entrance + hover + staggered lists), Lucide icons, accent switcher.
- **Telegram Mini App**: opens inside Telegram and adapts to its theme.
- **Settings tab**: paste a YouTube `cookies.txt` for age-restricted / members-only content, pick default format, pick accent color.
- **Delete files** from the UI (trash icon on every file row).
- Empty / loading (skeleton) / error (toast) states.

## Deploy on Railway
1. Create a new Railway project → **Empty Service** → **Deploy from GitHub repo** (this repo) or connect via CLI.
2. The `railway.json` already declares the `/data` volume (0.5 GB) and the healthcheck.
3. Railway auto-detects the `Dockerfile`. Deploy. The service listens on `$PORT` (default 5000).

Files are saved to `/data` (the mounted volume). The 500 MB cap is enforced by Railway's volume size.

## Run locally
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
mkdir -p downloads && DOWNLOAD_DIR=./downloads python app.py
# open http://localhost:5000
```

## Telegram Mini App
In @BotFather → your bot → Menu Button / Mini App → set the URL to your deployed app.
The app reads `Telegram.WebApp.themeParams` to match the chat theme automatically.

## API
| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Healthcheck |
| GET/POST | `/api/settings` | Read / save settings (cookies, default format, accent) |
| POST | `/api/download` | Queue a download `{url, format}` → `{job_id}` |
| GET | `/api/jobs/<id>` | Poll job status |
| GET | `/api/files` | List downloaded files |
| DELETE | `/api/files/<name>` | Delete a file |
| GET | `/d/<name>` | Download a saved file |

> YouTube login cookies are stored only in the volume as `cookies` text. They are never logged.
