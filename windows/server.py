from __future__ import annotations

import os
from pathlib import Path

APP_URL = "http://127.0.0.1:8765"


def configure_environment() -> None:
    base = os.getenv("LOCALAPPDATA")
    data = Path(base) / "PokerCoach" if base else Path.home() / "AppData" / "Local" / "PokerCoach"
    data.mkdir(parents=True, exist_ok=True)

    os.environ.setdefault("POKERCOACH_HOST", "127.0.0.1")
    os.environ.setdefault("POKERCOACH_PORT", "8765")
    os.environ.setdefault("POKERCOACH_DESKTOP_MODE", "1")
    os.environ.setdefault("POKERCOACH_DATA_DIR", str(data))
    os.environ.setdefault("POKERCOACH_URL", APP_URL)


def main() -> None:
    configure_environment()

    import app

    app.init_db()
    server = app.ThreadingHTTPServer((app.HOST, app.PORT), app.Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
