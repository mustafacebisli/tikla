import json
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import pyautogui
from pynput import keyboard, mouse

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05

COMBO_FILE = Path(__file__).parent / "combo.json"


class ClickRipple:
    """Tıklama noktasında genişleyen halka animasyonu gösterir."""

    SIZE = 100
    FRAMES = 14
    INTERVAL_MS = 25

    COLORS = {
        "left": ("#42A5F5", "#1565C0"),
        "right": ("#FF7043", "#E64A19"),
    }

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.enabled = True

    def show(self, x: int, y: int, button: str = "right") -> None:
        if not self.enabled:
            return
        self.root.after(0, lambda: self._animate(x, y, button))

    def _animate(self, x: int, y: int, button: str) -> None:
        fill, outline = self.COLORS.get(button, self.COLORS["right"])
        half = self.SIZE // 2

        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg="magenta")
        try:
            win.attributes("-transparentcolor", "magenta")
        except tk.TclError:
            pass
        win.geometry(f"{self.SIZE}x{self.SIZE}+{x - half}+{y - half}")

        canvas = tk.Canvas(
            win, width=self.SIZE, height=self.SIZE, bg="magenta", highlightthickness=0
        )
        canvas.pack()

        cx, cy = half, half
        dot = canvas.create_oval(cx - 5, cy - 5, cx + 5, cy + 5, fill=fill, outline="")
        ring = canvas.create_oval(cx - 10, cy - 10, cx + 10, cy + 10, outline=outline, width=3)

        def step(frame: int = 0) -> None:
            if frame >= self.FRAMES:
                win.destroy()
                return

            progress = frame / self.FRAMES
            radius = 10 + progress * 32
            width = max(1, int(3 - progress * 2.5))
            canvas.coords(ring, cx - radius, cy - radius, cx + radius, cy + radius)
            canvas.itemconfigure(ring, width=width)
            if progress > 0.4:
                canvas.itemconfigure(dot, state="hidden")

            win.after(self.INTERVAL_MS, lambda: step(frame + 1))

        step()


class AutoClickerApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Tık Otomasyon")
        self.root.resizable(False, False)

        self.running = False
        self.recording = False
        self.thread: threading.Thread | None = None
        self.sequence: list[dict] = []
        self._last_click_time: float | None = None

        self._keyboard_listener: keyboard.Listener | None = None
        self._mouse_listener: mouse.Listener | None = None
        self.ripple = ClickRipple(root)

        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")

        notebook = ttk.Notebook(root, padding=8)
        notebook.grid(row=0, column=0, sticky="nsew")

        self.simple_tab = ttk.Frame(notebook, padding=8)
        self.combo_tab = ttk.Frame(notebook, padding=8)
        notebook.add(self.simple_tab, text="Tek Sağ Tık")
        notebook.add(self.combo_tab, text="Kombinasyon")
        self.notebook = notebook

        self._build_simple_tab()
        self._build_combo_tab()

        opts = ttk.Frame(root, padding=(8, 0))
        opts.grid(row=1, column=0, sticky="w")
        self.anim_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            opts,
            text="Tıklama animasyonu göster",
            variable=self.anim_var,
            command=self._toggle_animation,
        ).pack(side=tk.LEFT)

        self.status = ttk.Label(root, text="Hazır", foreground="gray", padding=(8, 4))
        self.status.grid(row=2, column=0, sticky="ew")

        ttk.Label(
            root,
            text="F7 başlat/durdur · F8 kayıt başlat/bitir · Sol üst köşe acil durdurma",
            font=("Segoe UI", 8),
            foreground="gray",
            padding=(8, 0, 8, 8),
        ).grid(row=3, column=0)

        self._load_sequence()
        self._setup_hotkeys()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def set_status(self, text: str, color: str = "gray") -> None:
        self.status.config(text=text, foreground=color)

    def _toggle_animation(self) -> None:
        self.ripple.enabled = self.anim_var.get()

    def _click_at(self, x: int, y: int, button: str = "right") -> None:
        if button == "left":
            pyautogui.click(x, y)
        else:
            pyautogui.rightClick(x, y)
        self.ripple.show(x, y, button)

    # --- Basit mod ---

    def _build_simple_tab(self) -> None:
        main = self.simple_tab

        ttk.Label(main, text="Hedef Konum", font=("Segoe UI", 10, "bold")).grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 8)
        )

        ttk.Label(main, text="X:").grid(row=1, column=0, sticky="e", padx=(0, 4))
        self.x_entry = ttk.Entry(main, width=10)
        self.x_entry.grid(row=1, column=1, sticky="w")

        ttk.Label(main, text="Y:").grid(row=1, column=2, sticky="e", padx=(12, 4))
        self.y_entry = ttk.Entry(main, width=10)
        self.y_entry.grid(row=1, column=3, sticky="w")

        self.capture_btn = ttk.Button(
            main, text="Konumu Al (3 sn)", command=self.capture_position
        )
        self.capture_btn.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(8, 12))

        ttk.Separator(main, orient="horizontal").grid(
            row=3, column=0, columnspan=4, sticky="ew", pady=(0, 12)
        )

        ttk.Label(main, text="Aralık (saniye):").grid(row=4, column=0, columnspan=2, sticky="w")
        self.interval_entry = ttk.Entry(main, width=10)
        self.interval_entry.insert(0, "5")
        self.interval_entry.grid(row=4, column=2, columnspan=2, sticky="w")

        btn_frame = ttk.Frame(main)
        btn_frame.grid(row=5, column=0, columnspan=4, pady=(16, 0), sticky="ew")
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)

        self.simple_start_btn = ttk.Button(btn_frame, text="Başlat (F7)", command=self.start_simple)
        self.simple_start_btn.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self.simple_stop_btn = ttk.Button(
            btn_frame, text="Durdur (F7)", command=self.stop, state=tk.DISABLED
        )
        self.simple_stop_btn.grid(row=0, column=1, sticky="ew", padx=(6, 0))

    def capture_position(self) -> None:
        self.capture_btn.config(state=tk.DISABLED)
        self.set_status("3 saniye içinde fareyi hedefe götürün...", "blue")
        self.root.after(3000, self._set_position)

    def _set_position(self) -> None:
        x, y = pyautogui.position()
        self.x_entry.delete(0, tk.END)
        self.x_entry.insert(0, str(x))
        self.y_entry.delete(0, tk.END)
        self.y_entry.insert(0, str(y))
        self.capture_btn.config(state=tk.NORMAL)
        self.set_status(f"Konum alındı: ({x}, {y})", "green")

    def start_simple(self) -> None:
        try:
            x = int(self.x_entry.get().strip())
            y = int(self.y_entry.get().strip())
            interval = float(self.interval_entry.get().strip().replace(",", "."))
            if interval <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Hata", "Geçerli X, Y ve aralık değerleri girin.")
            return

        self._begin_running(f"Çalışıyor — her {interval} sn sağ tık")
        self.thread = threading.Thread(
            target=self._simple_loop, args=(x, y, interval), daemon=True
        )
        self.thread.start()

    def _simple_loop(self, x: int, y: int, interval: float) -> None:
        while self.running:
            try:
                self._click_at(x, y, "right")
            except pyautogui.FailSafeException:
                self.root.after(0, self._fail_safe_stop)
                return
            time.sleep(interval)

    # --- Kombinasyon modu ---

    def _build_combo_tab(self) -> None:
        main = self.combo_tab

        ttk.Label(main, text="Tıklama Kombinasyonu", font=("Segoe UI", 10, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 4)
        )
        ttk.Label(
            main,
            text="Kayıt başlatın, fareyi ilgili yerlere götürüp sol/sağ tıklayın.",
            font=("Segoe UI", 8),
            foreground="gray",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 8))

        rec_frame = ttk.Frame(main)
        rec_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        rec_frame.columnconfigure(0, weight=1)
        rec_frame.columnconfigure(1, weight=1)

        self.record_btn = ttk.Button(rec_frame, text="Kayıt Başlat (F8)", command=self.toggle_recording)
        self.record_btn.grid(row=0, column=0, sticky="ew", padx=(0, 4))

        self.clear_btn = ttk.Button(rec_frame, text="Temizle", command=self.clear_sequence)
        self.clear_btn.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        list_frame = ttk.Frame(main)
        list_frame.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=(0, 8))

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.sequence_list = tk.Listbox(
            list_frame, height=8, width=48, yscrollcommand=scrollbar.set, font=("Consolas", 9)
        )
        self.sequence_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.sequence_list.yview)

        ttk.Separator(main, orient="horizontal").grid(row=4, column=0, columnspan=2, sticky="ew", pady=8)

        ttk.Label(main, text="Tekrar aralığı (saniye):").grid(row=5, column=0, sticky="w")
        self.combo_interval_entry = ttk.Entry(main, width=10)
        self.combo_interval_entry.insert(0, "10")
        self.combo_interval_entry.grid(row=5, column=1, sticky="w")

        btn_frame = ttk.Frame(main)
        btn_frame.grid(row=6, column=0, columnspan=2, pady=(12, 0), sticky="ew")
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)

        self.combo_start_btn = ttk.Button(btn_frame, text="Başlat (F7)", command=self.start_combo)
        self.combo_start_btn.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self.combo_stop_btn = ttk.Button(
            btn_frame, text="Durdur (F7)", command=self.stop, state=tk.DISABLED
        )
        self.combo_stop_btn.grid(row=0, column=1, sticky="ew", padx=(6, 0))

    def _load_sequence(self) -> None:
        if COMBO_FILE.exists():
            try:
                self.sequence = json.loads(COMBO_FILE.read_text(encoding="utf-8"))
                self._refresh_sequence_list()
            except (json.JSONDecodeError, OSError):
                self.sequence = []

    def _save_sequence(self) -> None:
        try:
            COMBO_FILE.write_text(
                json.dumps(self.sequence, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass

    def _refresh_sequence_list(self) -> None:
        self.sequence_list.delete(0, tk.END)
        for i, action in enumerate(self.sequence, start=1):
            btn = "Sol" if action["button"] == "left" else "Sağ"
            delay = action.get("delay", 0)
            delay_text = f" (+{delay:.2f}s)" if i > 1 else ""
            self.sequence_list.insert(
                tk.END, f"{i:2}. {btn} tık @ ({action['x']}, {action['y']}){delay_text}"
            )

    def toggle_recording(self) -> None:
        if self.recording:
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self) -> None:
        if self.running:
            messagebox.showwarning("Uyarı", "Önce oynatmayı durdurun.")
            return

        self.recording = True
        self._last_click_time = None
        self.record_btn.config(text="Kayıt Bitir (F8)")
        self.clear_btn.config(state=tk.DISABLED)
        self.combo_start_btn.config(state=tk.DISABLED)
        self.set_status("Kayıt aktif — sol/sağ tıklayın, F8 ile bitirin", "red")
        self._start_mouse_listener()

    def stop_recording(self) -> None:
        self.recording = False
        self._stop_mouse_listener()
        self.record_btn.config(text="Kayıt Başlat (F8)")
        self.clear_btn.config(state=tk.NORMAL)
        self.combo_start_btn.config(state=tk.NORMAL)
        self._save_sequence()
        count = len(self.sequence)
        self.set_status(f"Kayıt bitti — {count} tıklama kaydedildi", "green")

    def clear_sequence(self) -> None:
        if self.recording:
            return
        if self.sequence and not messagebox.askyesno("Onay", "Kayıtlı kombinasyon silinsin mi?"):
            return
        self.sequence.clear()
        self._refresh_sequence_list()
        self._save_sequence()
        self.set_status("Kombinasyon temizlendi", "gray")

    def _on_mouse_click(self, x: int, y: int, button: mouse.Button, pressed: bool) -> None:
        if not pressed or not self.recording:
            return
        if button not in (mouse.Button.left, mouse.Button.right):
            return

        now = time.time()
        delay = round(now - self._last_click_time, 3) if self._last_click_time else 0.0
        self._last_click_time = now

        btn = "left" if button == mouse.Button.left else "right"
        action = {"x": x, "y": y, "button": btn, "delay": delay}
        self.sequence.append(action)
        self.root.after(0, self._refresh_sequence_list)
        self.root.after(
            0,
            lambda: self.set_status(
                f"Kaydedildi: {len(self.sequence)}. tıklama ({btn})", "red"
            ),
        )

    def _start_mouse_listener(self) -> None:
        self._stop_mouse_listener()
        self._mouse_listener = mouse.Listener(on_click=self._on_mouse_click)
        self._mouse_listener.daemon = True
        self._mouse_listener.start()

    def _stop_mouse_listener(self) -> None:
        if self._mouse_listener is not None:
            self._mouse_listener.stop()
            self._mouse_listener = None

    def start_combo(self) -> None:
        if self.recording:
            messagebox.showwarning("Uyarı", "Önce kaydı bitirin.")
            return
        if not self.sequence:
            messagebox.showerror("Hata", "Önce bir kombinasyon kaydedin.")
            return

        try:
            interval = float(self.combo_interval_entry.get().strip().replace(",", "."))
            if interval < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Hata", "Geçerli bir tekrar aralığı girin.")
            return

        count = len(self.sequence)
        self._begin_running(f"Çalışıyor — {count} tıklık kombinasyon, her {interval} sn tekrar")
        sequence = list(self.sequence)
        self.thread = threading.Thread(
            target=self._combo_loop, args=(sequence, interval), daemon=True
        )
        self.thread.start()

    def _combo_loop(self, sequence: list[dict], interval: float) -> None:
        while self.running:
            if not self._play_sequence_once(sequence):
                return
            if interval > 0:
                elapsed = 0.0
                while elapsed < interval and self.running:
                    time.sleep(min(0.1, interval - elapsed))
                    elapsed += 0.1

    def _play_sequence_once(self, sequence: list[dict]) -> bool:
        for i, action in enumerate(sequence):
            if not self.running:
                return True

            if i > 0:
                delay = action.get("delay", 0)
                if delay > 0:
                    time.sleep(delay)

            try:
                self._click_at(action["x"], action["y"], action["button"])
            except pyautogui.FailSafeException:
                self.root.after(0, self._fail_safe_stop)
                return False

        return True

    # --- Ortak ---

    def _begin_running(self, status_text: str) -> None:
        self.running = True
        self.simple_start_btn.config(state=tk.DISABLED)
        self.simple_stop_btn.config(state=tk.NORMAL)
        self.combo_start_btn.config(state=tk.DISABLED)
        self.combo_stop_btn.config(state=tk.NORMAL)
        self.capture_btn.config(state=tk.DISABLED)
        self.record_btn.config(state=tk.DISABLED)
        self.clear_btn.config(state=tk.DISABLED)
        self.set_status(status_text, "green")

    def stop(self) -> None:
        self.running = False
        self.simple_start_btn.config(state=tk.NORMAL)
        self.simple_stop_btn.config(state=tk.DISABLED)
        self.combo_start_btn.config(state=tk.NORMAL)
        self.combo_stop_btn.config(state=tk.DISABLED)
        self.capture_btn.config(state=tk.NORMAL)
        self.record_btn.config(state=tk.NORMAL)
        self.clear_btn.config(state=tk.NORMAL)
        self.set_status("Durduruldu", "gray")

    def _fail_safe_stop(self) -> None:
        self.stop()
        self.set_status("Güvenlik durdurması", "orange")

    def toggle(self) -> None:
        if self.running:
            self.stop()
            return

        tab = self.notebook.index(self.notebook.select())
        if tab == 0:
            self.start_simple()
        else:
            self.start_combo()

    def toggle_recording_hotkey(self) -> None:
        if self.notebook.index(self.notebook.select()) != 1:
            return
        self.toggle_recording()

    def _setup_hotkeys(self) -> None:
        def on_press(key: keyboard.Key | keyboard.KeyCode | None) -> None:
            if key == keyboard.Key.f7:
                self.root.after(0, self.toggle)
            elif key == keyboard.Key.f8:
                self.root.after(0, self.toggle_recording_hotkey)

        self._keyboard_listener = keyboard.Listener(on_press=on_press)
        self._keyboard_listener.daemon = True
        self._keyboard_listener.start()

        self.root.bind("<F7>", lambda _e: self.toggle())
        self.root.bind("<F8>", lambda _e: self.toggle_recording_hotkey())

    def on_close(self) -> None:
        self.running = False
        self.recording = False
        self._stop_mouse_listener()
        if self._keyboard_listener is not None:
            self._keyboard_listener.stop()
        self._save_sequence()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    AutoClickerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
