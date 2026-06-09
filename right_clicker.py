import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

import pyautogui
from pynput import keyboard

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05


class AutoRightClicker:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Sağ Tık")
        self.root.resizable(False, False)

        self.running = False
        self.thread: threading.Thread | None = None

        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")

        main = ttk.Frame(root, padding=16)
        main.grid(row=0, column=0, sticky="nsew")

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
        btn_frame.grid(row=5, column=0, columnspan=4, pady=(16, 8), sticky="ew")
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)

        self.start_btn = ttk.Button(btn_frame, text="Başlat (F7)", command=self.start)
        self.start_btn.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self.stop_btn = ttk.Button(
            btn_frame, text="Durdur (F7)", command=self.stop, state=tk.DISABLED
        )
        self.stop_btn.grid(row=0, column=1, sticky="ew", padx=(6, 0))

        self.status = ttk.Label(main, text="Hazır", foreground="gray")
        self.status.grid(row=6, column=0, columnspan=4, pady=(4, 0))

        ttk.Label(
            main,
            text="F7 ile başlat/durdur · Fareyi sol üst köşeye götürünce acil durur",
            font=("Segoe UI", 8),
            foreground="gray",
        ).grid(row=7, column=0, columnspan=4, pady=(8, 0))

        self._listener: keyboard.Listener | None = None
        self._setup_hotkey()
        self.root.bind("<F7>", lambda _event: self.toggle())
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def set_status(self, text: str, color: str = "gray") -> None:
        self.status.config(text=text, foreground=color)

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

    def toggle(self) -> None:
        if self.running:
            self.stop()
        else:
            self.start()

    def _setup_hotkey(self) -> None:
        def on_press(key: keyboard.Key | keyboard.KeyCode | None) -> None:
            if key == keyboard.Key.f7:
                self.root.after(0, self.toggle)

        self._listener = keyboard.Listener(on_press=on_press)
        self._listener.daemon = True
        self._listener.start()

    def start(self) -> None:
        try:
            x = int(self.x_entry.get().strip())
            y = int(self.y_entry.get().strip())
            interval = float(self.interval_entry.get().strip().replace(",", "."))
            if interval <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Hata", "Geçerli X, Y ve aralık değerleri girin.")
            return

        self.running = True
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.capture_btn.config(state=tk.DISABLED)
        self.set_status(f"Çalışıyor — her {interval} sn sağ tık", "green")

        self.thread = threading.Thread(
            target=self._loop, args=(x, y, interval), daemon=True
        )
        self.thread.start()

    def stop(self) -> None:
        self.running = False
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.capture_btn.config(state=tk.NORMAL)
        self.set_status("Durduruldu", "gray")

    def _loop(self, x: int, y: int, interval: float) -> None:
        while self.running:
            try:
                pyautogui.rightClick(x, y)
            except pyautogui.FailSafeException:
                self.root.after(0, self.stop)
                self.root.after(0, lambda: self.set_status("Güvenlik durdurması", "orange"))
                return
            time.sleep(interval)

    def on_close(self) -> None:
        self.running = False
        if self._listener is not None:
            self._listener.stop()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    AutoRightClicker(root)
    root.mainloop()


if __name__ == "__main__":
    main()
