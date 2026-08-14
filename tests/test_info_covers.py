import os, sys, json, tempfile, io
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest import mock
import app as appmod

TMP = tempfile.mkdtemp(prefix="fetchr_test_")
os.makedirs(TMP, exist_ok=True)

def _fake_info(title="My Vid", vid="abc123", thumb="http://t/cover.jpg", duration=100,
               formats=None):
    if formats is None:
        formats = [
            {"vcodec": "avc1", "acodec": "none", "height": 1080, "tbr": 5000},
            {"vcodec": "avc1", "acodec": "none", "height": 720, "tbr": 2500},
            {"vcodec": "avc1", "acodec": "none", "height": 360, "tbr": 800},
            {"vcodec": "none", "acodec": "mp4a", "height": None, "tbr": 128},
        ]
    return {"title": title, "id": vid, "thumbnail": thumb, "duration": duration,
            "formats": formats}

def test_estimate_sizes_per_quality():
    captured = {}
    class FakeYDL:
        def __init__(self, opts): captured.update(opts)
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def extract_info(self, url, download=False):
            return _fake_info()
    with mock.patch.object(appmod.yt_dlp, "YoutubeDL", FakeYDL):
        est = appmod.estimate_sizes("http://x", "")
    assert est and "qualities" in est, est
    labels = [q["label"] for q in est["qualities"]]
    assert "1080p" in labels and "720p" in labels and "360p" in labels, labels
    assert "MP3" in labels, labels
    q1080 = next(q for q in est["qualities"] if q["label"] == "1080p")
    assert q1080["size"] == int(5000/8*1000*100) + int(128/8*1000*100), q1080
    print("PASS estimate sizes:", labels)

def test_estimate_invalid_url():
    assert appmod.estimate_sizes("notaurl", "") is None

def test_run_download_records_meta_and_cover():
    fake_thumb = b"\xff\xd8\xfffakejpg"
    class FakeYDL:
        def __init__(self, opts): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def extract_info(self, url, download=False):
            return {"title": "Cool Clip", "id": "vid9", "thumbnail": "http://t/c.jpg",
                    "requested_downloads": [{"filepath": os.path.join(TMP, "Cool Clip [vid9].mp4")}],
                    "_filename": os.path.join(TMP, "Cool Clip [vid9].mp4")}
    def fake_urlopen(req, timeout=0):
        return io.BytesIO(fake_thumb)
    old_dl = appmod.DOWNLOAD_DIR
    old_meta = appmod.META_FILE
    appmod.DOWNLOAD_DIR = TMP
    appmod.META_FILE = os.path.join(TMP, ".meta.json")
    try:
        with mock.patch.object(appmod.yt_dlp, "YoutubeDL", FakeYDL), \
             mock.patch.object(appmod.urllib.request, "urlopen", fake_urlopen):
            open(os.path.join(TMP, "Cool Clip [vid9].mp4"), "w").write("x")  # simulate yt-dlp output
            appmod.run_download("jx", "http://x", {"type": "mp4", "quality": "1080"}, "")
        meta = appmod.load_meta()
        key = "Cool Clip [vid9].mp4"
        assert key in meta, meta
        assert meta[key]["title"] == "Cool Clip"
        assert meta[key]["cover"] == "cover_vid9.jpg", meta[key]
        assert os.path.exists(os.path.join(TMP, "cover_vid9.jpg"))
        print("PASS meta+cover recorded; cover at", meta[key]["cover"])
    finally:
        appmod.DOWNLOAD_DIR = old_dl
        appmod.META_FILE = old_meta

def test_list_files_excludes_covers_and_meta():
    old_dl = appmod.DOWNLOAD_DIR
    appmod.DOWNLOAD_DIR = TMP
    try:
        open(os.path.join(TMP, "Clip [vid9].mp4"), "w").write("x")
        open(os.path.join(TMP, "cover_vid9.jpg"), "w").write("x")
        open(os.path.join(TMP, ".meta.json"), "w").write("{}")
        names = [i["name"] for i in appmod.list_files()]
        assert "Clip [vid9].mp4" in names, names
        assert "cover_vid9.jpg" not in names, names
        assert ".meta.json" not in names, names
        print("PASS list_files excludes covers/meta")
    finally:
        appmod.DOWNLOAD_DIR = old_dl

if __name__ == "__main__":
    test_estimate_sizes_per_quality()
    test_estimate_invalid_url()
    test_run_download_records_meta_and_cover()
    test_list_files_excludes_covers_and_meta()
    print("ALL TESTS PASSED")
