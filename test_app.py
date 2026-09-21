#!/usr/bin/env python3
import http.cookiejar
import json
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

import app


class PokerCoachTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        app.DB_PATH = Path(cls.tmp.name) / "test.db"
        app.init_db()
        salt = bytes.fromhex("00" * 16)
        import hashlib
        digest = hashlib.pbkdf2_hmac("sha256", b"senha-teste", salt, 240_000).hex()
        app.PASSWORD_HASH = salt.hex() + "$" + digest
        app.SESSION_SECRET = "test-secret"
        cls.server = app.ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        jar = http.cookiejar.CookieJar()
        cls.client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.tmp.cleanup()

    @classmethod
    def call(cls, path, data=None):
        body = None if data is None else json.dumps(data).encode()
        req = urllib.request.Request(
            f"http://127.0.0.1:{cls.port}{path}", data=body,
            headers={"Content-Type": "application/json"},
        )
        return json.loads(cls.client.open(req).read())

    def test_end_to_end(self):
        self.assertEqual(self.call("/api/health")["status"], "ok")
        self.assertTrue(self.call("/api/login", {"password": "senha-teste"})["ok"])
        result = self.call("/api/analyze", {
            "completed_hand": True, "mode": "cash", "position": "BTN",
            "card1": "Ah", "card2": "Ks", "stack_bb": 100,
            "pot_bb": 1.5, "call_bb": 0, "last_raise_bb": 0,
            "street": "preflop", "situation": "unopened",
        })
        self.assertEqual(result["action"], "RAISE")
        self.assertEqual(result["hand"], "AKo")
        self.assertTrue(self.call("/api/session", {
            "played_at": "2026-09-21", "mode": "cash", "stakes": "NL10",
            "buy_in": 10, "cash_out": 13.5, "notes": "teste",
        })["ok"])
        summary = self.call("/api/summary")
        self.assertEqual(summary["sessions"], 1)
        self.assertEqual(summary["profit"], 3.5)


if __name__ == "__main__":
    unittest.main()
