from __future__ import annotations

import ctypes
import ipaddress
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import mss
from PIL import Image, ImageTk

from recognizer import card_text, recognize_board, recognize_hand, street_from_board
from numeric_ocr import OCR_ERROR, read_pot, read_single_number
from table_ocr import SEAT_LAYOUTS, analyze_table, infer_player_count
from tournament_ocr import analyze_tournament_hud


APP_VERSION = "0.12.0"
APP_NAME = "PokerVision"
BRIDGE_HOST = "127.0.0.1"
BRIDGE_PORT = 8766
_BRIDGE_LOCK = threading.Lock()
_BRIDGE_STATE = {
    "version": APP_VERSION,
    "running": False,
    "confirmed": False,
    "hand": [],
    "board": [],
    "street": "AGUARDANDO",
    "blinds": None,
    "ante": None,
    "hero_stack_chips": None,
    "hero_stack_bb": None,
    "table_stacks": [],
    "effective_stack_bb": None,
    "pot_chips": None,
    "pot_bb": None,
    "detected_player_count": None,
    "inactive_seats": None,
    "table_max_seats": 9,
    "table_scan_confidence": "",
    "table_scan_state": "disabled",
    "table_scan_at": 0.0,
    "inactive_points": [],
    "inactive_seat_indices": [],
    "seat_observations": [],
    "tournament_hud_enabled": False,
    "tournament_hud_state": "disabled",
    "tournament_hud_at": 0.0,
    "tournament_rank": None,
    "tournament_remaining": None,
    "tournament_avg_stack_bb": None,
    "tournament_small_blind": None,
    "tournament_big_blind": None,
    "tournament_ante": None,
    "tournament_level_seconds": None,
    "updated_at": 0.0,
}

_DEFAULT_POKERCOACH_TARGETS = (
    "http://192.168.15.140:8765",
    "http://Beelink:8765",
    "http://beelink.local:8765",
)
_target_from_env = os.getenv("POKERCOACH_URL", "").strip().rstrip("/")
POKERCOACH_TARGETS = (
    (_target_from_env,) if _target_from_env else _DEFAULT_POKERCOACH_TARGETS
)
_DELIVERY_LOCK = threading.Lock()
_DELIVERY_STATUS = {
    "ok": False,
    "target": "",
    "message": "aguardando envio ao Beelink",
    "updated_at": 0.0,
}


def _bridge_publish(
    *,
    running: bool | None = None,
    confirmed: bool | None = None,
    hand: tuple[str, ...] | list[str] | None = None,
    board: tuple[str, ...] | list[str] | None = None,
    street: str | None = None,
) -> None:
    with _BRIDGE_LOCK:
        if running is not None:
            _BRIDGE_STATE["running"] = bool(running)
        if confirmed is not None:
            _BRIDGE_STATE["confirmed"] = bool(confirmed)
        if hand is not None:
            _BRIDGE_STATE["hand"] = list(hand)
        if board is not None:
            _BRIDGE_STATE["board"] = list(board)
        if street is not None:
            _BRIDGE_STATE["street"] = str(street)
        _BRIDGE_STATE["updated_at"] = time.time()


def _bridge_snapshot() -> dict:
    with _BRIDGE_LOCK:
        return dict(_BRIDGE_STATE)


def _bridge_publish_numeric(data: dict) -> None:
    allowed = {
        "blinds",
        "ante",
        "hero_stack_chips",
        "hero_stack_bb",
        "table_stacks",
        "table_stacks_bb",
        "effective_stack_bb",
        "pot_chips",
        "pot_bb",
    }
    with _BRIDGE_LOCK:
        for key, value in data.items():
            if key in allowed:
                _BRIDGE_STATE[key] = value
        _BRIDGE_STATE["updated_at"] = time.time()


def _bridge_publish_table(data: dict) -> None:
    allowed = {
        "detected_player_count",
        "inactive_seats",
        "table_max_seats",
        "table_scan_confidence",
        "table_scan_state",
        "table_scan_at",
        "inactive_points",
        "inactive_seat_indices",
        "seat_observations",
    }
    with _BRIDGE_LOCK:
        for key, value in data.items():
            if key in allowed:
                _BRIDGE_STATE[key] = value
        _BRIDGE_STATE["updated_at"] = time.time()


def _bridge_publish_tournament(data: dict) -> None:
    allowed = {
        "tournament_hud_enabled",
        "tournament_hud_state",
        "tournament_hud_at",
        "tournament_rank",
        "tournament_remaining",
        "tournament_avg_stack_bb",
        "tournament_small_blind",
        "tournament_big_blind",
        "tournament_ante",
        "tournament_level_seconds",
    }
    with _BRIDGE_LOCK:
        for key, value in data.items():
            if key in allowed:
                _BRIDGE_STATE[key] = value
        _BRIDGE_STATE["updated_at"] = time.time()


def _origin_allowed(origin: str) -> bool:
    if not origin:
        return True
    try:
        parsed = urlparse(origin)
        host = (parsed.hostname or "").lower()
        if parsed.scheme not in {"http", "https"}:
            return False
        if host in {"localhost", "127.0.0.1", "beelink"} or host.endswith(".local"):
            return True
        address = ipaddress.ip_address(host)
        return bool(address.is_private or address.is_loopback)
    except (ValueError, TypeError):
        return False


class BridgeHandler(BaseHTTPRequestHandler):
    def _cors(self) -> bool:
        origin = self.headers.get("Origin", "")
        allowed = _origin_allowed(origin)
        if allowed and origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Cache-Control", "no-store")
        return allowed

    def do_OPTIONS(self) -> None:
        origin = self.headers.get("Origin", "")
        if not _origin_allowed(origin):
            self.send_response(403)
            self.end_headers()
            return
        self.send_response(204)
        self._cors()
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        origin = self.headers.get("Origin", "")
        if not _origin_allowed(origin):
            self.send_response(403)
            self.end_headers()
            return
        if self.path.split("?", 1)[0] != "/state":
            self.send_response(404)
            self.end_headers()
            return
        raw = json.dumps(_bridge_snapshot(), ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self._cors()
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, _format: str, *_args) -> None:
        return


def start_bridge_server() -> None:
    def run() -> None:
        try:
            server = ThreadingHTTPServer((BRIDGE_HOST, BRIDGE_PORT), BridgeHandler)
            server.serve_forever()
        except OSError as exc:
            print(f"PokerVision bridge indisponível em {BRIDGE_HOST}:{BRIDGE_PORT}: {exc}")

    threading.Thread(target=run, name="PokerVisionBridge", daemon=True).start()


def _set_delivery_status(ok: bool, target: str, message: str) -> None:
    with _DELIVERY_LOCK:
        _DELIVERY_STATUS["ok"] = bool(ok)
        _DELIVERY_STATUS["target"] = target
        _DELIVERY_STATUS["message"] = message
        _DELIVERY_STATUS["updated_at"] = time.time()


def delivery_status() -> dict:
    with _DELIVERY_LOCK:
        return dict(_DELIVERY_STATUS)


def start_beelink_publisher() -> None:
    """Push the latest confirmed PokerVision state to PokerCoach on the LAN."""
    def run() -> None:
        preferred: str | None = None
        while True:
            state = _bridge_snapshot()
            payload = json.dumps(state, ensure_ascii=False).encode("utf-8")
            targets = list(POKERCOACH_TARGETS)
            if preferred in targets:
                targets.remove(preferred)
                targets.insert(0, preferred)

            delivered = False
            last_error = ""
            for base in targets:
                url = base.rstrip("/") + "/api/vision/ingest"
                request = Request(
                    url,
                    data=payload,
                    method="POST",
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": f"PokerVision/{APP_VERSION}",
                    },
                )
                try:
                    with urlopen(request, timeout=0.7) as response:
                        if 200 <= response.status < 300:
                            preferred = base
                            delivered = True
                            try:
                                reply = json.loads(
                                    response.read().decode("utf-8") or "{}"
                                )
                                server_config = reply.get("config", {})
                                max_seats = int(
                                    server_config.get("table_max_seats", 9)
                                )
                                if 2 <= max_seats <= 10:
                                    current = int(
                                        _bridge_snapshot().get(
                                            "table_max_seats", 9
                                        ) or 9
                                    )
                                    if max_seats != current:
                                        _bridge_publish_table({
                                            "table_max_seats": max_seats,
                                            "detected_player_count": None,
                                            "inactive_seats": None,
                                            "table_scan_state": "waiting",
                                            "table_scan_at": 0.0,
                                            "inactive_points": [],
                                            "inactive_seat_indices": [],
                                            "seat_observations": [],
                                        })
                                        LOGGER.info(
                                            "TABLE_CONFIG max_seats=%s source=PokerCoach",
                                            max_seats,
                                        )
                            except (ValueError, TypeError, json.JSONDecodeError):
                                pass
                            _set_delivery_status(True, base, "sincronizado com PokerCoach")
                            break
                        last_error = f"HTTP {response.status}"
                except (OSError, URLError) as exc:
                    last_error = str(exc)

            if not delivered:
                _set_delivery_status(
                    False,
                    preferred or POKERCOACH_TARGETS[0],
                    last_error or "PokerCoach não encontrado",
                )
            time.sleep(0.5)

    threading.Thread(
        target=run,
        name="PokerVisionBeelinkPublisher",
        daemon=True,
    ).start()


class StableReading:
    """Require the same valid reading for a few frames before confirming it."""

    def __init__(self, confirmations: int = 3) -> None:
        self.confirmations = confirmations
        self.candidate: tuple[str, ...] | None = None
        self.count = 0
        self.stable: tuple[str, ...] = ()
        self.ready = False

    def reset(self) -> None:
        self.candidate = None
        self.count = 0
        self.stable = ()
        self.ready = False

    def observe(self, value: tuple[str, ...] | None) -> None:
        if value is None:
            self.candidate = None
            self.count = 0
            return

        if value == self.candidate:
            self.count += 1
        else:
            self.candidate = value
            self.count = 1

        if self.count >= self.confirmations:
            self.stable = value
            self.ready = True


def enable_dpi_awareness() -> None:
    """Keep Tk coordinates aligned with physical screen pixels on Windows."""
    if os.name != "nt":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


LOGGER = logging.getLogger("PokerVision")


def app_data_dir() -> Path:
    base = Path(os.environ.get("APPDATA", Path.home()))
    path = base / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_path() -> Path:
    return app_data_dir() / "pokervision.log"


def setup_logging() -> None:
    if LOGGER.handlers:
        return
    LOGGER.setLevel(logging.INFO)
    handler = RotatingFileHandler(
        log_path(),
        maxBytes=1_000_000,
        backupCount=2,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    )
    LOGGER.addHandler(handler)
    LOGGER.propagate = False
    LOGGER.info("START version=%s", APP_VERSION)


def config_path() -> Path:
    return app_data_dir() / "config.json"


def capture_dir() -> Path:
    path = Path.home() / "PokerVisionCaptures"
    path.mkdir(parents=True, exist_ok=True)
    return path


CALIBRATION_KEYS = (
    "hand",
    "board",
    "hero_stack",
    "pot",
    "table",
    "tournament_hud",
)


def load_config() -> dict:
    path = config_path()
    empty = {key: None for key in CALIBRATION_KEYS}
    empty["table_max_seats"] = 9
    empty["tournament_hud_enabled"] = False
    if not path.exists():
        return empty
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        result = {key: data.get(key) for key in CALIBRATION_KEYS}
        try:
            max_seats = int(data.get("table_max_seats", 9))
        except (TypeError, ValueError):
            max_seats = 9
        result["table_max_seats"] = max(2, min(10, max_seats))
        result["tournament_hud_enabled"] = bool(
            data.get("tournament_hud_enabled", False)
        )
        return result
    except Exception:
        return empty


def save_config(config: dict) -> None:
    config_path().write_text(
        json.dumps(config, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def grab_box(box: dict) -> Image.Image:
    monitor = {
        "left": int(box["x"]),
        "top": int(box["y"]),
        "width": int(box["width"]),
        "height": int(box["height"]),
    }
    with mss.mss() as sct:
        shot = sct.grab(monitor)
    return Image.frombytes("RGB", shot.size, shot.rgb)


def format_codes(codes: tuple[str, ...]) -> str:
    if not codes:
        return "SEM CARTAS"
    return "  ".join(card_text(code) for code in codes)


class RegionSelector:
    def __init__(
        self,
        root: tk.Tk,
        image: Image.Image,
        virtual_box: dict,
        label: str,
    ) -> None:
        self.result: dict | None = None
        self.start_x = 0
        self.start_y = 0
        self.rect_id: int | None = None
        self.virtual_box = virtual_box

        self.window = tk.Toplevel(root)
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.configure(bg="black")

        left = int(virtual_box["left"])
        top = int(virtual_box["top"])
        width = int(virtual_box["width"])
        height = int(virtual_box["height"])
        self.window.geometry(f"{width}x{height}{left:+d}{top:+d}")

        self.canvas = tk.Canvas(
            self.window,
            width=width,
            height=height,
            highlightthickness=0,
            cursor="crosshair",
        )
        self.canvas.pack(fill="both", expand=True)

        self.photo = ImageTk.PhotoImage(image)
        self.canvas.create_image(0, 0, anchor="nw", image=self.photo)

        self.canvas.create_rectangle(
            16,
            16,
            660,
            72,
            fill="#07130f",
            outline="#38d996",
            width=2,
        )
        self.canvas.create_text(
            30,
            31,
            anchor="nw",
            text=f"Selecione: {label}",
            fill="white",
            font=("Segoe UI", 18, "bold"),
        )
        self.canvas.create_text(
            30,
            56,
            anchor="nw",
            text="Arraste o retângulo. ESC cancela.",
            fill="#b7c8c0",
            font=("Segoe UI", 11),
        )

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.window.bind("<Escape>", self.cancel)
        self.window.focus_force()
        self.window.grab_set()

    def on_press(self, event: tk.Event) -> None:
        self.start_x = int(event.x)
        self.start_y = int(event.y)
        if self.rect_id is not None:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(
            self.start_x,
            self.start_y,
            self.start_x,
            self.start_y,
            outline="#38d996",
            width=3,
        )

    def on_drag(self, event: tk.Event) -> None:
        if self.rect_id is None:
            return
        self.canvas.coords(
            self.rect_id,
            self.start_x,
            self.start_y,
            int(event.x),
            int(event.y),
        )

    def on_release(self, event: tk.Event) -> None:
        x1 = min(self.start_x, int(event.x))
        y1 = min(self.start_y, int(event.y))
        x2 = max(self.start_x, int(event.x))
        y2 = max(self.start_y, int(event.y))
        width = x2 - x1
        height = y2 - y1
        if width < 20 or height < 20:
            return

        self.result = {
            "x": int(self.virtual_box["left"]) + x1,
            "y": int(self.virtual_box["top"]) + y1,
            "width": width,
            "height": height,
        }
        self.window.grab_release()
        self.window.destroy()

    def cancel(self, _event: tk.Event | None = None) -> None:
        self.result = None
        try:
            self.window.grab_release()
        except Exception:
            pass
        self.window.destroy()


class PokerVisionApp:
    REFRESH_MS = 250

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.config = load_config()
        self.running = False
        self.hand_photo: ImageTk.PhotoImage | None = None
        self.board_photo: ImageTk.PhotoImage | None = None
        self.hand_tracker = StableReading(confirmations=3)
        self.board_tracker = StableReading(confirmations=3)
        self.numeric_tracker = StableReading(confirmations=2)
        self.numeric_lock = threading.Lock()
        self.numeric_result: dict | None = None
        self.numeric_pending = False
        self.last_numeric_scan = 0.0
        self.table_tracker = StableReading(confirmations=3)
        self.table_lock = threading.Lock()
        self.table_result: dict | None = None
        self.table_pending = False
        self.last_table_scan = 0.0
        self.last_applied_table_scan_at = 0.0
        self.last_logged_card_state = None
        self.last_logged_numeric_state = None
        self.last_logged_table_state = None
        self.tournament_lock = threading.Lock()
        self.tournament_result: dict | None = None
        self.tournament_pending = False
        self.last_tournament_scan = 0.0
        self.last_applied_tournament_scan_at = 0.0
        self.last_logged_tournament_state = None
        self.player_memory: dict[str, dict] = {}
        self.inactive_seat_memory: dict[int, float] = {}
        self.active_seat_streak: dict[int, int] = {}
        self.player_round_key = None
        self.player_hand_key = None
        self.player_round_max_bet = 0.0
        _bridge_publish(
            running=False,
            confirmed=False,
            hand=[],
            board=[],
            street="AGUARDANDO",
        )

        root.title(f"{APP_NAME} {APP_VERSION}")
        root.geometry("1040x790")
        root.minsize(860, 680)
        root.configure(bg="#07130f")
        root.protocol("WM_DELETE_WINDOW", self.close)

        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass
        self.style.configure("TFrame", background="#07130f")
        self.style.configure("Card.TFrame", background="#0e211a")
        self.style.configure(
            "TLabel",
            background="#07130f",
            foreground="#edf8f3",
            font=("Segoe UI", 10),
        )
        self.style.configure(
            "Muted.TLabel",
            background="#07130f",
            foreground="#9bb5aa",
            font=("Segoe UI", 9),
        )
        self.style.configure(
            "Title.TLabel",
            background="#07130f",
            foreground="#edf8f3",
            font=("Segoe UI", 20, "bold"),
        )
        self.style.configure(
            "Detect.TLabel",
            background="#07130f",
            foreground="#38d996",
            font=("Segoe UI", 13, "bold"),
        )
        self.style.configure(
            "Status.TLabel",
            background="#0e211a",
            foreground="#38d996",
            font=("Segoe UI", 11, "bold"),
        )
        self.style.configure(
            "TButton",
            padding=(12, 8),
            font=("Segoe UI", 10),
        )

        self.build_ui()
        self.refresh_region_labels()
        self.root.after(100, self.preview_once)

    def build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=18)
        outer.pack(fill="both", expand=True)

        top = ttk.Frame(outer)
        top.pack(fill="x")
        ttk.Label(top, text="PokerVision", style="Title.TLabel").pack(side="left")
        ttk.Label(
            top,
            text=f"v{APP_VERSION} · reconhecimento visual",
            style="Muted.TLabel",
        ).pack(side="right", pady=(8, 0))

        ttk.Label(
            outer,
            text=(
                "Captura por coordenadas. Ausência de cartas é um estado normal; "
                "leituras incertas não são confirmadas."
            ),
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(4, 14))

        actions = ttk.Frame(outer)
        actions.pack(fill="x", pady=(0, 8))

        ttk.Button(
            actions,
            text="1. MÃO",
            command=lambda: self.select_region("hand"),
        ).pack(side="left", padx=(0, 8))
        ttk.Button(
            actions,
            text="2. BOARD",
            command=lambda: self.select_region("board"),
        ).pack(side="left", padx=(0, 8))
        ttk.Button(
            actions,
            text="3. MESA / JOGADORES",
            command=lambda: self.select_region("table"),
        ).pack(side="left", padx=(0, 8))
        ttk.Button(
            actions,
            text="Iniciar monitoramento",
            command=self.start,
        ).pack(side="left", padx=(12, 8))
        ttk.Button(
            actions,
            text="Parar",
            command=self.stop,
        ).pack(side="left")

        finance_actions = ttk.Frame(outer)
        finance_actions.pack(fill="x", pady=(0, 14))
        ttk.Label(
            finance_actions,
            text="Automação numérica:",
            style="Muted.TLabel",
        ).pack(side="left", padx=(0, 8))
        for key, label in (
            ("hero_stack", "MEU STACK"),
            ("pot", "POTE"),
        ):
            ttk.Button(
                finance_actions,
                text=label,
                command=lambda k=key: self.select_region(k),
            ).pack(side="left", padx=(0, 6))

        self.tournament_hud_var = tk.BooleanVar(
            value=bool(self.config.get("tournament_hud_enabled", False))
        )
        ttk.Checkbutton(
            finance_actions,
            text="HUD torneio",
            variable=self.tournament_hud_var,
            command=self.on_tournament_hud_toggle,
        ).pack(side="left", padx=(10, 6))
        ttk.Button(
            finance_actions,
            text="TORNEIO / HUD",
            command=lambda: self.select_region("tournament_hud"),
        ).pack(side="left", padx=(0, 10))

        ttk.Label(
            finance_actions,
            text="Lugares da mesa: controlado pelo site PokerCoach",
            style="Muted.TLabel",
        ).pack(side="left", padx=(10, 4))

        coords = ttk.Frame(outer, style="Card.TFrame", padding=12)
        coords.pack(fill="x", pady=(0, 14))
        self.hand_coords = ttk.Label(coords, text="")
        self.hand_coords.pack(anchor="w")
        self.board_coords = ttk.Label(coords, text="")
        self.board_coords.pack(anchor="w", pady=(4, 0))
        self.hero_stack_coords = ttk.Label(coords, text="")
        self.hero_stack_coords.pack(anchor="w", pady=(4, 0))
        self.pot_coords = ttk.Label(coords, text="")
        self.pot_coords.pack(anchor="w", pady=(4, 0))
        self.table_coords = ttk.Label(coords, text="")
        self.table_coords.pack(anchor="w", pady=(4, 0))
        self.tournament_hud_coords = ttk.Label(coords, text="")
        self.tournament_hud_coords.pack(anchor="w", pady=(4, 0))
        self.tournament_hud_readout = ttk.Label(
            coords,
            text="HUD TORNEIO: desativado",
            style="Muted.TLabel",
        )
        self.tournament_hud_readout.pack(anchor="w", pady=(4, 0))
        self.table_readout = ttk.Label(
            coords,
            text="JOGADORES: automação não configurada",
            style="Muted.TLabel",
        )
        self.table_readout.pack(anchor="w", pady=(5, 0))
        self.players_readout = ttk.Label(
            coords,
            text="STACKS DA MESA: aguardando leitura",
            style="Muted.TLabel",
            wraplength=960,
            justify="left",
        )
        self.players_readout.pack(anchor="w", pady=(4, 0))
        self.numeric_readout = ttk.Label(
            coords,
            text="OCR NUMÉRICO: aguardando monitoramento",
            style="Muted.TLabel",
        )
        self.numeric_readout.pack(anchor="w", pady=(7, 0))
        self.numeric_raw_readout = ttk.Label(
            coords,
            text="OCR BRUTO: —",
            style="Muted.TLabel",
        )
        self.numeric_raw_readout.pack(anchor="w", pady=(3, 0))
        self.street_readout = ttk.Label(
            coords,
            text="STREET: —",
            style="Detect.TLabel",
        )
        self.street_readout.pack(anchor="w", pady=(8, 0))
        self.bridge_readout = ttk.Label(
            coords,
            text="SITE: conectando ao PokerCoach no Beelink…",
            style="Muted.TLabel",
        )
        self.bridge_readout.pack(anchor="w", pady=(5, 0))

        previews = ttk.Frame(outer)
        previews.pack(fill="both", expand=True)
        previews.columnconfigure(0, weight=1)
        previews.columnconfigure(1, weight=1)
        previews.rowconfigure(1, weight=1)

        ttk.Label(previews, text="MÃO", style="TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 7)
        )
        ttk.Label(previews, text="BOARD", style="TLabel").grid(
            row=0, column=1, sticky="w", padx=(7, 0)
        )

        self.hand_preview = tk.Label(
            previews,
            bg="#0b1713",
            fg="#9bb5aa",
            text="Região não configurada",
            bd=1,
            relief="solid",
        )
        self.hand_preview.grid(
            row=1, column=0, sticky="nsew", padx=(0, 7), pady=(6, 0)
        )
        self.board_preview = tk.Label(
            previews,
            bg="#0b1713",
            fg="#9bb5aa",
            text="Região não configurada",
            bd=1,
            relief="solid",
        )
        self.board_preview.grid(
            row=1, column=1, sticky="nsew", padx=(7, 0), pady=(6, 0)
        )

        self.hand_detect = ttk.Label(
            previews,
            text="Detectado: —",
            style="Detect.TLabel",
        )
        self.hand_detect.grid(
            row=2, column=0, sticky="w", padx=(0, 7), pady=(8, 0)
        )
        self.board_detect = ttk.Label(
            previews,
            text="Detectado: —",
            style="Detect.TLabel",
        )
        self.board_detect.grid(
            row=2, column=1, sticky="w", padx=(7, 0), pady=(8, 0)
        )

        bottom = ttk.Frame(outer)
        bottom.pack(fill="x", pady=(14, 0))
        self.status = ttk.Label(
            bottom,
            text="Configure as duas regiões.",
            style="Status.TLabel",
            padding=(12, 10),
        )
        self.status.pack(side="left", fill="x", expand=True)

        ttk.Button(
            bottom,
            text="Copiar diagnóstico",
            command=self.copy_diagnostics,
        ).pack(side="right", padx=(10, 0))

        ttk.Button(
            bottom,
            text="Salvar amostra",
            command=self.save_sample,
        ).pack(side="right", padx=(10, 0))

    def on_tournament_hud_toggle(self) -> None:
        enabled = bool(self.tournament_hud_var.get())
        self.config["tournament_hud_enabled"] = enabled
        save_config(self.config)
        if not enabled:
            with self.tournament_lock:
                self.tournament_result = None
                self.tournament_pending = False
            _bridge_publish_tournament({
                "tournament_hud_enabled": False,
                "tournament_hud_state": "disabled",
                "tournament_hud_at": 0.0,
                "tournament_rank": None,
                "tournament_remaining": None,
                "tournament_avg_stack_bb": None,
                "tournament_small_blind": None,
                "tournament_big_blind": None,
                "tournament_ante": None,
                "tournament_level_seconds": None,
            })
            self.tournament_hud_readout.configure(
                text="HUD TORNEIO: desativado · motor continua sem esses dados"
            )
        else:
            _bridge_publish_tournament({
                "tournament_hud_enabled": True,
                "tournament_hud_state": (
                    "waiting" if self.config.get("tournament_hud") else "not_configured"
                ),
            })
            if not self.config.get("tournament_hud"):
                self.tournament_hud_readout.configure(
                    text="HUD TORNEIO: ativado · selecione a região TORNEIO / HUD"
                )
        self.refresh_region_labels()

    def on_table_max_changed(self, _event=None) -> None:
        return

    def select_region(self, key: str) -> None:
        labels = {
            "hand": "SUAS DUAS CARTAS",
            "board": "FLOP / TURN / RIVER",
            "hero_stack": "SEU STACK EM BB",
            "pot": "POTE EM BB",
            "table": "MESA COM ASSENTOS (sem chat e botões)",
            "tournament_hud": "FAIXA DO TORNEIO (posição, média, blinds e relógio)",
        }
        label = labels.get(key, key.upper())
        self.stop()
        self.root.withdraw()
        self.root.update_idletasks()
        time.sleep(0.20)

        try:
            with mss.mss() as sct:
                virtual = dict(sct.monitors[0])
                shot = sct.grab(virtual)
            image = Image.frombytes("RGB", shot.size, shot.rgb)

            selector = RegionSelector(self.root, image, virtual, label)
            self.root.wait_window(selector.window)
            if selector.result is not None:
                self.config[key] = selector.result
                save_config(self.config)
                LOGGER.info(
                    "CALIBRATION key=%s x=%s y=%s w=%s h=%s",
                    key,
                    selector.result.get("x"),
                    selector.result.get("y"),
                    selector.result.get("width"),
                    selector.result.get("height"),
                )
        except Exception as exc:
            messagebox.showerror("PokerVision", f"Falha ao selecionar região:\n{exc}")
        finally:
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
            self.hand_tracker.reset()
            self.board_tracker.reset()
            self.refresh_region_labels()
            self.preview_once()

    def refresh_region_labels(self) -> None:
        self.hand_coords.configure(text=self.format_region("MÃO", self.config["hand"]))
        self.board_coords.configure(
            text=self.format_region("BOARD", self.config["board"])
        )
        self.hero_stack_coords.configure(
            text=self.format_region("MEU STACK", self.config["hero_stack"])
        )
        self.pot_coords.configure(
            text=self.format_region("POTE", self.config["pot"])
        )
        self.table_coords.configure(
            text=self.format_region("MESA/JOGADORES", self.config.get("table"))
        )
        self.tournament_hud_coords.configure(
            text=self.format_region(
                "TORNEIO/HUD",
                self.config.get("tournament_hud"),
            )
        )
        if self.config["hand"] and self.config["board"]:
            extras = sum(bool(self.config[key]) for key in ("hero_stack", "pot"))
            table_status = "mesa configurada" if self.config.get("table") else "mesa opcional não configurada"
            self.status.configure(
                text=f"Cartas prontas · automação stack/pote: {extras}/2 · {table_status}."
            )
        else:
            self.status.configure(text="Configure as duas regiões.")

    @staticmethod
    def format_region(name: str, region: dict | None) -> str:
        if not region:
            return f"{name}: não configurada"
        return (
            f"{name}: x={region['x']}  y={region['y']}  "
            f"largura={region['width']}  altura={region['height']}"
        )

    @staticmethod
    def fit_preview(
        image: Image.Image,
        max_w: int = 430,
        max_h: int = 330,
    ) -> Image.Image:
        copy = image.copy()
        copy.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
        return copy

    def preview_region(
        self,
        region: dict | None,
        widget: tk.Label,
        kind: str,
    ) -> Image.Image | None:
        if not region:
            widget.configure(image="", text="Região não configurada")
            if kind == "hand":
                self.hand_photo = None
            else:
                self.board_photo = None
            return None

        image = grab_box(region)
        preview = self.fit_preview(image)
        photo = ImageTk.PhotoImage(preview)
        widget.configure(image=photo, text="")
        if kind == "hand":
            self.hand_photo = photo
        else:
            self.board_photo = photo
        return image

    @staticmethod
    def valid_value(reading, valid_counts: set[int]) -> tuple[str, ...] | None:
        occupied = sum(reading.occupied_slots)
        if reading.uncertain or occupied not in valid_counts:
            return None
        if len(reading.codes) != occupied:
            return None
        return reading.codes

    def update_recognition(
        self,
        hand_image: Image.Image,
        board_image: Image.Image,
    ) -> None:
        hand = recognize_hand(hand_image)
        board = recognize_board(board_image)

        hand_value = self.valid_value(hand, {0, 2})
        board_value = self.valid_value(board, {0, 3, 4, 5})

        if hand_value is None:
            self.hand_detect.configure(text="Detectado: LEITURA INCERTA")
        else:
            self.hand_detect.configure(text=f"Detectado: {format_codes(hand_value)}")
            self.hand_tracker.observe(hand_value)

        if board_value is None:
            count = sum(board.occupied_slots)
            label = "TRANSIÇÃO" if count in {1, 2} else "LEITURA INCERTA"
            self.board_detect.configure(text=f"Detectado: {label}")
        else:
            self.board_detect.configure(text=f"Detectado: {format_codes(board_value)}")
            self.board_tracker.observe(board_value)

        raw_street = street_from_board(board)
        self.street_readout.configure(text=f"STREET: {raw_street}")

        if not self.running:
            return

        if hand_value is None or board_value is None:
            _bridge_publish(running=self.running, confirmed=False)
            self.status.configure(
                text="LENDO · aguardando uma leitura estável por 3 capturas."
            )
            return

        current_confirmed = (
            self.hand_tracker.ready
            and self.board_tracker.ready
            and self.hand_tracker.stable == hand_value
            and self.board_tracker.stable == board_value
        )
        if not current_confirmed:
            _bridge_publish(running=self.running, confirmed=False)
            self.status.configure(
                text="CONFIRMANDO · a mesma leitura precisa aparecer em 3 capturas."
            )
            return

        stable_hand = self.hand_tracker.stable
        stable_board = self.board_tracker.stable
        stable_street = {
            0: "PRÉ-FLOP",
            3: "FLOP",
            4: "TURN",
            5: "RIVER",
        }.get(len(stable_board), "INCERTO")

        _bridge_publish(
            running=self.running,
            confirmed=True,
            hand=stable_hand,
            board=stable_board,
            street=stable_street,
        )

        card_signature = (
            tuple(stable_hand),
            tuple(stable_board),
            stable_street,
        )
        if card_signature != self.last_logged_card_state:
            LOGGER.info(
                "CARDS confirmed hand=%s board=%s street=%s",
                list(stable_hand),
                list(stable_board),
                stable_street,
            )
            self.last_logged_card_state = card_signature

        if not stable_hand:
            self.status.configure(
                text=f"AGUARDANDO MÃO · BOARD: {format_codes(stable_board)} · site sincronizado"
            )
            return

        self.status.configure(
            text=(
                f"CONFIRMADO · MÃO: {format_codes(stable_hand)} · "
                f"BOARD: {format_codes(stable_board)} · {stable_street} · SITE OK"
            )
        )

    @staticmethod
    def _round_value(value):
        return None if value is None else round(float(value), 4)

    def _player_key(self, obs: dict) -> str:
        seat_index = obs.get("seat_index")
        if seat_index is not None:
            try:
                return f"seat:{int(seat_index)}"
            except (TypeError, ValueError):
                pass
        x = float(obs.get("x", 0))
        y = float(obs.get("y", 0))
        best_key = None
        best_distance = 1e9
        for key, memory in self.player_memory.items():
            if "x" not in memory or "y" not in memory:
                continue
            dx = x - float(memory["x"])
            dy = y - float(memory["y"])
            distance = (dx * dx) + (dy * dy)
            if distance < best_distance:
                best_distance = distance
                best_key = key
        if best_key is not None and best_distance <= (0.085 * 0.085):
            return best_key
        return f"seat:{x:.3f}:{y:.3f}"

    def _current_round_key(self) -> tuple:
        state = _bridge_snapshot()
        return (
            tuple(state.get("hand", [])),
            str(state.get("street", "AGUARDANDO")),
            tuple(state.get("board", [])),
        )

    def _reset_player_round_if_needed(self) -> None:
        state = _bridge_snapshot()
        hand_key = tuple(state.get("hand", []))
        if len(hand_key) == 2 and hand_key != self.player_hand_key:
            self.player_hand_key = hand_key
            for memory in self.player_memory.values():
                memory["folded"] = False

        key = self._current_round_key()
        if key == self.player_round_key:
            return
        self.player_round_key = key
        self.player_round_max_bet = 0.0
        for memory in self.player_memory.values():
            memory["round_bet_bb"] = None
            memory["action"] = "UNKNOWN"
            memory["action_at"] = 0.0
            memory["action_history"] = []

    def _merge_player_observations(
        self,
        observations: list[dict],
        now: float,
    ) -> list[dict]:
        self._reset_player_round_if_needed()
        round_max_before = self.player_round_max_bet
        current_keys: set[str] = set()
        enriched: list[dict] = []

        for raw in observations:
            obs = dict(raw)
            key = self._player_key(obs)
            current_keys.add(key)
            memory = self.player_memory.setdefault(key, {})

            name = str(obs.get("name", "")).strip()
            if name:
                memory["name"] = name
            memory["x"] = float(obs.get("x", memory.get("x", 0)))
            memory["y"] = float(obs.get("y", memory.get("y", 0)))
            if obs.get("seat_index") is not None:
                memory["seat_index"] = int(obs["seat_index"])
            memory["status"] = str(obs.get("status", "active"))

            stack = obs.get("stack_bb")
            if stack is not None:
                memory["stack_bb"] = float(stack)

            bet = obs.get("bet_bb")
            previous_bet = memory.get("round_bet_bb")
            if bet is not None:
                bet = float(bet)
                memory["round_bet_bb"] = bet

            direct_action = str(obs.get("action", "unknown")).upper()
            if direct_action == "UNKNOWN":
                direct_action = ""

            inferred_action = ""
            if direct_action:
                inferred_action = direct_action
            elif bet is not None and previous_bet is not None and bet > previous_bet + 0.05:
                street = str(_bridge_snapshot().get("street", "AGUARDANDO"))
                if round_max_before <= 0.05:
                    if street != "PRÉ-FLOP":
                        inferred_action = "BET"
                    elif bet > 1.05:
                        inferred_action = "RAISE"
                elif abs(bet - round_max_before) <= 0.15:
                    inferred_action = "CALL"
                elif bet > round_max_before + 0.15:
                    inferred_action = "RAISE"

            if inferred_action:
                memory["action"] = inferred_action
                memory["action_at"] = now
                history = memory.setdefault("action_history", [])
                event = {
                    "action": inferred_action,
                    "bet_bb": memory.get("round_bet_bb"),
                    "at": now,
                }
                last_event = history[-1] if history else None
                same_event = bool(
                    last_event
                    and last_event.get("action") == event["action"]
                    and (
                        last_event.get("bet_bb") == event["bet_bb"]
                        or (
                            last_event.get("bet_bb") is not None
                            and event["bet_bb"] is not None
                            and abs(
                                float(last_event["bet_bb"])
                                - float(event["bet_bb"])
                            ) <= 0.05
                        )
                    )
                )
                if not same_event:
                    history.append(event)
                    del history[:-12]
                if inferred_action == "FOLD":
                    memory["folded"] = True

            memory["last_seen"] = now
            if bet is not None:
                self.player_round_max_bet = max(self.player_round_max_bet, bet)

            action = str(memory.get("action", "UNKNOWN")).upper()
            status = memory.get("status", "active")
            if memory.get("folded"):
                status = "folded"

            # PokerStars commonly replaces the numeric stack with "All In".
            # The last reliable stack therefore remains available as context;
            # the action tells the site that the player has committed it.
            result = {
                "seat_index": memory.get("seat_index"),
                "x": memory.get("x", 0),
                "y": memory.get("y", 0),
                "name": memory.get("name", ""),
                "stack_bb": memory.get("stack_bb"),
                "bet_bb": memory.get("round_bet_bb"),
                "action": action,
                "action_at": memory.get("action_at", 0.0),
                "action_history": list(memory.get("action_history", [])),
                "status": status,
                "stale": False,
                "last_seen_age": 0.0,
                "raw": str(obs.get("raw", ""))[:80],
            }
            complete = result["stack_bb"] is not None
            result["data_state"] = "complete" if complete else "partial"
            enriched.append(result)

        # Preserve the last reliable named reading briefly instead of erasing it
        # when one OCR frame misses the player.
        for key, memory in list(self.player_memory.items()):
            if key in current_keys or not memory.get("name"):
                continue
            age = max(0.0, now - float(memory.get("last_seen", 0) or 0))
            if age > 90:
                continue
            enriched.append({
                "seat_index": memory.get("seat_index"),
                "x": memory.get("x", 0),
                "y": memory.get("y", 0),
                "name": memory.get("name", ""),
                "stack_bb": memory.get("stack_bb"),
                "bet_bb": memory.get("round_bet_bb"),
                "action": str(memory.get("action", "UNKNOWN")).upper(),
                "action_at": memory.get("action_at", 0.0),
                "action_history": list(memory.get("action_history", [])),
                "status": "folded" if memory.get("folded") else memory.get("status", "active"),
                "stale": True,
                "last_seen_age": round(age, 2),
                "data_state": "stale",
                "raw": "",
            })

        return enriched[:10]

    def _table_worker(self, region: dict, max_seats: int) -> None:
        try:
            result = analyze_table(grab_box(region), max_seats=max_seats)
        except Exception as exc:
            result = {"valid": False, "error": str(exc)}
        finally:
            result["_scan_at"] = time.time()
            with self.table_lock:
                self.table_result = result
                self.table_pending = False

    def _tournament_worker(self, region: dict) -> None:
        try:
            result = analyze_tournament_hud(grab_box(region))
        except Exception as exc:
            result = {"valid": False, "error": str(exc), "raw_text": ""}
        finally:
            result["_scan_at"] = time.time()
            with self.tournament_lock:
                self.tournament_result = result
                self.tournament_pending = False

    def schedule_tournament_scan(self) -> None:
        if not self.running or self.tournament_pending:
            return
        if not bool(self.config.get("tournament_hud_enabled", False)):
            return
        region = self.config.get("tournament_hud")
        if not region:
            return
        now = time.time()
        if now - self.last_tournament_scan < 1.0:
            return
        self.last_tournament_scan = now
        self.tournament_pending = True
        threading.Thread(
            target=self._tournament_worker,
            args=(region,),
            name="PokerVisionTournamentOCR",
            daemon=True,
        ).start()

    def apply_tournament_result(self) -> None:
        if not bool(self.config.get("tournament_hud_enabled", False)):
            return
        with self.tournament_lock:
            data = dict(self.tournament_result) if self.tournament_result else None
        if not data:
            return
        scan_at = float(data.get("_scan_at", 0) or 0)
        if scan_at <= self.last_applied_tournament_scan_at:
            return
        self.last_applied_tournament_scan_at = scan_at

        if data.get("error"):
            self.tournament_hud_readout.configure(
                text=f"HUD TORNEIO: erro · {str(data['error'])[:70]}"
            )
            _bridge_publish_tournament({
                "tournament_hud_enabled": True,
                "tournament_hud_state": "error",
                "tournament_hud_at": scan_at,
            })
            return

        if not data.get("valid"):
            self.tournament_hud_readout.configure(
                text="HUD TORNEIO: leitura parcial · motor continua sem esses dados"
            )
            _bridge_publish_tournament({
                "tournament_hud_enabled": True,
                "tournament_hud_state": "partial",
                "tournament_hud_at": scan_at,
            })
            return

        rank = data.get("rank")
        remaining = data.get("remaining")
        avg = data.get("avg_stack_bb")
        sb = data.get("small_blind")
        bb = data.get("big_blind")
        ante = data.get("ante")
        seconds = data.get("level_seconds")

        parts = []
        if rank is not None and remaining is not None:
            parts.append(f"{int(rank)}/{int(remaining)}")
        if avg is not None:
            parts.append(f"média {avg:g} BB")
        if sb is not None and bb is not None:
            blind_text = f"{sb:g}/{bb:g}"
            if ante is not None:
                blind_text += f"({ante:g})"
            parts.append(blind_text)
        if seconds is not None:
            parts.append(f"{int(seconds)//60:02d}:{int(seconds)%60:02d}")

        self.tournament_hud_readout.configure(
            text="HUD TORNEIO: " + (" · ".join(parts) if parts else "confirmado")
        )
        payload = {
            "tournament_hud_enabled": True,
            "tournament_hud_state": "confirmed",
            "tournament_hud_at": scan_at,
            "tournament_rank": rank,
            "tournament_remaining": remaining,
            "tournament_avg_stack_bb": avg,
            "tournament_small_blind": sb,
            "tournament_big_blind": bb,
            "tournament_ante": ante,
            "tournament_level_seconds": seconds,
        }
        _bridge_publish_tournament(payload)

        signature = (
            rank, remaining, avg, sb, bb, ante,
            None if seconds is None else int(seconds) // 5,
        )
        if signature != self.last_logged_tournament_state:
            LOGGER.info(
                "TOURNAMENT_HUD %s raw=%r",
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                str(data.get("raw_text", ""))[:240],
            )
            self.last_logged_tournament_state = signature

    def schedule_table_scan(self) -> None:
        if not self.running or self.table_pending:
            return
        region = self.config.get("table")
        if not region:
            return
        now = time.time()
        if now - self.last_table_scan < 0.25:
            return

        self.last_table_scan = now
        self.table_pending = True
        max_seats = int(_bridge_snapshot().get("table_max_seats", 9) or 9)
        threading.Thread(
            target=self._table_worker,
            args=(region, max_seats),
            name="PokerVisionTableOCR",
            daemon=True,
        ).start()

    def _stable_inactive_seats(
        self,
        data: dict,
        max_seats: int,
        now: float,
    ) -> list[int]:
        raw_inactive = {
            int(value)
            for value in data.get("inactive_seat_indices", [])
            if isinstance(value, int) and 0 <= int(value) < max_seats
        }
        fresh_stack_seats = {
            int(obs["seat_index"])
            for obs in data.get("seat_observations", [])
            if (
                obs.get("seat_index") is not None
                and obs.get("stack_bb") is not None
                and 0 <= int(obs["seat_index"]) < max_seats
            )
        }

        for seat in raw_inactive:
            self.inactive_seat_memory[seat] = now
            self.active_seat_streak[seat] = 0

        # An inactive seat is cleared only after two consecutive OCR scans
        # show a real stack on that exact physical seat.
        for seat in list(self.inactive_seat_memory):
            if seat in raw_inactive:
                continue
            if seat in fresh_stack_seats:
                streak = int(self.active_seat_streak.get(seat, 0)) + 1
                self.active_seat_streak[seat] = streak
                if streak >= 2:
                    self.inactive_seat_memory.pop(seat, None)
                    self.active_seat_streak.pop(seat, None)
            else:
                self.active_seat_streak[seat] = 0

        # Drop impossible indices if table capacity changes.
        for seat in list(self.inactive_seat_memory):
            if not 0 <= int(seat) < max_seats:
                self.inactive_seat_memory.pop(seat, None)
                self.active_seat_streak.pop(seat, None)

        return sorted(self.inactive_seat_memory)

    def apply_table_result(self) -> None:
        with self.table_lock:
            data = dict(self.table_result) if self.table_result else None
        if not data:
            return

        scan_at = float(data.get("_scan_at", 0) or 0)
        if scan_at <= self.last_applied_table_scan_at:
            return
        self.last_applied_table_scan_at = scan_at
        now = scan_at or time.time()
        if data.get("error"):
            error = str(data["error"])
            self.table_readout.configure(
                text=f"JOGADORES: ERRO · {error}"
            )
            _bridge_publish_table({
                "table_scan_state": "error",
                "table_scan_at": now,
                "table_scan_confidence": "baixa",
            })
            signature = ("error", error[:80])
            if signature != self.last_logged_table_state:
                LOGGER.warning("TABLE_OCR error=%s", error)
                self.last_logged_table_state = signature
            return

        if not data.get("valid"):
            evidence = int(data.get("evidence_words", 0) or 0)
            self.table_readout.configure(
                text=f"JOGADORES: leitura parcial · evidências={evidence}"
            )
            _bridge_publish_table({
                "table_scan_state": "partial",
                "table_scan_at": now,
                "table_scan_confidence": "baixa",
            })
            signature = ("partial", evidence)
            if signature != self.last_logged_table_state:
                LOGGER.info("TABLE_OCR partial evidence=%s", evidence)
                self.last_logged_table_state = signature
            return

        max_seats = int(data.get("max_seats", _bridge_snapshot().get("table_max_seats", 9)))
        inactive_indices = self._stable_inactive_seats(data, max_seats, now)
        inactive = len(inactive_indices)
        count = infer_player_count(max_seats, inactive)
        if count is None:
            self.table_readout.configure(text="JOGADORES: leitura inconsistente")
            return

        points = [
            [round(float(SEAT_LAYOUTS[max_seats][seat][0]), 4),
             round(float(SEAT_LAYOUTS[max_seats][seat][1]), 4)]
            for seat in inactive_indices
        ]
        players = self._merge_player_observations(
            list(data.get("seat_observations", [])),
            now,
        )
        signature = (count, inactive, tuple(inactive_indices), max_seats)
        self.table_tracker.observe(signature)

        if not (
            self.table_tracker.ready
            and self.table_tracker.stable == signature
        ):
            self.table_readout.configure(
                text=(
                    f"JOGADORES: candidato {count}/{max_seats} · "
                    f"inativos/vazios {inactive} · confirmando 3 leituras rápidas"
                )
            )
            _bridge_publish_table({
                "table_scan_state": "partial",
                "table_scan_at": now,
                "table_scan_confidence": str(data.get("confidence", "média")),
            })
            return

        confidence = str(data.get("confidence", "média"))
        self.table_readout.configure(
            text=(
                f"JOGADORES: {count}/{max_seats} · "
                f"inativos/vazios {inactive} · confirmado"
            )
        )
        live_players = [p for p in players if not p.get("stale")]
        stacks = [
            float(p["stack_bb"])
            for p in live_players
            if p.get("stack_bb") is not None
        ]
        self.players_readout.configure(
            text=(
                f"STACKS DA MESA: {len(stacks)}/{max(0, count - 1)} adversários lidos"
                + (
                    " · " + " | ".join(f"{value:g} BB" for value in stacks[:8])
                    if stacks else ""
                )
            )
        )
        _bridge_publish_table({
            "detected_player_count": count,
            "inactive_seats": inactive,
            "table_max_seats": max_seats,
            "table_scan_confidence": confidence,
            "table_scan_state": "confirmed",
            "table_scan_at": now,
            "inactive_points": points,
            "inactive_seat_indices": inactive_indices,
            "seat_observations": players,
        })

        logged = ("confirmed", count, inactive, max_seats)
        if logged != self.last_logged_table_state:
            LOGGER.info(
                "TABLE_OCR confirmed active=%s max=%s inactive=%s confidence=%s",
                count,
                max_seats,
                inactive,
                confidence,
            )
            self.last_logged_table_state = logged
            LOGGER.info(
                "PLAYERS %s",
                json.dumps(players, ensure_ascii=False, separators=(",", ":")),
            )

    @staticmethod
    def _repair_factor_ten(previous, current):
        if previous is None or current is None:
            return current
        previous = float(previous)
        current = float(current)
        if previous <= 0 or current <= 0:
            return current

        for candidate in (current / 10.0, current * 10.0):
            if abs(candidate - previous) / previous <= 0.08:
                return round(candidate, 4)
        return current

    def _sanitize_numeric_result(self, data: dict) -> dict:
        clean = dict(data)
        previous = _bridge_snapshot().get("hero_stack_bb")
        current = clean.get("hero_stack_bb")
        repaired = self._repair_factor_ten(previous, current)
        if current is not None and repaired != current:
            LOGGER.warning(
                "NUMERIC repaired factor10 hero_stack raw=%s previous=%s repaired=%s text=%r",
                current,
                previous,
                repaired,
                clean.get("hero_text", ""),
            )
            clean["hero_stack_bb"] = repaired

        # The dedicated pot crop is fast but can occasionally misread one
        # digit. Cross-check it against the independent full-table OCR, which
        # only contributes a value when it sees an explicit "Pote: X BB".
        table_pot = None
        with self.table_lock:
            if self.table_result:
                table_pot = self.table_result.get("table_pot_bb")
        numeric_pot = clean.get("pot_bb")
        if table_pot is not None and float(table_pot) > 0:
            if numeric_pot is None:
                clean["pot_bb"] = float(table_pot)
            else:
                numeric_pot = float(numeric_pot)
                table_pot = float(table_pot)
                difference = abs(numeric_pot - table_pot) / max(table_pot, 0.01)
                if difference > 0.12:
                    LOGGER.warning(
                        "NUMERIC pot disagreement crop=%s table=%s; using table label",
                        numeric_pot,
                        table_pot,
                    )
                    clean["pot_bb"] = table_pot
        return clean

    def _numeric_signature(self, data: dict) -> tuple:
        return (
            self._round_value(data.get("hero_stack_bb")),
            self._round_value(data.get("pot_bb")),
            self._round_value(data.get("hero_stack_chips")),
            self._round_value(data.get("pot_chips")),
        )

    def _numeric_worker(self, regions: dict) -> None:
        result: dict = {}
        try:
            if OCR_ERROR:
                result["error"] = OCR_ERROR
            else:
                if regions.get("hero_stack"):
                    result["hero_stack_bb"] = None
                    result["hero_stack_chips"] = None
                    hero_read = read_single_number(grab_box(regions["hero_stack"]))
                    result["hero_text"] = hero_read["text"]
                    if hero_read.get("unit") == "bb":
                        result["hero_stack_bb"] = hero_read["value"]
                    else:
                        result["hero_stack_chips"] = hero_read["value"]

                if regions.get("pot"):
                    # Explicitly publish None when the current crop is unreadable.
                    # This prevents the bridge/site from silently reusing an old pot.
                    result["pot_bb"] = None
                    result["pot_chips"] = None
                    pot_read = read_pot(grab_box(regions["pot"]))
                    result["pot_text"] = pot_read["text"]
                    if pot_read.get("unit") == "bb" and pot_read.get("value") is not None:
                        result["pot_bb"] = pot_read["value"]
        except Exception as exc:
            result = {"error": str(exc)}
        finally:
            with self.numeric_lock:
                self.numeric_result = result
                self.numeric_pending = False

    def schedule_numeric_scan(self) -> None:
        if not self.running or self.numeric_pending:
            return
        now = time.time()
        if now - self.last_numeric_scan < 1.0:
            return

        regions = {
            key: self.config.get(key)
            for key in ("hero_stack", "pot")
        }
        if not any(regions.values()):
            return

        self.last_numeric_scan = now
        self.numeric_pending = True
        threading.Thread(
            target=self._numeric_worker,
            args=(regions,),
            name="PokerVisionNumericOCR",
            daemon=True,
        ).start()

    def apply_numeric_result(self) -> None:
        with self.numeric_lock:
            data = dict(self.numeric_result) if self.numeric_result else None
        if not data:
            return
        data = self._sanitize_numeric_result(data)
        if data.get("error"):
            self.numeric_readout.configure(
                text=f"OCR NUMÉRICO: {data['error']}"
            )
            return

        hero_bb = data.get("hero_stack_bb")
        pot_bb = data.get("pot_bb")
        parts = []
        if hero_bb is not None:
            parts.append(f"MEU STACK {hero_bb:g} BB")
        if pot_bb is not None:
            parts.append(f"POTE {pot_bb:g} BB")
        self.numeric_readout.configure(
            text="OCR NUMÉRICO: " + (" · ".join(parts) if parts else "sem leitura BB estável")
        )

        raw_parts = []
        for label, key in (
            ("MEU STACK", "hero_text"),
            ("POTE", "pot_text"),
        ):
            raw = str(data.get(key, "")).strip()
            if raw:
                raw_parts.append(f"{label}='{raw}'")
        self.numeric_raw_readout.configure(
            text="OCR BRUTO: " + (" | ".join(raw_parts) if raw_parts else "—")
        )

        signature = self._numeric_signature(data)
        self.numeric_tracker.observe(signature)
        if self.numeric_tracker.ready and self.numeric_tracker.stable == signature:
            _bridge_publish_numeric(data)
            if signature != self.last_logged_numeric_state:
                LOGGER.info(
                    "NUMERIC stable hero_stack_bb=%s pot_bb=%s",
                    data.get("hero_stack_bb"),
                    data.get("pot_bb"),
                )
                self.last_logged_numeric_state = signature

    def preview_once(self) -> None:
        try:
            delivery = delivery_status()
            if delivery["ok"]:
                self.bridge_readout.configure(
                    text=f"SITE: OK · {delivery['target']}"
                )
            else:
                self.bridge_readout.configure(
                    text=f"SITE: aguardando Beelink · {delivery['message'][:70]}"
                )

            self.schedule_numeric_scan()
            self.apply_numeric_result()
            self.schedule_table_scan()
            self.apply_table_result()
            self.schedule_tournament_scan()
            self.apply_tournament_result()

            hand_image = self.preview_region(
                self.config["hand"],
                self.hand_preview,
                "hand",
            )
            board_image = self.preview_region(
                self.config["board"],
                self.board_preview,
                "board",
            )
            if hand_image is not None and board_image is not None:
                self.update_recognition(hand_image, board_image)
        except Exception as exc:
            self.status.configure(text=f"Falha de captura/reconhecimento: {exc}")
            LOGGER.exception("PREVIEW failure: %s", exc)

    def start(self) -> None:
        if not self.config["hand"] or not self.config["board"]:
            messagebox.showwarning(
                "PokerVision",
                "Selecione primeiro a região da MÃO e a região do BOARD.",
            )
            return
        if self.running:
            return

        self.hand_tracker.reset()
        self.board_tracker.reset()
        self.numeric_tracker.reset()
        self.table_tracker.reset()
        self.player_memory.clear()
        self.inactive_seat_memory.clear()
        self.active_seat_streak.clear()
        self.player_round_key = None
        self.player_hand_key = None
        self.player_round_max_bet = 0.0
        _bridge_publish_table({
            "detected_player_count": None,
            "inactive_seats": None,
            "table_max_seats": int(_bridge_snapshot().get("table_max_seats", 9) or 9),
            "table_scan_confidence": "",
            "table_scan_state": "waiting" if self.config.get("table") else "disabled",
            "table_scan_at": 0.0,
            "inactive_points": [],
            "inactive_seat_indices": [],
            "seat_observations": [],
        })
        hud_enabled = bool(self.config.get("tournament_hud_enabled", False))
        _bridge_publish_tournament({
            "tournament_hud_enabled": hud_enabled,
            "tournament_hud_state": (
                "waiting"
                if hud_enabled and self.config.get("tournament_hud")
                else "not_configured"
                if hud_enabled
                else "disabled"
            ),
            "tournament_hud_at": 0.0,
        })
        self.running = True
        _bridge_publish(running=True, confirmed=False)
        self.status.configure(
            text="RECONHECIMENTO ATIVO · confirmando leituras em 3 capturas."
        )
        LOGGER.info(
            "MONITOR start table=%s max_seats=%s",
            bool(self.config.get("table")),
            _bridge_snapshot().get("table_max_seats", 9),
        )
        self.refresh_loop()

    def stop(self) -> None:
        was_running = self.running
        self.running = False
        _bridge_publish(running=False, confirmed=False)
        if was_running:
            LOGGER.info("MONITOR stop")
        if self.config["hand"] and self.config["board"]:
            self.status.configure(
                text="Monitoramento parado. Regiões continuam salvas."
            )

    def refresh_loop(self) -> None:
        if not self.running:
            return
        self.preview_once()
        self.root.after(self.REFRESH_MS, self.refresh_loop)

    def copy_diagnostics(self) -> None:
        with self.numeric_lock:
            numeric = dict(self.numeric_result) if self.numeric_result else None
        with self.table_lock:
            table = dict(self.table_result) if self.table_result else None

        config_summary = {}
        for key in CALIBRATION_KEYS:
            region = self.config.get(key)
            config_summary[key] = bool(region)
        config_summary["table_max_seats"] = _bridge_snapshot().get(
            "table_max_seats", 9
        )
        config_summary["tournament_hud_enabled"] = bool(
            self.config.get("tournament_hud_enabled", False)
        )

        payload = {
            "PokerVision": APP_VERSION,
            "running": self.running,
            "bridge": _bridge_snapshot(),
            "delivery": delivery_status(),
            "config": config_summary,
            "numeric_last": numeric,
            "table_last": table,
            "tournament_last": (
                dict(self.tournament_result)
                if self.tournament_result
                else None
            ),
            "log_file": str(log_path()),
        }
        text = json.dumps(payload, indent=2, ensure_ascii=False, default=str)
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.root.update()
            LOGGER.info("DIAGNOSTICS copied")
            messagebox.showinfo(
                "PokerVision",
                "Diagnóstico copiado. Pode colar direto no ChatGPT.",
            )
        except Exception as exc:
            LOGGER.exception("DIAGNOSTICS copy failure: %s", exc)
            messagebox.showerror(
                "PokerVision",
                f"Falha ao copiar diagnóstico:\n{exc}\n\nLog: {log_path()}",
            )

    def save_sample(self) -> None:
        if not self.config["hand"] or not self.config["board"]:
            messagebox.showwarning(
                "PokerVision",
                "Configure MÃO e BOARD antes de salvar uma amostra.",
            )
            return

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        folder = capture_dir()
        try:
            grab_box(self.config["hand"]).save(folder / f"{stamp}_hand.png")
            grab_box(self.config["board"]).save(folder / f"{stamp}_board.png")
            for key in ("hero_stack", "pot", "table", "tournament_hud"):
                region = self.config.get(key)
                if region:
                    grab_box(region).save(folder / f"{stamp}_{key}.png")
        except Exception as exc:
            messagebox.showerror("PokerVision", f"Falha ao salvar amostra:\n{exc}")
            return

        messagebox.showinfo(
            "PokerVision",
            f"Amostras salvas em:\n{folder}",
        )

    def close(self) -> None:
        self.running = False
        _bridge_publish(running=False, confirmed=False)
        LOGGER.info("CLOSE")
        self.root.destroy()


def main() -> None:
    enable_dpi_awareness()
    setup_logging()
    start_bridge_server()
    start_beelink_publisher()
    root = tk.Tk()
    PokerVisionApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
