import os, sys, json, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest import mock
import app as appmod

BAD_COOKIE = "# Netscape HTTP Cookie File\n.youtube.com TRUE / TRUE 0 YSC dead\n"

def test_layer1_format_fallback_then_best():
    calls = []
    class FakeYDL:
        def __init__(self, opts): calls.append(opts)
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def extract_info(self, url, download):
            if calls[-1]["format"] != "best":
                raise Exception("Requested format is not available. Use --list-formats for a list of available formats")
            return {"id":"x","title":"t","requested_downloads":[{"filepath":"/tmp/fake.mp4"}]}
    with mock.patch.object(appmod.yt_dlp, "YoutubeDL", FakeYDL):
        appmod.run_download("j1", "http://x", {"type":"mp4","quality":"1080"}, "")
    assert appmod.jobs["j1"]["status"] == "done"
    assert [c["format"] for c in calls] == [
        "bv[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080][ext=mp4]/bv[height<=1080]+ba/b[height<=1080]/best[height<=1080]/best",
        "best"]
    print("PASS L1 format->best")

def test_bad_cookie_retries_without_cookie():
    calls = []
    class FakeYDL:
        def __init__(self, opts): calls.append(opts)
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def extract_info(self, url, download):
            if calls[-1].get("cookiefile"):
                raise Exception("Sign in to confirm you're not a bot")  # expired cookie breaks it
            return {"id":"x","title":"t","requested_downloads":[{"filepath":"/tmp/fake.mp4"}]}
    with mock.patch.object(appmod.yt_dlp, "YoutubeDL", FakeYDL):
        appmod.run_download("j2", "http://x", {"type":"best"}, BAD_COOKIE)
    assert appmod.jobs["j2"]["status"] == "done", appmod.jobs["j2"]
    assert calls[0].get("cookiefile") and not calls[-1].get("cookiefile"), \
        "expected final attempt to drop the bad cookie"
    print("PASS L2 drop bad cookie -> succeed no-cookie")

def test_cookie_written_verbatim():
    captured = {}; saved = {}
    class FakeYDL:
        def __init__(self, opts):
            captured.update(opts)
            if "cookiefile" in opts:
                with open(opts["cookiefile"]) as f: saved["content"] = f.read()
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def extract_info(self, url, download): return {"id":"x","title":"t","requested_downloads":[{"filepath":"/tmp/fake.mp4"}]}
    with mock.patch.object(appmod.yt_dlp, "YoutubeDL", FakeYDL):
        appmod.run_download("j3", "http://x", {"type":"best"}, BAD_COOKIE)
    assert "cookiefile" in captured
    assert BAD_COOKIE in saved["content"]
    print("PASS cookie written verbatim")

def test_empty_cookie_skips_file():
    captured = {}
    class FakeYDL:
        def __init__(self, opts): captured.update(opts)
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def extract_info(self, url, download): return {"id":"x","title":"t","requested_downloads":[{"filepath":"/tmp/fake.mp4"}]}
    with mock.patch.object(appmod.yt_dlp, "YoutubeDL", FakeYDL):
        appmod.run_download("j4", "http://x", {"type":"best"}, "")
    assert "cookiefile" not in captured
    print("PASS empty cookie skipped")

if __name__ == "__main__":
    test_layer1_format_fallback_then_best()
    test_bad_cookie_retries_without_cookie()
    test_cookie_written_verbatim()
    test_empty_cookie_skips_file()
    print("ALL TESTS PASSED")
