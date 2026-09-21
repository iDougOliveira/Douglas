from __future__ import annotations

import ctypes
import ipaddress
import json
import os
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
from urllib.parse import urlparse

import mss
from PIL import Image, ImageTk

from recognizer import card_text, recognize_board, recognize_hand, street_from_board


APP_VERSION = "0.3.0"
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


def config_path() -> Path:
    base = Path(os.environ.get("APPDATA", Path.home()))
    path = base / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path / "config.json"


def capture_dir() -> Path:
    path = Path.home() / "PokerVisionCaptures"
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_config() -> dict:
    path = config_path()
    if not path.exists():
        return {"hand": None, "board": None}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {
            "hand": data.get("hand"),
            "board": data.get("board"),
        }
    except Exception:
        return {"hand": None, "board": None}


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
        _bridge_publish(
            running=False,
            confirmed=False,
            hand=[],
            board=[],
            street="AGUARDANDO",
        )

        root.title(f"{APP_NAME} {APP_VERSION}")
        root.geometry("960x700")
        root.minsize(780, 600)
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
        actions.pack(fill="x", pady=(0, 14))

        ttk.Button(
            actions,
            text="1. Selecionar MÃO",
            command=lambda: self.select_region("hand"),
        ).pack(side="left", padx=(0, 8))
        ttk.Button(
            actions,
            text="2. Selecionar BOARD",
            command=lambda: self.select_region("board"),
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

        coords = ttk.Frame(outer, style="Card.TFrame", padding=12)
        coords.pack(fill="x", pady=(0, 14))
        self.hand_coords = ttk.Label(coords, text="")
        self.hand_coords.pack(anchor="w")
        self.board_coords = ttk.Label(coords, text="")
        self.board_coords.pack(anchor="w", pady=(4, 0))
        self.street_readout = ttk.Label(
            coords,
            text="STREET: —",
            style="Detect.TLabel",
        )
        self.street_readout.pack(anchor="w", pady=(8, 0))
        self.bridge_readout = ttk.Label(
            coords,
            text=f"SITE: pronto em {BRIDGE_HOST}:{BRIDGE_PORT}",
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
            text="Salvar amostra",
            command=self.save_sample,
        ).pack(side="right", padx=(10, 0))

    def select_region(self, key: str) -> None:
        label = "SUAS DUAS CARTAS" if key == "hand" else "FLOP / TURN / RIVER"
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
        if self.config["hand"] and self.config["board"]:
            self.status.configure(text="Pronto para iniciar o reconhecimento.")
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

    def preview_once(self) -> None:
        try:
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
        self.running = True
        _bridge_publish(running=True, confirmed=False)
        self.status.configure(
            text="RECONHECIMENTO ATIVO · confirmando leituras em 3 capturas."
        )
        self.refresh_loop()

    def stop(self) -> None:
        self.running = False
        _bridge_publish(running=False, confirmed=False)
        if self.config["hand"] and self.config["board"]:
            self.status.configure(
                text="Monitoramento parado. Regiões continuam salvas."
            )

    def refresh_loop(self) -> None:
        if not self.running:
            return
        self.preview_once()
        self.root.after(self.REFRESH_MS, self.refresh_loop)

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
        self.root.destroy()


def main() -> None:
    enable_dpi_awareness()
    start_bridge_server()
    root = tk.Tk()
    PokerVisionApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
