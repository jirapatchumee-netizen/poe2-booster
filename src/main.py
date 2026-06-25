"""
POE2 Booster Overlay — Main Application
========================================
Production version with:
- Persistent top bar (like POE Overlay)
- Expandable panel with boost actions
- First-time setup wizard
- System monitor
- Auto-start option
- Pro features (locked)
- Win32 API overlay

Run: pythonw main.py
Hotkey: F4 = Toggle panel
"""

import tkinter as tk
import threading
import subprocess
import os
import sys
import ctypes
import time
import io
import json

# Fix encoding
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import COLORS as C, APP_NAME, APP_VERSION, HOTKEY, IS_PRO
import booster
import updater
from wizard import SetupWizard, is_first_run

try:
    import keyboard
except ImportError:
    sys.exit("pip install keyboard")

try:
    import psutil
except ImportError:
    sys.exit("pip install psutil")

try:
    import pystray
    from PIL import Image, ImageDraw
except ImportError:
    pystray = None

# ─── Windows API ──────────────────────────────────────────
user32 = ctypes.windll.user32
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TOPMOST = 0x00000008
WS_EX_NOACTIVATE = 0x08000000
HWND_TOPMOST = -1
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040


class POE2BoosterApp:
    def __init__(self):
        self.bar_visible = True
        self.monitor_running = True
        self.stats = {"cpu": 0, "ram": 0, "gpu_temp": 0, "vram": 0}
        self.topmost_after_id = None

        self._build_bar()
        self._start_monitor()
        self._register_hotkey()
        self._start_tray()
        self._start_topmost_loop()

        # Show wizard on first run
        if is_first_run():
            self.root.after(500, self._show_wizard)

        # Check for updates in background (after 3 seconds)
        self.root.after(3000, self._check_update)

    # ══════════════════════════════════════════════════════
    #   TOP BAR
    # ══════════════════════════════════════════════════════
    def _build_bar(self):
        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.93)
        self.root.configure(bg=C["bar_bg"])

        bar_w, bar_h = 780, 32
        sw = self.root.winfo_screenwidth()
        x = (sw - bar_w) // 2

        self.root.geometry(f"{bar_w}x{bar_h}+{x}+0")
        self.root.update_idletasks()
        self._apply_win32_flags()

        bar = tk.Frame(self.root, bg=C["bar_bg"], height=bar_h)
        bar.pack(fill="x", side="top")
        bar.pack_propagate(False)
        self.bar = bar

        # Icon
        icon = tk.Label(bar, text="⚡", font=("Segoe UI Emoji", 11),
                        bg=C["bar_bg"], fg=C["accent"], padx=8)
        icon.pack(side="left")

        # Title
        title = tk.Label(bar, text=APP_NAME, font=("Segoe UI Semibold", 9),
                         bg=C["bar_bg"], fg=C["text"], padx=4)
        title.pack(side="left")

        # Version badge
        tk.Label(bar, text=f"v{APP_VERSION}", font=("Segoe UI", 7),
                 bg=C["border"], fg=C["text_dim"], padx=4, pady=1).pack(side="left", padx=4)

        self._sep(bar)

        # Stats
        self.stat_labels = {}
        for key, name in [("cpu", "CPU"), ("ram", "RAM"), ("gpu", "GPU")]:
            f = tk.Frame(bar, bg=C["bar_bg"])
            f.pack(side="left", padx=5)
            tk.Label(f, text=name, font=("Segoe UI", 8),
                     bg=C["bar_bg"], fg=C["text_dim"]).pack(side="left")
            v = tk.Label(f, text="--", font=("Segoe UI Semibold", 9),
                          bg=C["bar_bg"], fg=C["success"], width=5, anchor="w")
            v.pack(side="left", padx=(3, 0))
            self.stat_labels[key] = v

        self._sep(bar)

        # Boost button
        boost = tk.Label(bar, text="🚀 Boost", font=("Segoe UI Semibold", 9),
                         bg=C["accent_dim"], fg="#fff", padx=10, pady=2, cursor="hand2")
        boost.pack(side="left", padx=4, pady=4)
        boost.bind("<Button-1>", lambda e: self._threaded(self._do_boost))
        boost.bind("<Enter>", lambda e: boost.config(bg=C["accent"]))
        boost.bind("<Leave>", lambda e: boost.config(bg=C["accent_dim"]))

        # Update notification (hidden until update is found)
        self.update_label = tk.Label(bar, text="", font=("Segoe UI Semibold", 8),
                                     bg="#1a4a1a", fg=C["success"], padx=8, pady=2,
                                     cursor="hand2")
        self._update_info = None
        self._update_win = None  # Track update popup window

        # Close → tray
        close = tk.Label(bar, text="✕", font=("Segoe UI", 10, "bold"),
                         bg=C["bar_bg"], fg=C["text_dim"], padx=6, cursor="hand2")
        close.pack(side="right", padx=(2, 6))
        close.bind("<Button-1>", lambda e: self._to_tray())
        close.bind("<Enter>", lambda e: close.config(fg=C["danger"]))
        close.bind("<Leave>", lambda e: close.config(fg=C["text_dim"]))

        # Settings
        gear = tk.Label(bar, text="⚙", font=("Segoe UI Emoji", 10),
                        bg=C["bar_bg"], fg=C["text_dim"], padx=4, cursor="hand2")
        gear.pack(side="right", padx=2)
        gear.bind("<Button-1>", lambda e: self._show_settings())

        # Tips button
        tips_btn = tk.Label(bar, text="💡", font=("Segoe UI Emoji", 10),
                            bg=C["bar_bg"], fg=C["text_dim"], padx=4, cursor="hand2")
        tips_btn.pack(side="right", padx=2)
        tips_btn.bind("<Button-1>", lambda e: self._show_tips())
        tips_btn.bind("<Enter>", lambda e: tips_btn.config(fg=C["warning"]))
        tips_btn.bind("<Leave>", lambda e: tips_btn.config(fg=C["text_dim"]))

        # Status text
        self.bar_status = tk.Label(bar, text="", font=("Segoe UI", 8),
                                   bg=C["bar_bg"], fg=C["success"], padx=4)
        self.bar_status.pack(side="right", padx=(0, 8))

        # ── Result notification area (expands below bar after Boost) ──
        self.result_frame = tk.Frame(self.root, bg="#0d2818", height=36)
        self.result_frame.pack_propagate(False)
        tk.Frame(self.result_frame, bg=C["success"], width=3).pack(side="left", fill="y")
        self.result_label = tk.Label(
            self.result_frame, text="",
            font=("Segoe UI Semibold", 12),
            bg="#0d2818", fg=C["success"], padx=12
        )
        self.result_label.pack(side="left", fill="y")
        self._result_hide_id = None

        # Draggable
        for w in [bar, icon, title]:
            w.bind("<ButtonPress-1>", self._drag_start)
            w.bind("<B1-Motion>", self._drag_move)

    def _sep(self, parent):
        f = tk.Frame(parent, bg=C["bar_bg"], width=1, padx=4)
        f.pack(side="left", fill="y", pady=6)
        tk.Frame(f, bg=C["separator"], width=1).pack(fill="y", expand=True)

    # ══════════════════════════════════════════════════════
    #   DRAG / WIN32 / VISIBILITY
    # ══════════════════════════════════════════════════════
    def _toggle_visibility(self, event=None):
        if self.bar_visible:
            self._to_tray()
        else:
            self._from_tray()

    def _drag_start(self, e):
        self._dx = e.x_root - self.root.winfo_x()
        self._dy = e.y_root - self.root.winfo_y()

    def _drag_move(self, e):
        x, y = e.x_root - self._dx, e.y_root - self._dy
        h, w = self.root.winfo_height(), self.root.winfo_width()
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _get_hwnd(self):
        return int(self.root.wm_frame(), 16)

    def _apply_win32_flags(self):
        try:
            hwnd = self._get_hwnd()
            ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ex |= WS_EX_TOOLWINDOW | WS_EX_TOPMOST | WS_EX_NOACTIVATE
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex)
            self._force_topmost()
        except Exception:
            pass

    def _force_topmost(self):
        try:
            user32.SetWindowPos(
                self._get_hwnd(), HWND_TOPMOST, 0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW)
        except Exception:
            pass

    def _start_topmost_loop(self):
        def loop():
            self._force_topmost()
            self.topmost_after_id = self.root.after(1000, loop)
        self.topmost_after_id = self.root.after(1000, loop)

    # ══════════════════════════════════════════════════════
    #   ACTIONS
    # ══════════════════════════════════════════════════════
    def _status(self, text, color=None):
        color = color or C["text"]
        def update():
            self.bar_status.config(text=text, fg=color)
        self.root.after(0, update)

    def _threaded(self, fn):
        if fn:
            threading.Thread(target=fn, daemon=True).start()

    def _do_boost(self):
        self._status("🔄 Optimizing...", C["warning"])
        r = booster.boost_all()

        # Build summary from all optimizations
        parts = []
        cache_mb = r.get("cache_mb", 0)
        temp_mb = r.get("temp_mb", 0)
        total_mb = cache_mb + temp_mb
        if total_mb > 0.1:
            parts.append(f"🗑️ {total_mb:.0f} MB Cleared")

        ram_mb = r.get("ram_freed_mb", 0)
        if ram_mb > 1:
            parts.append(f"💾 {ram_mb:.0f} MB RAM Freed")

        if r.get("priority_set"):
            parts.append("⬆ POE2 Priority")

        if r.get("dns_flushed"):
            parts.append("🌐 DNS Flushed")

        if r.get("power_set"):
            parts.append("⚡ High Perf")

        if r.get("overlays_optimized", 0) > 0:
            parts.append(f"⬇️ {r['overlays_optimized']} Overlays")

        if parts:
            summary = "✅  " + "  ·  ".join(parts)
            self._show_boost_result(summary, C["success"])
        else:
            self._show_boost_result("✅  System is already optimized!", C["accent"])

    def _show_boost_result(self, text, color):
        """Show expanded result notification below the bar"""
        def update():
            if self._result_hide_id:
                self.root.after_cancel(self._result_hide_id)
            self.result_label.config(text=text, fg=color)
            self.result_frame.pack(fill="x", side="top")
            self.bar_status.config(text="")
            # Expand window height to show result
            w = self.root.winfo_width()
            x, y = self.root.winfo_x(), self.root.winfo_y()
            self.root.geometry(f"{w}x68+{x}+{y}")
            # Auto-collapse after 5 seconds
            self._result_hide_id = self.root.after(5000, self._hide_boost_result)
        self.root.after(0, update)

    def _hide_boost_result(self):
        """Collapse the result notification back to normal bar"""
        self.result_frame.pack_forget()
        w = self.root.winfo_width()
        x, y = self.root.winfo_x(), self.root.winfo_y()
        self.root.geometry(f"{w}x32+{x}+{y}")
        self.bar_status.config(text="")
        self._result_hide_id = None

    # ══════════════════════════════════════════════════════
    #   MONITOR
    # ══════════════════════════════════════════════════════
    def _start_monitor(self):
        def loop():
            while self.monitor_running:
                try:
                    cpu = psutil.cpu_percent(interval=0)
                    ram = psutil.virtual_memory().percent
                    gpu_t, vram = booster.get_gpu_stats()
                    self.stats = {"cpu": cpu, "ram": ram, "gpu_temp": gpu_t, "vram": vram}
                    self.root.after(0, lambda c=cpu, r=ram, g=gpu_t: self._update_bar(c, r, g))
                except Exception:
                    pass
                time.sleep(2)
        threading.Thread(target=loop, daemon=True).start()

    def _color(self, val, max_v=100):
        pct = (val / max_v) * 100
        return C["success"] if pct < 50 else C["warning"] if pct < 75 else C["danger"]

    def _update_bar(self, cpu, ram, gpu):
        try:
            self.stat_labels["cpu"].config(text=f"{cpu:.0f}%", fg=self._color(cpu))
            self.stat_labels["ram"].config(text=f"{ram:.0f}%", fg=self._color(ram))
            self.stat_labels["gpu"].config(text=f"{gpu:.0f}°C", fg=self._color(gpu, 90))
        except Exception:
            pass

    # ══════════════════════════════════════════════════════
    #   WIZARD / SETTINGS
    # ══════════════════════════════════════════════════════
    def _show_wizard(self):
        SetupWizard(self.root, booster, on_complete=None).show()

    def _show_settings(self):
        win = tk.Toplevel(self.root)
        win.title("Settings")
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.attributes("-alpha", 0.96)
        win.configure(bg=C["panel_bg"])

        w, h = 320, 240
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

        main = tk.Frame(win, bg=C["panel_bg"], padx=16, pady=12)
        main.pack(fill="both", expand=True)

        # Header
        hdr = tk.Frame(main, bg=C["panel_bg"])
        hdr.pack(fill="x", pady=(0, 10))
        tk.Label(hdr, text="⚙  Settings", font=("Segoe UI Semibold", 12),
                 bg=C["panel_bg"], fg=C["text"]).pack(side="left")
        close = tk.Label(hdr, text="✕", font=("Segoe UI", 12),
                         bg=C["panel_bg"], fg=C["text_dim"], cursor="hand2")
        close.pack(side="right")
        close.bind("<Button-1>", lambda e: win.destroy())

        tk.Frame(main, bg=C["border"], height=1).pack(fill="x", pady=(0, 10))

        # Auto-start toggle
        auto_var = tk.BooleanVar(value=self._is_autostart())
        auto_frame = tk.Frame(main, bg=C["card"], padx=10, pady=8)
        auto_frame.pack(fill="x", pady=3)
        auto_frame.config(highlightbackground=C["border"], highlightthickness=1)
        tk.Label(auto_frame, text="🚀 เปิดอัตโนมัติกับ Windows",
                 font=("Segoe UI", 9), bg=C["card"], fg=C["text"]).pack(side="left")
        tk.Checkbutton(auto_frame, variable=auto_var, bg=C["card"],
                       command=lambda: self._toggle_autostart(auto_var.get())
                       ).pack(side="right")

        # Hotkey info
        hk_frame = tk.Frame(main, bg=C["card"], padx=10, pady=8)
        hk_frame.pack(fill="x", pady=3)
        hk_frame.config(highlightbackground=C["border"], highlightthickness=1)
        tk.Label(hk_frame, text=f"⌨ Hotkey: {HOTKEY} (ซ่อน/แสดง แถบข้อมูล)",
                 font=("Segoe UI", 9), bg=C["card"], fg=C["text"]).pack(side="left")

        # About
        tk.Frame(main, bg=C["border"], height=1).pack(fill="x", pady=10)
        tk.Label(main, text=f"{APP_NAME} v{APP_VERSION}",
                 font=("Segoe UI", 9), bg=C["panel_bg"], fg=C["text_dim"]).pack()
        tk.Label(main, text="Made with ⚡ for POE2 players",
                 font=("Segoe UI", 8), bg=C["panel_bg"], fg=C["text_dim"]).pack()

    def _is_autostart(self):
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                 r"Software\Microsoft\Windows\CurrentVersion\Run")
            winreg.QueryValueEx(key, APP_NAME)
            return True
        except Exception:
            return False

    def _toggle_autostart(self, enable):
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                 r"Software\Microsoft\Windows\CurrentVersion\Run",
                                 0, winreg.KEY_SET_VALUE)
            if enable:
                exe = sys.executable
                script = os.path.abspath(__file__)
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, f'"{exe}" "{script}"')
            else:
                winreg.DeleteValue(key, APP_NAME)
        except Exception:
            pass

    # ══════════════════════════════════════════════════════
    #   AUTO-UPDATE
    # ══════════════════════════════════════════════════════
    def _check_update(self):
        """Check GitHub for new version in background"""
        def check():
            try:
                from config import APP_VERSION
                info = updater.check_for_update(APP_VERSION)
                if info:
                    self._update_info = info
                    self.root.after(0, lambda: self._show_update_available(info))
            except Exception:
                pass
        threading.Thread(target=check, daemon=True).start()

    def _show_update_available(self, info):
        """Show pulsing update badge on bar when new version is found"""
        version = info["version"]
        size_mb = info.get("size", 0) / (1024 * 1024)
        self.update_label.config(
            text=f"⬆ พบเวอร์ชันใหม่ {version} ({size_mb:.1f} MB)",
            bg="#1a4a1a", fg=C["success"]
        )
        self.update_label.pack(side="left", padx=4, pady=4)
        self.update_label.bind("<Button-1>", lambda e: self._show_update_dialog())
        self.update_label.bind("<Enter>",
                               lambda e: self.update_label.config(bg=C["success"], fg="#fff"))
        self.update_label.bind("<Leave>",
                               lambda e: self.update_label.config(bg="#1a4a1a", fg=C["success"]))
        # Pulse animation to draw attention
        self._pulse_update_badge()
        self._status(f"🔄 พบเวอร์ชันใหม่ {version}", C["accent"])

    def _pulse_update_badge(self):
        """Gentle pulse animation on update badge"""
        if not self._update_info or self._update_win:
            return
        try:
            cur = self.update_label.cget("bg")
            nxt = "#2a6a2a" if cur == "#1a4a1a" else "#1a4a1a"
            self.update_label.config(bg=nxt)
            self.root.after(1200, self._pulse_update_badge)
        except Exception:
            pass

    def _show_update_dialog(self):
        """Show a proper update popup dialog"""
        import webbrowser

        if self._update_win and self._update_win.winfo_exists():
            self._update_win.focus_force()
            return

        info = self._update_info
        if not info:
            return

        version = info["version"]
        size_mb = info.get("size", 0) / (1024 * 1024)
        notes = info.get("notes", "") or "ไม่มีรายละเอียดเพิ่มเติม"
        download_url = info.get("download_url", "")
        is_frozen = getattr(sys, "frozen", False)

        # ── Create dialog window ──
        win = tk.Toplevel(self.root)
        self._update_win = win
        win.title("อัปเดตใหม่!")
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg=C["panel_bg"])
        w, h = 420, 400
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

        # Border
        border = tk.Frame(win, bg=C["accent"], padx=2, pady=2)
        border.pack(fill="both", expand=True)
        main = tk.Frame(border, bg=C["panel_bg"], padx=16, pady=12)
        main.pack(fill="both", expand=True)

        # ── Header ──
        hdr = tk.Frame(main, bg=C["panel_bg"])
        hdr.pack(fill="x")
        tk.Label(hdr, text="🔄 พบเวอร์ชันใหม่!",
                 font=("Segoe UI Semibold", 14), bg=C["panel_bg"],
                 fg=C["accent"]).pack(side="left")
        close_btn = tk.Label(hdr, text="✕", font=("Segoe UI", 12, "bold"),
                             bg=C["panel_bg"], fg=C["text_dim"], cursor="hand2")
        close_btn.pack(side="right")
        close_btn.bind("<Button-1>", lambda e: win.destroy())
        close_btn.bind("<Enter>", lambda e: close_btn.config(fg=C["danger"]))
        close_btn.bind("<Leave>", lambda e: close_btn.config(fg=C["text_dim"]))

        tk.Frame(main, bg=C["border"], height=1).pack(fill="x", pady=8)

        # ── Version comparison ──
        ver_frame = tk.Frame(main, bg=C["card"], padx=12, pady=10)
        ver_frame.pack(fill="x", pady=(0, 8))
        ver_frame.config(highlightbackground=C["border"], highlightthickness=1)
        tk.Label(ver_frame, text=f"เวอร์ชันปัจจุบัน:   v{APP_VERSION}",
                 font=("Segoe UI", 10), bg=C["card"],
                 fg=C["text_dim"]).pack(anchor="w")
        tk.Label(ver_frame, text=f"เวอร์ชันใหม่:         {version}",
                 font=("Segoe UI Semibold", 10), bg=C["card"],
                 fg=C["success"]).pack(anchor="w")
        tk.Label(ver_frame, text=f"ขนาดไฟล์:            {size_mb:.1f} MB",
                 font=("Segoe UI", 10), bg=C["card"],
                 fg=C["text_dim"]).pack(anchor="w")

        # ── Release Notes ──
        tk.Label(main, text="📋 มีอะไรใหม่:",
                 font=("Segoe UI Semibold", 10), bg=C["panel_bg"],
                 fg=C["text"]).pack(anchor="w", pady=(4, 2))
        notes_frame = tk.Frame(main, bg=C["card"], padx=10, pady=8)
        notes_frame.pack(fill="both", expand=True, pady=(0, 8))
        notes_frame.config(highlightbackground=C["border"], highlightthickness=1)
        display_notes = notes[:500] + ("..." if len(notes) > 500 else "")
        notes_lbl = tk.Label(notes_frame, text=display_notes,
                             font=("Segoe UI", 9), bg=C["card"],
                             fg=C["text_dim"], wraplength=370, justify="left")
        notes_lbl.pack(anchor="w")

        # ── Progress bar (hidden initially) ──
        prog_frame = tk.Frame(main, bg=C["panel_bg"])
        prog_bar_bg = tk.Frame(prog_frame, bg=C["card"], height=22)
        prog_bar_bg.pack(fill="x")
        prog_bar_bg.pack_propagate(False)
        prog_fill = tk.Frame(prog_bar_bg, bg=C["accent"], width=0)
        prog_fill.place(x=0, y=0, relheight=1, width=0)
        prog_text = tk.Label(prog_bar_bg, text="0%",
                             font=("Segoe UI Semibold", 9), bg=C["card"],
                             fg="#fff")
        prog_text.place(relx=0.5, rely=0.5, anchor="center")
        status_lbl = tk.Label(prog_frame, text="",
                              font=("Segoe UI", 9), bg=C["panel_bg"],
                              fg=C["text_dim"])
        status_lbl.pack(anchor="w", pady=(4, 0))

        # ── Buttons ──
        btn_frame = tk.Frame(main, bg=C["panel_bg"])
        btn_frame.pack(fill="x", pady=(4, 0))

        def make_btn(parent, text, bg_color, fg_color, cmd):
            b = tk.Label(parent, text=text, font=("Segoe UI Semibold", 10),
                         bg=bg_color, fg=fg_color, padx=16, pady=6,
                         cursor="hand2")
            b.bind("<Button-1>", lambda e: cmd())
            hover_bg = C.get("accent", "#3388ff")
            b.bind("<Enter>", lambda e: b.config(bg=hover_bg))
            b.bind("<Leave>", lambda e: b.config(bg=bg_color))
            return b

        # ── Countdown restart animation ──
        def _countdown_restart(seconds_left, temp_path=None):
            """Show animated countdown then quit so batch script takes over"""
            if seconds_left <= 0:
                # Time to quit — batch script will replace exe and restart
                auto_btn.config(text="🔄 รีสตาร์ทตอนนี้!", bg=C["accent"])
                status_lbl.config(text="🔄 กำลังปิดแอปเพื่ออัปเดต...", fg=C["accent"])
                self.root.after(500, lambda: self._quit(getattr(self, "tray", None)))
                return

            dots = "." * (4 - seconds_left % 4)
            auto_btn.config(
                text=f"⏳ รีสตาร์ทใน {seconds_left} วินาที{dots}",
                bg=C["success"], fg="#fff"
            )
            status_lbl.config(
                text=f"✅ ดาวน์โหลดเสร็จแล้ว! แอปจะปิดและเปิดใหม่เป็นเวอร์ชัน {version} อัตโนมัติ",
                fg=C["success"]
            )
            # Pulse the progress bar green
            prog_fill.config(bg=C["success"])
            prog_fill.place(x=0, y=0, relheight=1, relwidth=1)
            prog_text.config(text=f"🔄 {seconds_left}s", bg=C["success"])

            self.root.after(1000, lambda: _countdown_restart(seconds_left - 1, temp_path))

        def do_auto_update():
            """Download + auto-restart (for .exe mode)"""
            # Disable buttons
            auto_btn.config(text="⏳ กำลังดาวน์โหลด...", bg=C["warning"], cursor="")
            auto_btn.unbind("<Button-1>")
            auto_btn.unbind("<Enter>")
            auto_btn.unbind("<Leave>")
            close_btn.unbind("<Button-1>")  # Prevent closing during download
            close_btn.config(fg=C["panel_bg"])
            manual_btn.pack_forget()
            prog_frame.pack(fill="x", pady=(0, 4), before=btn_frame)

            def callback(status, msg):
                def ui():
                    if status == "downloading":
                        try:
                            pct_str = msg.split("%")[0].split()[-1]
                            pct = int(pct_str)
                        except Exception:
                            pct = 0
                        bar_w = max(1, int(prog_bar_bg.winfo_width() * pct / 100))
                        prog_fill.place(x=0, y=0, relheight=1, width=bar_w)
                        prog_text.config(text=f"{pct}%", bg=C["accent"] if pct > 40 else C["card"])
                        status_lbl.config(text=msg, fg=C["warning"])
                        auto_btn.config(text=f"⏳ ดาวน์โหลด {pct}%")
                    elif status == "downloaded":
                        prog_fill.place(x=0, y=0, relheight=1, relwidth=1)
                        prog_text.config(text="100%", bg=C["accent"])
                        status_lbl.config(text=f"✅ {msg}", fg=C["success"])
                        auto_btn.config(text="✅ ดาวน์โหลดเสร็จ!", bg=C["success"])
                    elif status == "installing":
                        status_lbl.config(text=f"📦 {msg}", fg=C["accent"])
                    elif status == "restarting":
                        status_lbl.config(text=f"✅ {msg}", fg=C["success"])
                    elif status == "error":
                        status_lbl.config(text=f"❌ {msg}", fg=C["danger"])
                        auto_btn.config(text="❌ ล้มเหลว", bg=C["danger"])
                        close_btn.bind("<Button-1>", lambda e: win.destroy())
                        close_btn.config(fg=C["text_dim"])
                        _show_fallback_btn()
                self.root.after(0, ui)

            def run():
                # Step 1: Download
                temp_path = updater.download_to_temp(download_url, callback=callback)
                if not temp_path:
                    return

                # Step 2: Prepare batch script for self-replace
                ok = updater.apply_update_and_restart(temp_path, callback=callback)
                if ok:
                    # Step 3: Start countdown → quit
                    self.root.after(0, lambda: _countdown_restart(3, temp_path))
                else:
                    self.root.after(0, _show_fallback_btn)

            threading.Thread(target=run, daemon=True).start()

        def do_download_only():
            """Download-only mode for non-.exe (opens Downloads folder after)"""
            auto_btn.config(text="⏳ กำลังดาวน์โหลด...", bg=C["warning"], cursor="")
            auto_btn.unbind("<Button-1>")
            auto_btn.unbind("<Enter>")
            auto_btn.unbind("<Leave>")
            prog_frame.pack(fill="x", pady=(0, 4), before=btn_frame)

            def callback(status, msg):
                def ui():
                    if status == "downloading":
                        try:
                            pct_str = msg.split("%")[0].split()[-1]
                            pct = int(pct_str)
                        except Exception:
                            pct = 0
                        bar_w = max(1, int(prog_bar_bg.winfo_width() * pct / 100))
                        prog_fill.place(x=0, y=0, relheight=1, width=bar_w)
                        prog_text.config(text=f"{pct}%", bg=C["accent"] if pct > 40 else C["card"])
                        status_lbl.config(text=msg, fg=C["warning"])
                        auto_btn.config(text=f"⏳ ดาวน์โหลด {pct}%")
                    elif status == "downloaded":
                        prog_fill.place(x=0, y=0, relheight=1, relwidth=1)
                        prog_text.config(text="100%", bg=C["success"])
                    elif status == "error":
                        status_lbl.config(text=f"❌ {msg}", fg=C["danger"])
                        auto_btn.config(text="❌ ล้มเหลว", bg=C["danger"])
                self.root.after(0, ui)

            def run():
                dest = updater.download_to_temp(download_url, callback=callback)
                if dest:
                    def show_done():
                        auto_btn.config(text="✅ ดาวน์โหลดเสร็จ!", bg=C["success"])
                        status_lbl.config(
                            text=f"📂 ไฟล์อยู่ที่: {dest}\nเปิดโฟลเดอร์ให้แล้ว — นำไฟล์ไปแทนที่ตัวเก่าแล้วเปิดใหม่",
                            fg=C["success"]
                        )
                        # Open the folder containing the downloaded file
                        try:
                            folder = os.path.dirname(dest)
                            os.startfile(folder)
                        except Exception:
                            pass
                    self.root.after(0, show_done)

            threading.Thread(target=run, daemon=True).start()

        def do_open_browser():
            """Open GitHub release page in browser"""
            release_url = updater.get_release_url(version)
            try:
                webbrowser.open(release_url)
                status_lbl.config(text="🌐 เปิดหน้าดาวน์โหลดในเบราว์เซอร์แล้ว")
                prog_frame.pack(fill="x", pady=(0, 4), before=btn_frame)
            except Exception:
                status_lbl.config(text="❌ ไม่สามารถเปิดเบราว์เซอร์ได้")

        def _show_fallback_btn():
            """Show manual download button as fallback"""
            fb = tk.Label(btn_frame, text="🌐 ดาวน์โหลดจากเว็บแทน",
                          font=("Segoe UI Semibold", 10),
                          bg="#1a3a5a", fg="#6ab7ff", padx=16, pady=6,
                          cursor="hand2")
            fb.pack(side="left", fill="x", expand=True, padx=(0, 2), pady=(4, 0))
            fb.bind("<Button-1>", lambda e: do_open_browser())

        # ── Build buttons based on mode ──
        if is_frozen:
            auto_btn = make_btn(btn_frame, "⬆ อัปเดตและรีสตาร์ทอัตโนมัติ",
                                C["accent_dim"], "#fff", do_auto_update)
            auto_btn.pack(side="left", fill="x", expand=True, padx=(0, 4))
            manual_btn = make_btn(btn_frame, "🌐 เว็บ",
                                  C["card"], C["text_dim"], do_open_browser)
            manual_btn.pack(side="left", padx=(0, 0))
        else:
            auto_btn = make_btn(btn_frame, "⬇ ดาวน์โหลด .exe ใหม่",
                                C["accent_dim"], "#fff", do_download_only)
            auto_btn.pack(side="left", fill="x", expand=True, padx=(0, 4))
            manual_btn = make_btn(btn_frame, "🌐 เว็บ",
                                  C["card"], C["text_dim"], do_open_browser)
            manual_btn.pack(side="left", padx=(0, 0))

        # Draggable header
        for w_drag in [hdr]:
            w_drag.bind("<ButtonPress-1>", lambda e: setattr(win, '_dx', e.x_root - win.winfo_x()) or setattr(win, '_dy', e.y_root - win.winfo_y()))
            w_drag.bind("<B1-Motion>", lambda e: win.geometry(f"+{e.x_root - win._dx}+{e.y_root - win._dy}"))

    # ══════════════════════════════════════════════════════
    #   TIPS PANEL
    # ══════════════════════════════════════════════════════
    def _show_tips(self):
        """Show performance tips panel for POE2"""
        win = tk.Toplevel(self.root)
        win.title("Performance Tips")
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.attributes("-alpha", 0.96)
        win.configure(bg=C["panel_bg"])

        w, h = 460, 600
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

        # Scrollable canvas
        canvas = tk.Canvas(win, bg=C["panel_bg"], highlightthickness=0, bd=0)
        scrollbar = tk.Scrollbar(win, orient="vertical", command=canvas.yview)
        content = tk.Frame(canvas, bg=C["panel_bg"])

        content.bind("<Configure>",
                     lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        cf = canvas.create_window((0, 0), window=content, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(cf, width=e.width))

        def _mw(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        win.bind_all("<MouseWheel>", _mw)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        # ── Header ──
        hdr = tk.Frame(content, bg=C["panel_bg"])
        hdr.pack(fill="x", padx=16, pady=(12, 6))
        tk.Label(hdr, text="💡  คำแนะนำเพิ่มประสิทธิภาพ POE2",
                 font=("Segoe UI Semibold", 12),
                 bg=C["panel_bg"], fg=C["text"]).pack(side="left")
        close = tk.Label(hdr, text="✕", font=("Segoe UI", 12, "bold"),
                         bg=C["panel_bg"], fg=C["text_dim"], cursor="hand2")
        close.pack(side="right")
        close.bind("<Button-1>",
                   lambda e: (win.unbind_all("<MouseWheel>"), win.destroy()))
        close.bind("<Enter>", lambda e: close.config(fg=C["danger"]))
        close.bind("<Leave>", lambda e: close.config(fg=C["text_dim"]))

        tk.Frame(content, bg=C["border"], height=1).pack(fill="x", padx=16, pady=(0, 6))

        # Explanation banner
        banner = tk.Frame(content, bg="#1a1a0d", padx=12, pady=6)
        banner.pack(fill="x", padx=16, pady=(0, 6))
        banner.config(highlightbackground=C["warning"], highlightthickness=1)
        tk.Label(banner, text="⚠  CPU สูง + GPU ต่ำ = CPU เป็นคอขวด",
                 font=("Segoe UI Semibold", 9),
                 bg="#1a1a0d", fg=C["warning"]).pack(anchor="w")
        tk.Label(banner, text="แก้โดยลดงาน CPU ในเกมตามคำแนะนำด้านล่าง",
                 font=("Segoe UI", 8),
                 bg="#1a1a0d", fg=C["text_dim"]).pack(anchor="w")

        # ── Section: Auto-Optimize Config ──
        self._tip_heading(content, "⚡  ปรับแต่งไฟล์ Config อัตโนมัติ")
        
        cfg_path = booster.get_poe2_config_path()
        
        opt_frame = tk.Frame(content, bg=C["card"], padx=12, pady=10)
        opt_frame.pack(fill="x", padx=16, pady=4)
        opt_frame.config(highlightbackground=C["border"], highlightthickness=1)
        
        if cfg_path:
            is_opt, _ = booster.check_poe2_config_status(cfg_path)
            
            status_text = "สถานะ: ปรับแต่งแล้ว (ดีมาก! ✅)" if is_opt else "สถานะ: ยังไม่ได้ปรับแต่งตามสูตรแอดมิน ⚠️"
            status_color = C["success"] if is_opt else C["warning"]
            
            status_lbl = tk.Label(opt_frame, text=status_text, font=("Segoe UI Semibold", 9),
                                  bg=C["card"], fg=status_color)
            status_lbl.pack(anchor="w")
            
            path_lbl = tk.Label(opt_frame, text=f"ไฟล์: {os.path.basename(cfg_path)}", font=("Segoe UI", 8),
                                 bg=C["card"], fg=C["text_dim"])
            path_lbl.pack(anchor="w", pady=(2, 6))
            
            btn_frame = tk.Frame(opt_frame, bg=C["card"])
            btn_frame.pack(fill="x", pady=(4, 0))
            
            # Auto-Apply Button
            apply_btn = tk.Label(btn_frame, text="⚡ ใช้ค่าแนะนำของแอดมิน", font=("Segoe UI Semibold", 9),
                                 bg=C["accent_dim"], fg="#ffffff", padx=12, pady=6, cursor="hand2")
            apply_btn.pack(side="left", padx=(0, 8))
            
            # Revert Button (only if backup exists)
            has_backup = os.path.exists(cfg_path + ".backup")
            revert_btn = tk.Label(btn_frame, text="⏪ คืนค่าเดิม", font=("Segoe UI", 9),
                                  bg=C["border"], fg=C["text"], padx=10, pady=6, cursor="hand2")
            if has_backup:
                revert_btn.pack(side="left")
                
            msg_lbl = tk.Label(opt_frame, text="", font=("Segoe UI", 8), bg=C["card"], fg=C["success"])
            msg_lbl.pack(anchor="w", pady=(6, 0))
            
            def do_apply(e):
                success, msg = booster.optimize_poe2_config(cfg_path)
                if success:
                    status_lbl.config(text="สถานะ: ปรับแต่งแล้ว (ดีมาก! ✅)", fg=C["success"])
                    revert_btn.pack(side="left")
                    msg_lbl.config(text="⚡ สำรองไฟล์เดิมและปรับแต่งสำเร็จ! กรุณารีสตาร์ทเกมหากเปิดอยู่", fg=C["success"])
                else:
                    msg_lbl.config(text=f"❌ {msg}", fg=C["danger"])
                    
            def do_revert(e):
                success, msg = booster.revert_poe2_config(cfg_path)
                if success:
                    status_lbl.config(text="สถานะ: ยังไม่ได้ปรับแต่งตามสูตรแอดมิน ⚠️", fg=C["warning"])
                    revert_btn.pack_forget()
                    msg_lbl.config(text="⏪ คืนค่าการตั้งค่าเดิมเรียบร้อยแล้ว!", fg=C["success"])
                else:
                    msg_lbl.config(text=f"❌ {msg}", fg=C["danger"])
                    
            apply_btn.bind("<Button-1>", do_apply)
            apply_btn.bind("<Enter>", lambda e: apply_btn.config(bg=C["accent"]))
            apply_btn.bind("<Leave>", lambda e: apply_btn.config(bg=C["accent_dim"]))
            
            revert_btn.bind("<Button-1>", do_revert)
            revert_btn.bind("<Enter>", lambda e: revert_btn.config(bg=C["card_hover"]))
            revert_btn.bind("<Leave>", lambda e: revert_btn.config(bg=C["border"]))
            
        else:
            tk.Label(opt_frame, text="❌ ไม่พบไฟล์ poe2_production_Config.ini", font=("Segoe UI Semibold", 9),
                     bg=C["card"], fg=C["danger"]).pack(anchor="w")
            tk.Label(opt_frame, text="กรุณาเข้าเล่นเกม Path of Exile 2 อย่างน้อย 1 ครั้ง เพื่อให้ระบบสร้างไฟล์",
                     font=("Segoe UI", 8), bg=C["card"], fg=C["text_dim"]).pack(anchor="w", pady=(2, 0))

        # ── Section: Overlay Conflicts ──
        conflicts = booster.scan_overlay_conflicts()
        if conflicts:
            self._tip_heading(content, "⚠️  พบแอป Overlay ที่อาจทำให้เกมกระตุก")
            
            conflict_frame = tk.Frame(content, bg=C["card"], padx=12, pady=10)
            conflict_frame.pack(fill="x", padx=16, pady=4)
            conflict_frame.config(highlightbackground=C["warning"], highlightthickness=1)
            
            info_lbl = tk.Label(conflict_frame, text="ตรวจพบแอป Overlay รันอยู่เบื้องหลัง:",
                                font=("Segoe UI Semibold", 9), bg=C["card"], fg=C["warning"])
            info_lbl.pack(anchor="w", pady=(0, 4))
            
            for c in conflicts:
                app_name = c["display_name"]
                tip_text = c["tip"]
                
                app_lbl = tk.Label(conflict_frame, text=f"• {app_name}", font=("Segoe UI Semibold", 9),
                                   bg=C["card"], fg=C["text"])
                app_lbl.pack(anchor="w")
                
                tip_lbl = tk.Label(conflict_frame, text=tip_text, font=("Segoe UI", 8),
                                   bg=C["card"], fg=C["text_dim"], wraplength=400, justify="left")
                tip_lbl.pack(anchor="w", padx=12, pady=(0, 4))
                
            btn_opt = tk.Label(conflict_frame, text="⚡ ลดภาระ CPU ของแอปเหล่านี้", font=("Segoe UI Semibold", 9),
                               bg=C["accent_dim"], fg="#ffffff", padx=12, pady=6, cursor="hand2")
            btn_opt.pack(anchor="w", pady=(4, 0))
            
            opt_msg = tk.Label(conflict_frame, text="", font=("Segoe UI", 8), bg=C["card"], fg=C["success"])
            opt_msg.pack(anchor="w", pady=(4, 0))
            
            def do_opt_overlays(e):
                count = booster.optimize_overlay_priorities()
                if count > 0:
                    opt_msg.config(text=f"✅ ปรับลด CPU ของแอป Overlay {count} รายการ เรียบร้อย!", fg=C["success"])
                else:
                    opt_msg.config(text="✅ ปรับลด CPU เรียบร้อยแล้ว หรือไม่พบแอปเพิ่ม", fg=C["success"])
                    
            btn_opt.bind("<Button-1>", do_opt_overlays)
            btn_opt.bind("<Enter>", lambda e: btn_opt.config(bg=C["accent"]))
            btn_opt.bind("<Leave>", lambda e: btn_opt.config(bg=C["accent_dim"]))

        # ── Section: In-game ──
        self._tip_heading(content, "🎮  คำแนะนำการตั้งค่าในเกมตามสูตรแอดมิน")
        for s, d in [
            ("Renderer", "ใช้ Vulkan (ลด CPU คอขวดอย่างเห็นได้ชัด)"),
            ("Shadow Detail", "Low (ช่วยลดภาระ CPU ได้มากที่สุด)"),
            ("Light Quality", "Low (ลดภาระการคำนวณแสงในด่าน)"),
            ("Global Illum.", "Off (ปิดแสงเงาสะท้อนระดับสูงเพื่อความลื่น)"),
            ("Texture Quality", "Low (ช่วยประหยัด VRAM และแรมระบบ)"),
            ("Dynamic Res.", "เปิดใช้งาน (ช่วยรักษาเฟรมเรตให้สม่ำเสมอ)"),
            ("Sound Channels", "Low (ลดภาระ CPU ด้านเสียงตอนมอนเยอะ)"),
            ("Mute BG Sounds", "ปิดเสียงเพลง/รอบข้างใน config (เซฟ CPU มหาศาล)"),
            ("Multithreading", "เปิดใช้งาน (เพื่อดึงพลัง CPU ออกมาทุกคอร์)"),
        ]:
            self._tip_row(content, s, d)

        # ── Section: System ──
        self._tip_heading(content, "🖥️  ปรับในระบบ")
        for s, d in [
            ("GPU Driver", "อัปเดตล่าสุด (มี POE2 optimization)"),
            ("Game Bar", "Settings → Gaming → Off (กิน CPU เงียบๆ)"),
            ("Intel 12th+", "ตั้ง Affinity ใช้เฉพาะ P-Core"),
        ]:
            self._tip_row(content, s, d)

        # ── Section: Special tip ──
        self._tip_heading(content, "🧠  เคล็ดลับ: Warm Up Shader Cache")
        tip = tk.Frame(content, bg="#0d1a0d", padx=12, pady=8)
        tip.pack(fill="x", padx=16, pady=2)
        tip.config(highlightbackground=C["success"], highlightthickness=1)
        tk.Label(tip, text="หลังกด Boost ล้าง cache → เข้าเกมเดินในเมืองก่อน 2-3 นาที",
                 font=("Segoe UI Semibold", 9),
                 bg="#0d1a0d", fg=C["success"],
                 wraplength=400, justify="left").pack(anchor="w")
        tk.Label(tip, text="ให้เกม compile shader ใหม่ให้ครบ จะลื่นขึ้นมาก!",
                 font=("Segoe UI", 8),
                 bg="#0d1a0d", fg=C["text_dim"],
                 wraplength=400, justify="left").pack(anchor="w", pady=(2, 0))

        # Footer
        tk.Frame(content, bg=C["border"], height=1).pack(fill="x", padx=16, pady=(10, 6))
        tk.Label(content, text="💚 กด 🚀 Boost ก่อนเล่นทุกครั้งเพื่อผลลัพธ์ที่ดีที่สุด!",
                 font=("Segoe UI Semibold", 9),
                 bg=C["panel_bg"], fg=C["success"]).pack(pady=(0, 12))

    def _tip_heading(self, parent, title):
        """Section heading for tips panel"""
        tk.Label(parent, text=title, font=("Segoe UI Semibold", 10),
                 bg=C["panel_bg"], fg=C["accent"]).pack(anchor="w", padx=16, pady=(8, 3))

    def _tip_row(self, parent, setting, desc):
        """Single tip row with setting name and description"""
        f = tk.Frame(parent, bg=C["card"], padx=10, pady=4)
        f.pack(fill="x", padx=16, pady=1)
        f.config(highlightbackground=C["border"], highlightthickness=1)
        tk.Label(f, text=f"▸ {setting}", font=("Segoe UI Semibold", 9),
                 bg=C["card"], fg=C["text"], width=14, anchor="w").pack(side="left")
        tk.Label(f, text=desc, font=("Segoe UI", 8),
                 bg=C["card"], fg=C["text_dim"], anchor="w").pack(side="left", padx=(4, 0))

    # ══════════════════════════════════════════════════════
    #   TRAY / HOTKEY / RUN
    # ══════════════════════════════════════════════════════
    def _to_tray(self):
        self.root.withdraw()
        self.bar_visible = False

    def _from_tray(self):
        self.root.deiconify()
        self._force_topmost()
        self.bar_visible = True

    def _register_hotkey(self):
        keyboard.add_hotkey(HOTKEY, lambda: self.root.after(0, self._toggle_visibility),
                            suppress=False)

    def _start_tray(self):
        if not pystray:
            return
        def go():
            img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            d.ellipse([4, 4, 60, 60], fill="#1f6feb")
            d.polygon([(32, 8), (18, 34), (30, 34), (28, 56), (46, 28), (34, 28)],
                      fill="#ffffff")
            menu = pystray.Menu(
                pystray.MenuItem("Show/Hide Overlay", lambda i, _: self.root.after(0, self._toggle_visibility),
                                 default=True),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("🚀 Boost (Clear Cache)", lambda i, _: self._threaded(self._do_boost)),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Quit", lambda i, _: self._quit(i)),
            )
            self.tray = pystray.Icon(APP_NAME, img, APP_NAME, menu)
            self.tray.run()
        threading.Thread(target=go, daemon=True).start()

    def _quit(self, icon=None):
        self.monitor_running = False
        if icon:
            icon.stop()
        self.root.after(0, self.root.destroy)

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW",
                           lambda: self._quit(getattr(self, 'tray', None)))
        print(f"{APP_NAME} v{APP_VERSION} is running!")
        print(f"Hotkey: {HOTKEY} | Bar stays on top of game")
        self.root.mainloop()


if __name__ == "__main__":
    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        is_admin = False
    if not is_admin:
        print("Tip: Run as Administrator for best results")

    app = POE2BoosterApp()
    app.run()


