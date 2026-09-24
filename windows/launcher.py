from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

APP_URL = "http://127.0.0.1:8765"
HEALTH_URL = APP_URL + "/api/health"
CREATE_NO_WINDOW = 0x08000000


def install_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def local_data_dir() -> Path:
    base = os.getenv("LOCALAPPDATA")
    if base:
        return Path(base) / "PokerCoach"
    return Path.home() / "AppData" / "Local" / "PokerCoach"


def app_env() -> dict[str, str]:
    env = os.environ.copy()
    data = local_data_dir()
    data.mkdir(parents=True, exist_ok=True)
    env.update({
        "POKERCOACH_HOST": "127.0.0.1",
        "POKERCOACH_PORT": "8765",
        "POKERCOACH_DESKTOP_MODE": "1",
        "POKERCOACH_DATA_DIR": str(data),
        "POKERCOACH_URL": APP_URL,
    })
    return env


def server_ready(timeout: float = 0.7) -> bool:
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=timeout) as response:
            return response.status == 200
    except Exception:
        return False


def wait_for_server(seconds: float = 20.0) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        if server_ready():
            return True
        time.sleep(0.25)
    return False


def process_running(image_name: str) -> bool:
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {image_name}", "/NH"],
            capture_output=True,
            text=True,
            creationflags=CREATE_NO_WINDOW,
            timeout=3,
            check=False,
        )
        return image_name.lower() in result.stdout.lower()
    except Exception:
        return False


def show_error(message: str) -> None:
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, message, "PokerCoach", 0x10)
    except Exception:
        pass


def main() -> int:
    root = install_dir()
    server_exe = root / "PokerCoachServer.exe"
    vision_exe = root / "PokerVision.exe"
    env = app_env()
    server_process = None

    if not server_ready():
        if not server_exe.exists():
            show_error(f"PokerCoachServer.exe não encontrado em:\n{root}")
            return 2
        try:
            server_process = subprocess.Popen(
                [str(server_exe)],
                cwd=str(root),
                env=env,
                creationflags=CREATE_NO_WINDOW,
            )
        except OSError as exc:
            show_error(f"Não foi possível iniciar o servidor local:\n{exc}")
            return 3

        if not wait_for_server():
            if server_process and server_process.poll() is None:
                server_process.terminate()
            show_error(
                "O servidor local do PokerCoach não respondeu na porta 8765.\n"
                "Reinicie o computador ou feche outro programa que esteja usando essa porta."
            )
            return 4

    webbrowser.open(APP_URL, new=2)

    if process_running("PokerVision.exe"):
        return 0

    if not vision_exe.exists():
        show_error(f"PokerVision.exe não encontrado em:\n{root}")
        if server_process and server_process.poll() is None:
            server_process.terminate()
        return 5

    try:
        vision_process = subprocess.Popen(
            [str(vision_exe)],
            cwd=str(root),
            env=env,
        )
        vision_process.wait()
    except OSError as exc:
        show_error(f"Não foi possível iniciar o PokerVision:\n{exc}")
        return 6
    finally:
        if server_process and server_process.poll() is None:
            server_process.terminate()
            try:
                server_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                server_process.kill()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
