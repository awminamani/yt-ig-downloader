import os, sys, json, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest import mock
import app as appmod

REAL_COOKIE = """# Netscape HTTP Cookie File
# https://curl.haxx.se/rfc/cookie_spec.html
# This is a generated file! Do not edit.

.youtube.com TRUE / TRUE 1802291007 VISITOR_PRIVACY_METADATA CgJOTBIiEh4SHAsMDg8QERITFBUWFxgZGhscHR4fICEiIyQlJicgLg%3D%3D
.youtube.com TRUE / TRUE 1821299008 PREF f6=40000000&tz=Asia.Tehran
.youtube.com TRUE / TRUE 1802291007 VISITOR_INFO1_LIVE ahqH-klt7hI
.youtube.com TRUE / FALSE 0 YSC Zr8BcqxsHv4
"""

def test_format_fallback_on_unavailable():
    """Primary selector raising 'Requested format is not available' must retry with 'best'."""
    calls = []
    class FakeYDL:
        def __init__(self, opts): calls.append(opts); self.opts = opts
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def extract_info(self, url, download):
            if calls[-1]['format'] != 'best':
                raise Exception("Requested format is not available. Use --list-formats for a list of available formats")
            return {"id": "x", "title": "t", "requested_downloads": [{"filepath": "/tmp/fake.mp4"}], "_filename": "/tmp/fake.mp4"}
    with mock.patch.object(appmod.yt_dlp, "YoutubeDL", FakeYDL):
        appmod.run_download("job1", "http://x", {"type": "mp4", "quality": "1080"}, "")
    assert appmod.jobs["job1"]["status"] == "done", appmod.jobs["job1"]
    fmts = [c["format"] for c in calls]
    assert fmts[0] != "best" and fmts[-1] == "best", fmts
    print("PASS fallback:", fmts)

def test_cookie_written_and_passed():
    """Real cookie text must be written to a temp file and passed as cookiefile."""
    captured = {}
    saved = {}
    class FakeYDL:
        def __init__(self, opts):
            captured.update(opts)
            if "cookiefile" in opts:  # file exists now, before deletion in finally
                with open(opts["cookiefile"]) as f:
                    saved["content"] = f.read()
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def extract_info(self, url, download): return {"id":"x","title":"t","requested_downloads":[{"filepath":"/tmp/fake.mp4"}]}
    with mock.patch.object(appmod.yt_dlp, "YoutubeDL", FakeYDL):
        appmod.run_download("job2", "http://x", {"type": "best"}, REAL_COOKIE)
    assert "cookiefile" in captured, "cookiefile opt missing!"
    assert REAL_COOKIE in saved["content"], "cookie content not written verbatim"
    assert appmod.jobs["job2"]["status"] == "done"
    print("PASS cookie passed; file:", captured["cookiefile"])

def test_empty_cookie_not_written():
    captured = {}
    class FakeYDL:
        def __init__(self, opts): captured.update(opts)
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def extract_info(self, url, download): return {"id":"x","title":"t","requested_downloads":[{"filepath":"/tmp/fake.mp4"}]}
    with mock.patch.object(appmod.yt_dlp, "YoutubeDL", FakeYDL):
        appmod.run_download("job3", "http://x", {"type": "best"}, "")
    assert "cookiefile" not in captured, "empty cookie should not create a file"
    print("PASS empty cookie skipped")

if __name__ == "__main__":
    test_format_fallback_on_unavailable()
    test_cookie_written_and_passed()
    test_empty_cookie_not_written()
    print("ALL TESTS PASSED")
