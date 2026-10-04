"""未配信状態の回帰。標準ライブラリとHTTP stubだけで検証する。"""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check_release as app


def release(tag):
    return {"tag_name": tag, "html_url": "https://example.test/" + tag,
            "published_at": "2026-10-01T00:00:00Z", "body": "変更", "name": tag}


class Response(io.BytesIO):
    def __init__(self, data=b"", status=204):
        super().__init__(data)
        self.status = status

    def getcode(self):
        return self.status


class DeliveryStateTest(unittest.TestCase):
    def setUp(self):
        self.temp = self.enterContext(tempfile.TemporaryDirectory())
        self.state = Path(self.temp) / "state" / "last_tag.txt"
        self.state.parent.mkdir()
        self.state.write_text("v1\n", encoding="utf-8")
        self.enterContext(patch.dict(os.environ, {"STATE_FILE": str(self.state)}, clear=True))
        self.output = self.enterContext(contextlib.redirect_stdout(io.StringIO()))
        self.errors = self.enterContext(contextlib.redirect_stderr(io.StringIO()))
        self.network_attempts = []

        def denied(*args, **kwargs):
            self.network_attempts.append(1)
            raise AssertionError("実通信は禁止")

        for target in ("socket.socket.connect", "socket.socket.connect_ex", "socket.socket.sendto",
                       "socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyaddr"):
            self.enterContext(patch(target, denied))
        self.posts = []
        self.gets = []
        self.failure = None
        self.status = 204
        self.releases = [release("v3"), release("v2"), release("v1")]
        self.http = self.enterContext(patch.object(app.urllib.request, "urlopen", side_effect=self.request))

    def tearDown(self):
        self.assertEqual([], self.network_attempts)

    def request(self, request, timeout):
        if request.get_method() == "GET":
            self.gets.append(request.full_url)
            return Response(json.dumps(self.releases).encode(), 200)
        self.assertEqual("POST", request.get_method())
        self.assertEqual("https://discord.test/stub-secret", request.full_url)
        self.posts.append(json.loads(request.data))
        if self.failure is not None:
            raise self.failure
        return Response(status=self.status)

    def enable_webhook(self):
        os.environ["DISCORD_WEBHOOK_URL"] = "https://discord.test/stub-secret"

    def test_missing_webhook_is_not_delivery(self):
        for value in (None, "", "  \t\n"):
            with self.subTest(value=value):
                self.assertFalse(app.notify_discord([release("v2")], value))
        self.assertEqual([], self.posts)

    def test_missing_then_recovery_then_duplicate(self):
        for value in (None, "", " \t"):
            with self.subTest(value=value):
                os.environ.pop("DISCORD_WEBHOOK_URL", None)
                if value is not None:
                    os.environ["DISCORD_WEBHOOK_URL"] = value
                self.assertEqual(1, app.main())
                self.assertEqual("v1\n", self.state.read_text())
                self.assertEqual([], self.posts)
        self.enable_webhook()
        self.assertEqual(0, app.main())
        self.assertEqual("v3\n", self.state.read_text())
        self.assertEqual(["新しいリリース: v3", "新しいリリース: v2"],
                         [e["title"] for e in self.posts[0]["embeds"]])
        self.assertEqual(0, app.main())
        self.assertEqual(1, len(self.posts))

    def test_http_failure_preserves_state_then_retries(self):
        self.enable_webhook()
        for code in (401, 429, 500, 503):
            with self.subTest(status=code):
                self.failure = urllib.error.HTTPError("https://discord.test/stub-secret", code,
                                                      "stub-secret", {}, None)
                self.assertEqual(1, app.main())
                self.assertEqual("v1\n", self.state.read_text())
        self.failure = None
        self.assertEqual(0, app.main())
        self.assertEqual("v3\n", self.state.read_text())
        self.assertNotIn("stub-secret", self.errors.getvalue())

    def test_timeout_and_transport_preserve_state(self):
        self.enable_webhook()
        for error in (TimeoutError("stub-secret"), urllib.error.URLError("stub-secret")):
            with self.subTest(error=type(error).__name__):
                self.failure = error
                self.assertEqual(1, app.main())
                self.assertEqual("v1\n", self.state.read_text())
        self.assertNotIn("stub-secret", self.errors.getvalue())

    def test_save_failure_keeps_old_state_and_allows_retry(self):
        self.enable_webhook()
        with patch.object(app.os, "replace", side_effect=OSError("保存失敗")):
            self.assertEqual(1, app.main())
        self.assertEqual("v1\n", self.state.read_text())
        self.assertEqual([self.state], list(self.state.parent.iterdir()))
        self.assertEqual(0, app.main())
        self.assertEqual("v3\n", self.state.read_text())
        self.assertEqual(2, len(self.posts))  # 保存失敗後の再送は許容する
        self.assertEqual(0, app.main())
        self.assertEqual(2, len(self.posts))

    def test_bootstrap_missing_or_empty_state_does_not_notify(self):
        for absent in (True, False):
            with self.subTest(absent=absent):
                if absent:
                    self.state.unlink()
                else:
                    self.state.write_text("")
                self.assertEqual(0, app.main())
                self.assertEqual("v3\n", self.state.read_text())
        self.assertEqual([], self.posts)

    def test_no_change_and_no_targets_need_no_webhook(self):
        self.state.write_text("v3\n")
        with patch.object(app, "write_last_tag") as save:
            self.assertEqual(0, app.main())
            save.assert_not_called()
        self.assertTrue(app.notify_discord([], None))
        self.assertEqual([], self.posts)

    def test_read_failure_does_not_send_or_write(self):
        self.enable_webhook()
        with patch.object(Path, "read_text", side_effect=PermissionError("読込失敗")):
            self.assertEqual(1, app.main())
        self.assertEqual("v1\n", self.state.read_text())
        self.assertEqual([], self.posts)

    def test_bootstrap_save_failure_is_nonzero(self):
        self.state.unlink()
        with patch.object(app.os, "replace", side_effect=OSError("保存失敗")):
            self.assertEqual(1, app.main())
        self.assertFalse(self.state.exists())
        self.assertEqual([], self.posts)

    def test_partial_write_does_not_truncate_old_state(self):
        self.enable_webhook()
        create = app.tempfile.NamedTemporaryFile

        def failing_file(*args, **kwargs):
            temporary = create(*args, **kwargs)
            write = temporary.write

            def partial_write(value):
                write(value[:1])
                raise OSError("書き込み途中で失敗")

            temporary.write = partial_write
            return temporary

        with patch.object(app.tempfile, "NamedTemporaryFile", side_effect=failing_file):
            self.assertEqual(1, app.main())
        self.assertEqual(b"v1\n", self.state.read_bytes())
        self.assertEqual([self.state], list(self.state.parent.iterdir()))

    def test_non_2xx_response_does_not_advance_state(self):
        self.enable_webhook()
        self.status = 302
        self.assertEqual(1, app.main())
        self.assertEqual(b"v1\n", self.state.read_bytes())

    def test_new_tag_outside_history_keeps_existing_fallback(self):
        self.enable_webhook()
        self.state.write_text("v0\n")
        self.assertEqual(0, app.main())
        self.assertEqual(1, len(self.posts[0]["embeds"]))
        self.assertEqual("v3\n", self.state.read_text())
