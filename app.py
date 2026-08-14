import os, json, threading, uuid, tempfile, re, sys, subprocess
from flask import Flask, request, jsonify, send_from_directory
import yt_dlp

DOWNLOAD_DIR = os.environ.get("DOWNLOAD_DIR", "/data")
SETTINGS_FILE = os.path.join(DOWNLOAD_DIR, ".settings.json")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ponytail: single global lock — serializes downloads so two big files can't
# exhaust the 500MB volume at once. Per-user locks if multi-tenant later.
dl_lock = threading.Lock()
jobs = {}  # id -> {status, error, files}

def update_ytdlp():
    # ponytail: YouTube format manifests change constantly; a pinned yt-dlp goes
    # stale in weeks. Self-update on boot (non-fatal: keep build if no network).
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-U", "yt-dlp"],
                       capture_output=True, timeout=180)
    except Exception:
        pass

def build_format(fmt, quality):
    # ponytail: greedy [ext=mp4] chains can fail when a video has no MP4 stream;
    # the trailing /best fallback + merge_output_format guarantees a result.
    if fmt == "mp3":
        return "bestaudio/best", True, None
    if fmt == "best":
        return "best", False, None
    h = int(quality) if quality and str(quality).isdigit() else None
    if h:
        sel = (f"bv[height<={h}][ext=mp4]+ba[ext=m4a]/"
               f"b[height<={h}][ext=mp4]/"
               f"bv[height<={h}]+ba/b[height<={h}]/best[height<={h}]/best")
    else:
        sel = "bv[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best"
    return sel, False, "mp4"

def run_download(job_id, url, preset, cookies_text):
    # ponytail: layered retry so transient failures never reach the UI:
    #   1) chosen format (+cookie) 2) best (+cookie) 3) best WITHOUT cookie.
    # A stored/expired cookie can break the request (metube works without one),
    # so the final no-cookie attempt mirrors a working bare downloader.
    try:
        with dl_lock:
            fmt = preset.get("type", "best") if isinstance(preset, dict) else preset
            quality = preset.get("quality") if isinstance(preset, dict) else None
            primary = build_format(fmt, quality)
            fallback = ("bestaudio/best", True, None) if fmt == "mp3" else ("best", False, None)
            attempts = [(primary[0], primary[1], primary[2], True),
                        (fallback[0], fallback[1], fallback[2], True)]
            if cookies_text and cookies_text.strip():
                attempts.append((fallback[0], fallback[1], fallback[2], False))
            last_err = None
            cookiefile = None
            for sel, is_audio, merge, use_cookie in attempts:
                opts = {
                    "outtmpl": os.path.join(DOWNLOAD_DIR, "%(title)s [%(id)s].%(ext)s"),
                    "noplaylist": True,
                    "quiet": True,
                    "no_warnings": True,
                    "format": sel,
                }
                if merge:
                    opts["merge_output_format"] = merge
                if is_audio:
                    opts["postprocessors"] = [{
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }]
                if use_cookie and cookies_text and cookies_text.strip():
                    fd, cookiefile = tempfile.mkstemp(suffix=".txt", prefix="cookies_")
                    with os.fdopen(fd, "w") as cf:
                        cf.write(cookies_text)
                    opts["cookiefile"] = cookiefile
                try:
                    files = []
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        info = ydl.extract_info(url, download=True)
                        if info:
                            for rd in info.get("requested_downloads", []):
                                p = rd.get("filepath")
                                if p and os.path.exists(p):
                                    files.append(p)
                            if not files and info.get("_filename") and os.path.exists(info["_filename"]):
                                files.append(info["_filename"])
                    jobs[job_id] = {"status": "done", "error": None, "files": files}
                    return
                except Exception as e:
                    last_err = e
                finally:
                    if cookiefile and os.path.exists(cookiefile):
                        try:
                            os.remove(cookiefile)
                        except Exception:
                            pass
                        cookiefile = None
            jobs[job_id] = {"status": "error", "error": str(last_err), "files": []}
    except Exception as e:
        jobs[job_id] = {"status": "error", "error": str(e), "files": []}


def load_settings():
    try:
        with open(SETTINGS_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def save_settings(d):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(d, f, indent=2)


def safe_path(name):
    if not name or name.startswith(".") or "/" in name or "\\" in name or name == "..":
        return None
    base = os.path.abspath(DOWNLOAD_DIR)
    p = os.path.normpath(os.path.join(base, name))
    if p != base and not p.startswith(base + os.sep):
        return None
    return p


def list_files():
    items = []
    for name in os.listdir(DOWNLOAD_DIR):
        if name.startswith(".") or name.startswith("cookies_") or ".part" in name:
            continue
        p = os.path.join(DOWNLOAD_DIR, name)
        if os.path.isfile(p):
            st = os.stat(p)
            items.append({"name": name, "size": st.st_size, "mtime": int(st.st_mtime)})
    items.sort(key=lambda x: x["mtime"], reverse=True)
    return items


app = Flask(__name__, static_folder=None)


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/api/health")
def health():
    return jsonify({"ok": True})


@app.route("/api/settings", methods=["GET"])
def get_settings():
    s = load_settings()
    masked = bool(s.get("yt_cookies"))
    out = {k: v for k, v in s.items() if k != "yt_cookies"}
    out["has_cookies"] = masked
    return jsonify(out)


@app.route("/api/settings", methods=["POST"])
def post_settings():
    d = request.get_json(force=True, silent=True) or {}
    s = load_settings()
    if d.get("clear_cookies"):
        s.pop("yt_cookies", None)
    elif "yt_cookies" in d and d["yt_cookies"].strip():
        s["yt_cookies"] = d["yt_cookies"]
    if "default_format" in d:
        s["default_format"] = d["default_format"]
    if "accent" in d:
        s["accent"] = d["accent"]
    s["yt_cookies"] = s.get("yt_cookies", "")
    save_settings(s)
    return jsonify({"ok": True})


@app.route("/api/download", methods=["POST"])
def download():
    d = request.get_json(force=True, silent=True) or {}
    url = (d.get("url") or "").strip()
    if not re.match(r"^https?://", url):
        return jsonify({"error": "Invalid URL"}), 400
    preset_raw = d.get("format") or load_settings().get("default_format", "best")
    if isinstance(preset_raw, dict):
        preset = preset_raw
    else:
        preset = {"type": preset_raw, "quality": d.get("quality")}
    job_id = uuid.uuid4().hex
    jobs[job_id] = {"status": "pending", "error": None, "files": []}
    settings = load_settings()
    threading.Thread(
        target=run_download,
        args=(job_id, url, preset, settings.get("yt_cookies", "")),
        daemon=True,
    ).start()
    return jsonify({"job_id": job_id})


@app.route("/api/jobs/<job_id>")
def job_status(job_id):
    j = jobs.get(job_id)
    if not j:
        return jsonify({"error": "not found"}), 404
    return jsonify(j)


@app.route("/api/files")
def files():
    return jsonify({"files": list_files()})


@app.route("/api/files/<name>", methods=["DELETE"])
def delete_file(name):
    p = safe_path(name)
    if not p or not os.path.isfile(p):
        return jsonify({"error": "not found"}), 404
    os.remove(p)
    return jsonify({"ok": True})


@app.route("/d/<name>")
def serve_file(name):
    p = safe_path(name)
    if not p or not os.path.isfile(p):
        return jsonify({"error": "not found"}), 404
    return send_from_directory(DOWNLOAD_DIR, name, as_attachment=True)


if __name__ == "__main__":
    update_ytdlp()  # refresh yt-dlp on boot so YouTube format changes don't break it
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
