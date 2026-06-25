"""
POE2 Booster Overlay — Main Application
========================================
Production version with:
- Persistent top bar (like POE Overlay)
- Expandable panel with boost actions
- First-time setup wizard
- System monitor with Real-time Ping
- Auto-start option
- Unified Bento Grid Dashboard with Tabs
- Auto-Boost, Smart Cache Clear, OBS Streamer Mode, Custom Themes
- Win32 API overlay display affinity protection
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

import config
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
        self.stats = {"cpu": 0, "ram": 0, "gpu_temp": 0, "vram": 0, "ping": -1}
        self.topmost_after_id = None
        self._update_info = None
        self._update_win = None
        self._dash_win = None
        self._result_hide_id = None
        self._game_was_running = False

        # Load Pro configuration settings
        cfg = config.load_config()
        self.pro_auto_boost = cfg.get("auto_boost", False)
        self.pro_auto_clean = cfg.get("auto_clean", False)
        self.pro_streamer_mode = cfg.get("streamer_mode", False)

        # Build UI & start loops
        self._build_bar()
        self._start_monitor()
        self._start_pro_services()
        self._apply_streamer_mode()
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
        c = config.COLORS
        self.root = tk.Tk()
        self.root.title(config.APP_NAME)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.93)
        self.root.configure(bg=c["bar_bg"])

        bar_w, bar_h = 780, 32
        sw = self.root.winfo_screenwidth()
        x = (sw - bar_w) // 2

        self.root.geometry(f"{bar_w}x{bar_h}+{x}+0")
        self.root.update_idletasks()
        self._apply_win32_flags()

        bar = tk.Frame(self.root, bg=c["bar_bg"], height=bar_h)
        bar.pack(fill="x", side="top")
        bar.pack_propagate(False)
        self.bar = bar

        # Icon
        self.bar_icon = tk.Label(bar, text="⚡", font=("Segoe UI Emoji", 11),
                        bg=c["bar_bg"], fg=c["accent"], padx=8)
        self.bar_icon.pack(side="left")

        # Title
        self.bar_title = tk.Label(bar, text=config.APP_NAME, font=("Segoe UI Semibold", 9),
                         bg=c["bar_bg"], fg=c["text"], padx=4)
        self.bar_title.pack(side="left")

        # Version badge
        self.bar_ver = tk.Label(bar, text=f"v{config.APP_VERSION}", font=("Segoe UI", 7),
                  bg=c["border"], fg=c["text_dim"], padx=4, pady=1)
        self.bar_ver.pack(side="left", padx=4)

        self._sep(bar)

        # Stats Labels (CPU, RAM, GPU)
        self.stat_labels = {}
        for key, name in [("cpu", "CPU"), ("ram", "RAM"), ("gpu", "GPU")]:
            f = tk.Frame(bar, bg=c["bar_bg"])
            f.pack(side="left", padx=5)
            tk.Label(f, text=name, font=("Segoe UI", 8),
                     bg=c["bar_bg"], fg=c["text_dim"]).pack(side="left")
            v = tk.Label(f, text="--", font=("Segoe UI Semibold", 9),
                          bg=c["bar_bg"], fg=c["success"], width=5, anchor="w")
            v.pack(side="left", padx=(3, 0))
            self.stat_labels[key] = v

        # Real-time Network Ping Stats
        f_ping = tk.Frame(bar, bg=c["bar_bg"])
        f_ping.pack(side="left", padx=5)
        tk.Label(f_ping, text="PING", font=("Segoe UI", 8),
                 bg=c["bar_bg"], fg=c["text_dim"]).pack(side="left")
        v_ping = tk.Label(f_ping, text="--", font=("Segoe UI Semibold", 9),
                           bg=c["bar_bg"], fg=c["success"], width=7, anchor="w")
        v_ping.pack(side="left", padx=(3, 0))
        self.stat_labels["ping"] = v_ping

        self._sep(bar)

        # Boost button
        self.bar_boost = tk.Label(bar, text="🚀 Boost", font=("Segoe UI Semibold", 9),
                         bg=c["accent_dim"], fg="#fff", padx=10, pady=2, cursor="hand2")
        self.bar_boost.pack(side="left", padx=4, pady=4)
        self.bar_boost.bind("<Button-1>", lambda e: self._threaded(self._do_boost))
        self.bar_boost.bind("<Enter>", lambda e: self.bar_boost.config(bg=c["accent"]))
        self.bar_boost.bind("<Leave>", lambda e: self.bar_boost.config(bg=c["accent_dim"]))

        # Update notification (hidden until update is found)
        self.update_label = tk.Label(bar, text="", font=("Segoe UI Semibold", 8),
                                     bg="#1a4a1a", fg=c["success"], padx=8, pady=2,
                                     cursor="hand2")

        # Close → tray
        self.bar_close = tk.Label(bar, text="✕", font=("Segoe UI", 10, "bold"),
                         bg=c["bar_bg"], fg=c["text_dim"], padx=6, cursor="hand2")
        self.bar_close.pack(side="right", padx=(2, 6))
        self.bar_close.bind("<Button-1>", lambda e: self._to_tray())
        self.bar_close.bind("<Enter>", lambda e: self.bar_close.config(fg=c["danger"]))
        self.bar_close.bind("<Leave>", lambda e: self.bar_close.config(fg=c["text_dim"]))

        # Dashboard / settings gear button
        self.bar_gear = tk.Label(bar, text="⚙", font=("Segoe UI Emoji", 10),
                        bg=c["bar_bg"], fg=c["text_dim"], padx=4, cursor="hand2")
        self.bar_gear.pack(side="right", padx=2)
        self.bar_gear.bind("<Button-1>", lambda e: self._show_dashboard(tab="settings"))

        # Dashboard / tips button
        self.bar_dash = tk.Label(bar, text="📊", font=("Segoe UI Emoji", 10),
                            bg=c["bar_bg"], fg=c["text_dim"], padx=4, cursor="hand2")
        self.bar_dash.pack(side="right", padx=2)
        self.bar_dash.bind("<Button-1>", lambda e: self._show_dashboard(tab="status"))
        self.bar_dash.bind("<Enter>", lambda e: self.bar_dash.config(fg=c["accent"]))
        self.bar_dash.bind("<Leave>", lambda e: self.bar_dash.config(fg=c["text_dim"]))

        # Status text
        self.bar_status = tk.Label(bar, text="", font=("Segoe UI", 8),
                                   bg=c["bar_bg"], fg=c["success"], padx=4)
        self.bar_status.pack(side="right", padx=(0, 8))

        # ── Result notification area (expands below bar after Boost) ──
        self.result_frame = tk.Frame(self.root, bg="#0d2818", height=36)
        self.result_frame.pack_propagate(False)
        self.result_border = tk.Frame(self.result_frame, bg=c["success"], width=3)
        self.result_border.pack(side="left", fill="y")
        self.result_label = tk.Label(
            self.result_frame, text="",
            font=("Segoe UI Semibold", 10),
            bg="#0d2818", fg=c["success"], padx=12
        )
        self.result_label.pack(side="left", fill="y")

        # Draggable
        for w in [bar, self.bar_icon, self.bar_title]:
            w.bind("<ButtonPress-1>", self._drag_start)
            w.bind("<B1-Motion>", self._drag_move)

    def _sep(self, parent):
        c = config.COLORS
        f = tk.Frame(parent, bg=c["bar_bg"], width=1, padx=4)
        f.pack(side="left", fill="y", pady=6)
        tk.Frame(f, bg=c["separator"], width=1).pack(fill="y", expand=True)

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

    def _protect_window(self, win):
        """Hides window from screen capture if Streamer Mode is enabled"""
        if self.pro_streamer_mode:
            try:
                win.update_idletasks()
                hwnd = int(win.wm_frame(), 16)
                ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 0x00000011)  # WDA_EXCLUDEFROMCAPTURE
            except Exception:
                pass

    def _apply_streamer_mode(self):
        """Apply OBS Streamer Mode display affinity to the main bar window"""
        hwnd = self._get_hwnd()
        try:
            if self.pro_streamer_mode:
                ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 0x00000011)
            else:
                ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 0)
        except Exception:
            pass

    # ══════════════════════════════════════════════════════
    #   BACKGROUND SERVICES (MONITOR, AUTO-BOOST, SMART-CLEAN)
    # ══════════════════════════════════════════════════════
    def _start_monitor(self):
        def loop():
            ping_counter = 0
            while self.monitor_running:
                try:
                    cpu = psutil.cpu_percent(interval=0)
                    ram = psutil.virtual_memory().percent
                    gpu_t, vram = booster.get_gpu_stats()
                    
                    # Update ping every 4 seconds (2 cycles)
                    ping_counter += 1
                    if ping_counter >= 2:
                        ping_counter = 0
                        ping_val = booster.check_network_ping()
                        self.stats["ping"] = ping_val
                        
                    self.stats.update({"cpu": cpu, "ram": ram, "gpu_temp": gpu_t, "vram": vram})
                    self.root.after(0, self._update_bar_ui)
                except Exception:
                    pass
                time.sleep(2)
        threading.Thread(target=loop, daemon=True).start()

    def _color(self, val, max_v=100):
        pct = (val / max_v) * 100
        c = config.COLORS
        return c["success"] if pct < 50 else c["warning"] if pct < 75 else c["danger"]

    def _color_ping(self, val):
        c = config.COLORS
        if val < 60:
            return c["success"]
        elif val < 150:
            return c["warning"]
        return c["danger"]

    def _update_bar_ui(self):
        try:
            c = config.COLORS
            cpu = self.stats.get("cpu", 0)
            ram = self.stats.get("ram", 0)
            gpu = self.stats.get("gpu_temp", 0)
            ping = self.stats.get("ping", -1)
            
            self.stat_labels["cpu"].config(text=f"{cpu:.0f}%", fg=self._color(cpu))
            self.stat_labels["ram"].config(text=f"{ram:.0f}%", fg=self._color(ram))
            self.stat_labels["gpu"].config(text=f"{gpu:.0f}°C", fg=self._color(gpu, 90))
            
            if ping >= 998:
                self.stat_labels["ping"].config(text="Offline", fg=c["danger"])
            elif ping >= 0:
                self.stat_labels["ping"].config(text=f"{ping:.0f}ms", fg=self._color_ping(ping))
            else:
                self.stat_labels["ping"].config(text="--", fg=c["text_dim"])
                
            # If dashboard is currently open, refresh the dashboard values
            if self._dash_win and self._dash_win.winfo_exists():
                self._update_dash_labels()
        except Exception:
            pass

    def _start_pro_services(self):
        """Launch auto-boost detector and smart cache clean timers"""
        def auto_boost_loop():
            while self.monitor_running:
                if self.pro_auto_boost:
                    running = booster.is_poe2_running()
                    if running and not self._game_was_running:
                        self._game_was_running = True
                        self._status("🔄 Auto-Boosting...", config.COLORS["warning"])
                        self._do_boost()
                        self._status("⚡ Auto-Boosted!", config.COLORS["success"])
                        self.root.after(3000, lambda: self._status(""))
                    elif not running:
                        self._game_was_running = False
                time.sleep(5)

        def auto_clean_loop():
            while self.monitor_running:
                if self.pro_auto_clean:
                    try:
                        size = booster.get_shader_cache_size_mb()
                        if size > 500:  # 500MB Threshold
                            cleared = booster.clear_shader_cache()
                            if cleared > 0:
                                self._status(f"🧹 Auto-Cleaned {cleared:.0f}MB Cache", config.COLORS["success"])
                                self.root.after(4000, lambda: self._status(""))
                    except Exception:
                        pass
                time.sleep(300)  # Check every 5 minutes

        threading.Thread(target=auto_boost_loop, daemon=True).start()
        threading.Thread(target=auto_clean_loop, daemon=True).start()

    def _refresh_theme(self):
        """Apply colors of currently active theme to open bar components"""
        c = config.COLORS
        try:
            self.root.configure(bg=c["bar_bg"])
            self.bar.configure(bg=c["bar_bg"])
            self.bar_icon.config(bg=c["bar_bg"], fg=c["accent"])
            self.bar_title.config(bg=c["bar_bg"], fg=c["text"])
            self.bar_ver.config(bg=c["border"], fg=c["text_dim"])
            self.bar_boost.config(bg=c["accent_dim"])
            self.bar_close.config(bg=c["bar_bg"], fg=c["text_dim"])
            self.bar_gear.config(bg=c["bar_bg"], fg=c["text_dim"])
            self.bar_dash.config(bg=c["bar_bg"], fg=c["text_dim"])
            self.bar_status.config(bg=c["bar_bg"])
            
            # Recolor result frame
            self.result_frame.config(bg="#0d2818")
            self.result_border.config(bg=c["success"])
            self.result_label.config(bg="#0d2818", fg=c["success"])
            
            # Update labels static texts colors
            for f in self.bar.winfo_children():
                if isinstance(f, tk.Frame) and len(f.winfo_children()) == 2:
                    # It's a stats frame
                    lbl_title = f.winfo_children()[0]
                    lbl_val = f.winfo_children()[1]
                    lbl_title.config(bg=c["bar_bg"], fg=c["text_dim"])
                    lbl_val.config(bg=c["bar_bg"])
                    
            self._update_bar_ui()
        except Exception:
            pass

    # ══════════════════════════════════════════════════════
    #   ACTIONS (BOOST & AUTO-UPDATE)
    # ══════════════════════════════════════════════════════
    def _status(self, text, color=None):
        c = config.COLORS
        color = color or c["text"]
        def update():
            self.bar_status.config(text=text, fg=color)
        self.root.after(0, update)

    def _threaded(self, fn):
        if fn:
            threading.Thread(target=fn, daemon=True).start()

    def _do_boost(self):
        c = config.COLORS
        self._status("🔄 Optimizing...", c["warning"])
        r = booster.boost_all()

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
            self._show_boost_result(summary, c["success"])
        else:
            self._show_boost_result("✅  System is already optimized!", c["accent"])

        # If Dashboard is open on status page, reload
        if self._dash_win and self._dash_win.winfo_exists():
            self.root.after(500, lambda: self._show_dashboard(tab="status"))

        # ── Auto-Update after Boost ──
        # If an update was detected, automatically download & install it
        if self._update_info and not getattr(self, '_update_in_progress', False):
            self.root.after(2500, lambda: self._silent_auto_update())

    def _silent_auto_update(self):
        """Headless auto-update: download, install, and restart without user interaction.
        Shows progress on the overlay result bar so the user can see what's happening."""
        if getattr(self, '_update_in_progress', False):
            return
        self._update_in_progress = True

        info = self._update_info
        if not info:
            self._update_in_progress = False
            return

        version = info["version"]
        download_url = info.get("download_url", "")
        if not download_url:
            self._update_in_progress = False
            return

        c = config.COLORS
        is_frozen = getattr(sys, "frozen", False)

        # Show starting message on the bar
        self._show_boost_result(f"⬆ พบ {version} — กำลังดาวน์โหลดอัปเดตอัตโนมัติ...", c["accent"])
        # Cancel auto-hide so the result bar stays visible during update
        if self._result_hide_id:
            self.root.after_cancel(self._result_hide_id)
            self._result_hide_id = None

        def callback(status, msg):
            def ui():
                try:
                    if status == "downloading":
                        try:
                            pct_str = msg.split("%")[0].split()[-1]
                            pct = int(pct_str)
                        except Exception:
                            pct = 0
                        self.result_label.config(
                            text=f"⬆ อัปเดต {version}:  ดาวน์โหลด {pct}%",
                            fg=c["warning"]
                        )
                    elif status == "downloaded":
                        self.result_label.config(
                            text=f"✅ ดาวน์โหลด {version} เสร็จ — กำลังติดตั้ง...",
                            fg=c["success"]
                        )
                    elif status == "installing":
                        self.result_label.config(
                            text=f"📦 ติดตั้ง {version}...",
                            fg=c["accent"]
                        )
                    elif status == "error":
                        self.result_label.config(
                            text=f"❌ อัปเดตล้มเหลว: {msg}",
                            fg=c["danger"]
                        )
                        self._update_in_progress = False
                        self._result_hide_id = self.root.after(8000, self._hide_boost_result)
                except Exception:
                    pass
            self.root.after(0, ui)

        def countdown(sec):
            """Countdown on the result bar then quit to restart"""
            try:
                if sec <= 0:
                    self.result_label.config(
                        text=f"🔄 กำลังรีสตาร์ทเป็น {version}...",
                        fg=c["accent"]
                    )
                    self.root.after(500, lambda: self._quit(getattr(self, 'tray', None)))
                    return
                self.result_label.config(
                    text=f"✅ อัปเดตเสร็จ! รีสตาร์ทอัตโนมัติใน {sec} วินาที...",
                    fg=c["success"]
                )
                self.root.after(1000, lambda: countdown(sec - 1))
            except Exception:
                pass

        def run_update():
            temp_path = updater.download_to_temp(download_url, callback=callback)
            if not temp_path:
                self._update_in_progress = False
                return

            if is_frozen:
                # .exe mode: apply update and restart
                ok = updater.apply_update_and_restart(temp_path, callback=callback)
                if ok:
                    self.root.after(0, lambda: countdown(3))
                else:
                    self._update_in_progress = False
            else:
                # Dev mode: just download, show location, don't auto-restart
                def show_done():
                    self.result_label.config(
                        text=f"✅ ดาวน์โหลด {version} เสร็จ — ไฟล์อยู่ที่: {os.path.basename(temp_path)}",
                        fg=c["success"]
                    )
                    self._update_in_progress = False
                    self._result_hide_id = self.root.after(10000, self._hide_boost_result)
                    try:
                        os.startfile(os.path.dirname(temp_path))
                    except Exception:
                        pass
                self.root.after(0, show_done)

        threading.Thread(target=run_update, daemon=True).start()

    def _show_boost_result(self, text, color):
        def update():
            if self._result_hide_id:
                self.root.after_cancel(self._result_hide_id)
            self.result_label.config(text=text, fg=color)
            self.result_frame.pack(fill="x", side="top")
            self.bar_status.config(text="")
            # Expand overlay window height
            w = self.root.winfo_width()
            x, y = self.root.winfo_x(), self.root.winfo_y()
            self.root.geometry(f"{w}x68+{x}+{y}")
            self._result_hide_id = self.root.after(5000, self._hide_boost_result)
        self.root.after(0, update)

    def _hide_boost_result(self):
        self.result_frame.pack_forget()
        w = self.root.winfo_width()
        x, y = self.root.winfo_x(), self.root.winfo_y()
        self.root.geometry(f"{w}x32+{x}+{y}")
        self.bar_status.config(text="")
        self._result_hide_id = None

    # ══════════════════════════════════════════════════════
    #   UNIFIED BENTO DASHBOARD UI
    # ══════════════════════════════════════════════════════
    def _show_dashboard(self, tab="status"):
        """Show the unified Premium Bento Grid Dashboard window"""
        c = config.COLORS

        # If already open, raise to focus and switch tab
        if self._dash_win and self._dash_win.winfo_exists():
            self._dash_win.focus_force()
            self._switch_dash_tab(tab)
            return

        win = tk.Toplevel(self.root)
        self._dash_win = win
        win.title("POE2 Booster — Dashboard")
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.attributes("-alpha", 0.96)
        win.configure(bg=c["panel_bg"])

        w, h = 680, 460
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
        self._protect_window(win)

        # Border outline
        border = tk.Frame(win, bg=c["border"], padx=1, pady=1)
        border.pack(fill="both", expand=True)

        main = tk.Frame(border, bg=c["panel_bg"])
        main.pack(fill="both", expand=True)

        # ── Left Sidebar (Navigation) ──
        sidebar = tk.Frame(main, bg=c["bar_bg"], width=150)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        # Brand Logo Section
        logo_f = tk.Frame(sidebar, bg=c["bar_bg"], pady=16)
        logo_f.pack(fill="x")
        tk.Label(logo_f, text="⚡", font=("Segoe UI Emoji", 20), bg=c["bar_bg"], fg=c["accent"]).pack()
        tk.Label(logo_f, text=config.APP_NAME, font=("Segoe UI Semibold", 10), bg=c["bar_bg"], fg=c["text"]).pack(pady=4)

        # Navigation Buttons Container
        self._nav_btns = {}
        nav_items = [
            ("status", "📊  สถานะระบบ"),
            ("optimizer", "🎮  ปรับแต่งเกม"),
            ("advanced", "⚙️  ตั้งค่าขั้นสูง"),
        ]

        def handle_nav_click(target):
            self._switch_dash_tab(target)

        nav_f = tk.Frame(sidebar, bg=c["bar_bg"])
        nav_f.pack(fill="both", expand=True, pady=10)

        for key, text in nav_items:
            btn = tk.Label(
                nav_f, text=text, font=("Segoe UI", 9),
                bg=c["bar_bg"], fg=c["text_dim"], anchor="w",
                padx=16, pady=10, cursor="hand2"
            )
            btn.pack(fill="x")
            btn.bind("<Button-1>", lambda e, k=key: handle_nav_click(k))
            self._nav_btns[key] = btn

        # Sidebar Footer
        sb_foot = tk.Frame(sidebar, bg=c["bar_bg"], pady=12)
        sb_foot.pack(side="bottom", fill="x")
        tk.Label(sb_foot, text=f"v{config.APP_VERSION}", font=("Segoe UI", 8), bg=c["bar_bg"], fg=c["text_dim"]).pack()

        # ── Right Content Pane ──
        self.dash_content = tk.Frame(main, bg=c["panel_bg"], padx=18, pady=12)
        self.dash_content.pack(side="right", fill="both", expand=True)

        # Draggable Header on Sidebar and Content Pane
        sidebar.bind("<ButtonPress-1>", lambda e: setattr(win, '_dx', e.x_root - win.winfo_x()) or setattr(win, '_dy', e.y_root - win.winfo_y()))
        sidebar.bind("<B1-Motion>", lambda e: win.geometry(f"+{e.x_root - win._dx}+{e.y_root - win._dy}"))
        self.dash_content.bind("<ButtonPress-1>", lambda e: setattr(win, '_dx', e.x_root - win.winfo_x()) or setattr(win, '_dy', e.y_root - win.winfo_y()))
        self.dash_content.bind("<B1-Motion>", lambda e: win.geometry(f"+{e.x_root - win._dx}+{e.y_root - win._dy}"))

        # Switch to starting tab
        self._switch_dash_tab(tab)

    def _switch_dash_tab(self, target_tab):
        """Switches active dashboard tab and highlights sidebar button"""
        c = config.COLORS
        # Reset navigation styling
        for key, btn in self._nav_btns.items():
            btn.config(bg=c["bar_bg"], fg=c["text_dim"])
        
        # Highlight active tab
        if target_tab in self._nav_btns:
            self._nav_btns[target_tab].config(bg=c["panel_bg"], fg=c["accent"])

        # Clear Content pane
        for widget in self.dash_content.winfo_children():
            widget.destroy()

        # Render active tab
        if target_tab == "status":
            self._render_status_tab()
        elif target_tab == "optimizer":
            self._render_optimizer_tab()
        elif target_tab == "advanced":
            self._render_advanced_settings_tab()
        elif target_tab == "settings":
            self._render_advanced_settings_tab()

    # ── TAB 1: STATUS & BENTO GRID ───────────────────────
    def _render_status_tab(self):
        c = config.COLORS
        win = self._dash_win

        # Title Header
        hdr = tk.Frame(self.dash_content, bg=c["panel_bg"])
        hdr.pack(fill="x", pady=(0, 10))
        tk.Label(hdr, text="📊  สถานะระบบและประสิทธิภาพ", font=("Segoe UI Semibold", 13), bg=c["panel_bg"], fg=c["text"]).pack(side="left")
        
        close = tk.Label(hdr, text="✕", font=("Segoe UI", 12, "bold"), bg=c["panel_bg"], fg=c["text_dim"], cursor="hand2")
        close.pack(side="right")
        close.bind("<Button-1>", lambda e: win.destroy())

        # Bento Grid Container (2x2)
        grid_f = tk.Frame(self.dash_content, bg=c["panel_bg"])
        grid_f.pack(fill="both", expand=True)
        
        # Grid layout configurations
        grid_f.columnconfigure(0, weight=1, uniform="group")
        grid_f.columnconfigure(1, weight=1, uniform="group")
        grid_f.rowconfigure(0, weight=1, uniform="group")
        grid_f.rowconfigure(1, weight=1, uniform="group")

        self._bento_widgets = {}

        # 1. CPU Card
        c1 = tk.Frame(grid_f, bg=c["card"], padx=10, pady=8)
        c1.grid(row=0, column=0, padx=4, pady=4, sticky="nsew")
        c1.config(highlightbackground=c["border"], highlightthickness=1)
        tk.Label(c1, text="🖥️  CPU Usage", font=("Segoe UI Semibold", 9), bg=c["card"], fg=c["text_dim"]).pack(anchor="w")
        v1 = tk.Label(c1, text="--%", font=("Segoe UI Bold", 20), bg=c["card"], fg=c["success"])
        v1.pack(anchor="w", pady=4)
        cv1 = tk.Canvas(c1, bg=c["border"], height=4, highlightthickness=0, bd=0)
        cv1.pack(fill="x", pady=4)
        self._bento_widgets["cpu"] = (v1, cv1)

        # 2. RAM Card
        c2 = tk.Frame(grid_f, bg=c["card"], padx=10, pady=8)
        c2.grid(row=0, column=1, padx=4, pady=4, sticky="nsew")
        c2.config(highlightbackground=c["border"], highlightthickness=1)
        tk.Label(c2, text="💾  System Memory", font=("Segoe UI Semibold", 9), bg=c["card"], fg=c["text_dim"]).pack(anchor="w")
        v2 = tk.Label(c2, text="--%", font=("Segoe UI Bold", 20), bg=c["card"], fg=c["success"])
        v2.pack(anchor="w", pady=4)
        cv2 = tk.Canvas(c2, bg=c["border"], height=4, highlightthickness=0, bd=0)
        cv2.pack(fill="x", pady=4)
        self._bento_widgets["ram"] = (v2, cv2)

        # 3. GPU Card
        c3 = tk.Frame(grid_f, bg=c["card"], padx=10, pady=8)
        c3.grid(row=1, column=0, padx=4, pady=4, sticky="nsew")
        c3.config(highlightbackground=c["border"], highlightthickness=1)
        tk.Label(c3, text="🎮  GPU Temp & VRAM", font=("Segoe UI Semibold", 9), bg=c["card"], fg=c["text_dim"]).pack(anchor="w")
        v3 = tk.Label(c3, text="--°C", font=("Segoe UI Bold", 20), bg=c["card"], fg=c["success"])
        v3.pack(anchor="w", pady=4)
        cv3 = tk.Canvas(c3, bg=c["border"], height=4, highlightthickness=0, bd=0)
        cv3.pack(fill="x", pady=4)
        self._bento_widgets["gpu"] = (v3, cv3)

        # 4. Network Latency Card (PING)
        c4 = tk.Frame(grid_f, bg=c["card"], padx=10, pady=8)
        c4.grid(row=1, column=1, padx=4, pady=4, sticky="nsew")
        c4.config(highlightbackground=c["border"], highlightthickness=1)
        tk.Label(c4, text="🌐  Network Ping", font=("Segoe UI Semibold", 9), bg=c["card"], fg=c["text_dim"]).pack(anchor="w")
        v4 = tk.Label(c4, text="-- ms", font=("Segoe UI Bold", 20), bg=c["card"], fg=c["success"])
        v4.pack(anchor="w", pady=4)
        cv4 = tk.Canvas(c4, bg=c["border"], height=4, highlightthickness=0, bd=0)
        cv4.pack(fill="x", pady=4)
        self._bento_widgets["ping"] = (v4, cv4)

        # Update Bento labels immediately
        self._update_dash_labels()

        # Big Capsule Boost Button at Bottom
        bst_card = tk.Frame(self.dash_content, bg=c["card"], padx=12, pady=10)
        bst_card.pack(fill="x", pady=(10, 0))
        bst_card.config(highlightbackground=c["border"], highlightthickness=1)

        # Left Info
        info_f = tk.Frame(bst_card, bg=c["card"])
        info_f.pack(side="left", fill="y")
        
        # Calculate cache size
        cache_mb = booster.get_shader_cache_size_mb()
        tk.Label(info_f, text=f"ไฟล์ขยะสะสม: {cache_mb:.1f} MB", font=("Segoe UI", 9), bg=c["card"], fg=c["text"]).pack(anchor="w")
        tk.Label(info_f, text="เคลียร์ Cache, จัดการ RAM & ลำดับ CPU ให้ POE2", font=("Segoe UI", 8), bg=c["card"], fg=c["text_dim"]).pack(anchor="w", pady=2)

        # Right Boost Action
        bst_btn = tk.Label(
            bst_card, text="🚀  BOOST NOW", font=("Segoe UI Bold", 10),
            bg=c["accent_dim"], fg="#fff", padx=20, pady=8, cursor="hand2"
        )
        bst_btn.pack(side="right")
        bst_btn.bind("<Button-1>", lambda e: self._threaded(self._do_boost))
        bst_btn.bind("<Enter>", lambda e: bst_btn.config(bg=c["accent"]))
        bst_btn.bind("<Leave>", lambda e: bst_btn.config(bg=c["accent_dim"]))

    def _update_dash_labels(self):
        """Populate current monitor values in status tab bento cards"""
        c = config.COLORS
        if not hasattr(self, "_bento_widgets"):
            return
        try:
            # 1. CPU
            cpu = self.stats.get("cpu", 0)
            v_lbl, canvas = self._bento_widgets["cpu"]
            v_lbl.config(text=f"{cpu:.0f}%", fg=self._color(cpu))
            self._fill_dash_canvas(canvas, cpu, self._color(cpu))

            # 2. RAM
            ram = self.stats.get("ram", 0)
            v_lbl, canvas = self._bento_widgets["ram"]
            v_lbl.config(text=f"{ram:.0f}%", fg=self._color(ram))
            self._fill_dash_canvas(canvas, ram, self._color(ram))

            # 3. GPU
            gpu = self.stats.get("gpu_temp", 0)
            v_lbl, canvas = self._bento_widgets["gpu"]
            v_lbl.config(text=f"{gpu:.0f}°C", fg=self._color(gpu, 90))
            self._fill_dash_canvas(canvas, gpu, self._color(gpu, 90))

            # 4. PING
            ping = self.stats.get("ping", -1)
            v_lbl, canvas = self._bento_widgets["ping"]
            if ping >= 998:
                v_lbl.config(text="Offline", fg=c["danger"])
                self._fill_dash_canvas(canvas, 100, c["danger"])
            elif ping >= 0:
                v_lbl.config(text=f"{ping:.0f} ms", fg=self._color_ping(ping))
                ping_pct = min(100, int(ping / 300 * 100))  # Scale 300ms as max
                self._fill_dash_canvas(canvas, ping_pct, self._color_ping(ping))
            else:
                v_lbl.config(text="-- ms", fg=c["text_dim"])
                self._fill_dash_canvas(canvas, 0, c["border"])
        except Exception:
            pass

    def _fill_dash_canvas(self, canvas, pct, fill_color):
        try:
            canvas.delete("all")
            w = canvas.winfo_width()
            h = canvas.winfo_height()
            fill_w = max(1, int(w * pct / 100))
            canvas.create_rectangle(0, 0, fill_w, h, fill=fill_color, width=0)
        except Exception:
            pass

    # ── TAB 2: OPTIMIZER (CONFIGS & OVERLAYS) ────────────
    def _render_optimizer_tab(self):
        c = config.COLORS
        win = self._dash_win

        # Title
        hdr = tk.Frame(self.dash_content, bg=c["panel_bg"])
        hdr.pack(fill="x", pady=(0, 10))
        tk.Label(hdr, text="🎮  ปรับแต่งประสิทธิภาพของเกม", font=("Segoe UI Semibold", 13), bg=c["panel_bg"], fg=c["text"]).pack(side="left")
        
        close = tk.Label(hdr, text="✕", font=("Segoe UI", 12, "bold"), bg=c["panel_bg"], fg=c["text_dim"], cursor="hand2")
        close.pack(side="right")
        close.bind("<Button-1>", lambda e: win.destroy())

        # Scrollable Frame for settings list
        canvas = tk.Canvas(self.dash_content, bg=c["panel_bg"], highlightthickness=0)
        scrollbar = tk.Scrollbar(self.dash_content, orient="vertical", command=canvas.yview)
        scroll_f = tk.Frame(canvas, bg=c["panel_bg"])

        scroll_f.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        cf = canvas.create_window((0, 0), window=scroll_f, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(cf, width=e.width))

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        # ── 1. Auto Config Option ──
        tk.Label(scroll_f, text="⚡ ปรับแต่งไฟล์ POE2 Config แนะนำ", font=("Segoe UI Semibold", 10), bg=c["panel_bg"], fg=c["accent"]).pack(anchor="w", pady=(4, 4))
        
        cfg_path = booster.get_poe2_config_path()
        opt_card = tk.Frame(scroll_f, bg=c["card"], padx=12, pady=10)
        opt_card.pack(fill="x", pady=2)
        opt_card.config(highlightbackground=c["border"], highlightthickness=1)

        if cfg_path:
            is_opt, _ = booster.check_poe2_config_status(cfg_path)
            status_text = "สถานะ: ปรับแต่งแล้ว (ตามสูตรแอดมิน) ✅" if is_opt else "สถานะ: ยังไม่ได้ปรับแต่งตามสูตรแอดมิน ⚠️"
            status_color = c["success"] if is_opt else c["warning"]
            
            lbl_status = tk.Label(opt_card, text=status_text, font=("Segoe UI Semibold", 9), bg=c["card"], fg=status_color)
            lbl_status.pack(anchor="w")
            
            tk.Label(opt_card, text=f"ไฟล์: {os.path.basename(cfg_path)}", font=("Segoe UI", 8), bg=c["card"], fg=c["text_dim"]).pack(anchor="w", pady=2)

            btn_f = tk.Frame(opt_card, bg=c["card"])
            btn_f.pack(fill="x", pady=(6, 0))

            apply_b = tk.Label(btn_f, text="⚡ ใช้ค่าแนะนำของแอดมิน", font=("Segoe UI Semibold", 9), bg=c["accent_dim"], fg="#fff", padx=12, pady=6, cursor="hand2")
            apply_b.pack(side="left", padx=(0, 8))

            has_bkp = os.path.exists(cfg_path + ".backup")
            revert_b = tk.Label(btn_f, text="⏪ คืนค่าเดิม", font=("Segoe UI", 9), bg=c["border"], fg=c["text"], padx=10, pady=6, cursor="hand2")
            if has_bkp:
                revert_b.pack(side="left")

            msg_lbl = tk.Label(opt_card, text="", font=("Segoe UI", 8), bg=c["card"], fg=c["success"])
            msg_lbl.pack(anchor="w", pady=(4, 0))

            def do_apply(e):
                ok, msg = booster.optimize_poe2_config(cfg_path)
                if ok:
                    lbl_status.config(text="สถานะ: ปรับแต่งแล้ว (ตามสูตรแอดมิน) ✅", fg=c["success"])
                    revert_b.pack(side="left")
                    msg_lbl.config(text="⚡ ปรับแต่งสำเร็จ! กรุณารีสตาร์ทเกมหากเปิดอยู่", fg=c["success"])
                else:
                    msg_lbl.config(text=f"❌ {msg}", fg=c["danger"])

            def do_revert(e):
                ok, msg = booster.revert_poe2_config(cfg_path)
                if ok:
                    lbl_status.config(text="สถานะ: ยังไม่ได้ปรับแต่งตามสูตรแอดมิน ⚠️", fg=c["warning"])
                    revert_b.pack_forget()
                    msg_lbl.config(text="⏪ คืนค่าการตั้งค่าเดิมเรียบร้อยแล้ว!", fg=c["success"])
                else:
                    msg_lbl.config(text=f"❌ {msg}", fg=c["danger"])

            apply_b.bind("<Button-1>", do_apply)
            apply_b.bind("<Enter>", lambda e: apply_b.config(bg=c["accent"]))
            apply_b.bind("<Leave>", lambda e: apply_b.config(bg=c["accent_dim"]))
            
            revert_b.bind("<Button-1>", do_revert)
            revert_b.bind("<Enter>", lambda e: revert_b.config(bg=c["card_hover"]))
            revert_b.bind("<Leave>", lambda e: revert_b.config(bg=c["border"]))
        else:
            tk.Label(opt_card, text="❌ ไม่พบไฟล์ poe2_production_Config.ini", font=("Segoe UI Semibold", 9), bg=c["card"], fg=c["danger"]).pack(anchor="w")
            tk.Label(opt_card, text="กรุณาเข้าเปิดเกมอย่างน้อย 1 ครั้ง เพื่อสร้างไฟล์", font=("Segoe UI", 8), bg=c["card"], fg=c["text_dim"]).pack(anchor="w", pady=2)

        # ── 2. Active Overlays Option ──
        conflicts = booster.scan_overlay_conflicts()
        if conflicts:
            tk.Label(scroll_f, text="⚠️ แอป Overlay ที่ทำงานเบื้องหลัง", font=("Segoe UI Semibold", 10), bg=c["panel_bg"], fg=c["warning"]).pack(anchor="w", pady=(10, 4))
            
            conflict_card = tk.Frame(scroll_f, bg=c["card"], padx=12, pady=10)
            conflict_card.pack(fill="x", pady=2)
            conflict_card.config(highlightbackground=c["warning"], highlightthickness=1)

            for item in conflicts:
                disp = item["display_name"]
                tip = item["tip"]
                tk.Label(conflict_card, text=f"• {disp}", font=("Segoe UI Semibold", 9), bg=c["card"], fg=c["text"]).pack(anchor="w")
                tk.Label(conflict_card, text=tip, font=("Segoe UI", 8), bg=c["card"], fg=c["text_dim"], wraplength=450, justify="left").pack(anchor="w", padx=12, pady=(0, 4))

            btn_opt = tk.Label(conflict_card, text="⚡ ลดภาระ CPU ของแอปเหล่านี้", font=("Segoe UI Semibold", 9), bg=c["accent_dim"], fg="#fff", padx=12, pady=6, cursor="hand2")
            btn_opt.pack(anchor="w", pady=(4, 0))

            opt_msg = tk.Label(conflict_card, text="", font=("Segoe UI", 8), bg=c["card"], fg=c["success"])
            opt_msg.pack(anchor="w", pady=(4, 0))

            def do_opt_overlays(e):
                count = booster.optimize_overlay_priorities()
                opt_msg.config(text=f"✅ ปรับลดลำดับ CPU ของ Overlay {count} รายการ สำเร็จ!", fg=c["success"])

            btn_opt.bind("<Button-1>", do_opt_overlays)
            btn_opt.bind("<Enter>", lambda e: btn_opt.config(bg=c["accent"]))
            btn_opt.bind("<Leave>", lambda e: btn_opt.config(bg=c["accent_dim"]))

    # ── TAB 3: PRO FEATURES (THEMES & AUTO-BOOST) ────────
    def _render_pro_settings_tab(self):
        c = config.COLORS
        win = self._dash_win

        # Title
        hdr = tk.Frame(self.dash_content, bg=c["panel_bg"])
        hdr.pack(fill="x", pady=(0, 10))
        tk.Label(hdr, text="💎  ฟีเจอร์ระดับ PRO", font=("Segoe UI Semibold", 13), bg=c["panel_bg"], fg=c["text"]).pack(side="left")
        
        close = tk.Label(hdr, text="✕", font=("Segoe UI", 12, "bold"), bg=c["panel_bg"], fg=c["text_dim"], cursor="hand2")
        close.pack(side="right")
        close.bind("<Button-1>", lambda e: win.destroy())

        # If not Pro, show block overlay
        if not config.IS_PRO:
            lock_f = tk.Frame(self.dash_content, bg=c["card"], padx=20, pady=24)
            lock_f.pack(fill="both", expand=True, pady=10)
            lock_f.config(highlightbackground=c["border"], highlightthickness=1)
            
            tk.Label(lock_f, text="🔒 ฟีเจอร์นี้เฉพาะสมาชิกระดับ PRO เท่านั้น", font=("Segoe UI Semibold", 12), bg=c["card"], fg=c["pro_badge"]).pack(pady=(10, 8))
            tk.Label(lock_f, text="ปลดล็อกสุดยอดฟีเจอร์ช่วยให้การเล่นเกมสมบูรณ์แบบที่สุด:\n\n"
                                  "• 🔄 Auto-Boost: ไม่ต้องกดบูสต์เอง แอปสแกนและรันคำสั่งเมื่อเปิดเกมทันที\n"
                                  "• 🎬 OBS Streamer Mode: ซ่อนแถบ Overlay ทั้งหมดไม่ให้ผู้ชมในสตรีมเห็น\n"
                                  "• 🌐 Real-time Ping: ติดตามค่าความหน่วงสัญญาณเน็ตได้ตลอดเวลา\n"
                                  "• ⏰ Smart Auto-Clean: ป้องกันเกมสะดุดจากการลืมล้างไฟล์แคชสะสม\n"
                                  "• 🎨 Custom Themes: ปรับแต่งโทนสี Overlay ได้ตามสไตล์ที่คุณชอบ",
                     font=("Segoe UI", 10), bg=c["card"], fg=c["text_dim"], justify="left", wraplength=440).pack(pady=8)
            
            btn_act = tk.Label(lock_f, text="🔑  ไปที่หน้าใส่คีย์ใช้งาน", font=("Segoe UI Semibold", 10), bg=c["accent_dim"], fg="#fff", padx=16, pady=8, cursor="hand2")
            btn_act.pack(pady=12)
            btn_act.bind("<Button-1>", lambda e: self._switch_dash_tab("activation"))
            btn_act.bind("<Enter>", lambda e: btn_act.config(bg=c["accent"]))
            btn_act.bind("<Leave>", lambda e: btn_act.config(bg=c["accent_dim"]))
            return

        # Render Pro settings controls
        f_options = tk.Frame(self.dash_content, bg=c["panel_bg"])
        f_options.pack(fill="both", expand=True)

        def save_pro_settings():
            config.save_config_file(
                auto_boost=self.pro_auto_boost,
                auto_clean=self.pro_auto_clean,
                streamer_mode=self.pro_streamer_mode
            )
            self._apply_streamer_mode()

        def toggle_opt(key):
            if key == "auto_boost":
                self.pro_auto_boost = not self.pro_auto_boost
            elif key == "auto_clean":
                self.pro_auto_clean = not self.pro_auto_clean
            elif key == "streamer_mode":
                self.pro_streamer_mode = not self.pro_streamer_mode
            save_pro_settings()
            self._switch_dash_tab("pro_settings")  # Redraw tab to reflect checkbox states

        # 1. Option Auto Boost
        f_ab = tk.Frame(f_options, bg=c["card"], padx=12, pady=10)
        f_ab.pack(fill="x", pady=4)
        f_ab.config(highlightbackground=c["border"], highlightthickness=1)
        cb_ab = tk.Label(f_ab, text="[ ✓ ]" if self.pro_auto_boost else "[   ]", font=("Segoe UI Bold", 10), bg=c["card"], fg=c["accent"] if self.pro_auto_boost else c["text_dim"], cursor="hand2")
        cb_ab.pack(side="left", padx=(4, 10))
        cb_ab.bind("<Button-1>", lambda e: toggle_opt("auto_boost"))
        tk.Label(f_ab, text="🔄  เปิดใช้งาน Auto-Boost อัตโนมัติ", font=("Segoe UI Semibold", 9), bg=c["card"], fg=c["text"]).pack(side="left")
        tk.Label(f_ab, text="ล้างแคช/จัดลำดับแรมทันทีเมื่อเกมเริ่มรัน", font=("Segoe UI", 8), bg=c["card"], fg=c["text_dim"]).pack(side="right", padx=10)

        # 2. Option Auto Cache Clear
        f_ac = tk.Frame(f_options, bg=c["card"], padx=12, pady=10)
        f_ac.pack(fill="x", pady=4)
        f_ac.config(highlightbackground=c["border"], highlightthickness=1)
        cb_ac = tk.Label(f_ac, text="[ ✓ ]" if self.pro_auto_clean else "[   ]", font=("Segoe UI Bold", 10), bg=c["card"], fg=c["accent"] if self.pro_auto_clean else c["text_dim"], cursor="hand2")
        cb_ac.pack(side="left", padx=(4, 10))
        cb_ac.bind("<Button-1>", lambda e: toggle_opt("auto_clean"))
        tk.Label(f_ac, text="⏰  เปิดใช้งาน Smart Cache Auto-Cleaner", font=("Segoe UI Semibold", 9), bg=c["card"], fg=c["text"]).pack(side="left")
        tk.Label(f_ac, text="เคลียร์ไฟล์ขยะแคชทันทีหากตรวจพบขนาดเกิน 500MB", font=("Segoe UI", 8), bg=c["card"], fg=c["text_dim"]).pack(side="right", padx=10)

        # 3. Option OBS Streamer Mode
        f_sm = tk.Frame(f_options, bg=c["card"], padx=12, pady=10)
        f_sm.pack(fill="x", pady=4)
        f_sm.config(highlightbackground=c["border"], highlightthickness=1)
        cb_sm = tk.Label(f_sm, text="[ ✓ ]" if self.pro_streamer_mode else "[   ]", font=("Segoe UI Bold", 10), bg=c["card"], fg=c["accent"] if self.pro_streamer_mode else c["text_dim"], cursor="hand2")
        cb_sm.pack(side="left", padx=(4, 10))
        cb_sm.bind("<Button-1>", lambda e: toggle_opt("streamer_mode"))
        tk.Label(f_sm, text="🎬  เปิดใช้งาน OBS Streamer Mode", font=("Segoe UI Semibold", 9), bg=c["card"], fg=c["text"]).pack(side="left")
        tk.Label(f_sm, text="ซ่อนหน้าต่างและ Overlay บนภาพหน้าจอของ OBS", font=("Segoe UI", 8), bg=c["card"], fg=c["text_dim"]).pack(side="right", padx=10)

        # 4. Color Themes selector
        f_theme = tk.Frame(f_options, bg=c["card"], padx=12, pady=12)
        f_theme.pack(fill="x", pady=10)
        f_theme.config(highlightbackground=c["border"], highlightthickness=1)
        tk.Label(f_theme, text="🎨  เลือกชุดสี (Accent Theme):", font=("Segoe UI Semibold", 9), bg=c["card"], fg=c["text"]).pack(anchor="w")

        f_colors = tk.Frame(f_theme, bg=c["card"], pady=6)
        f_colors.pack(anchor="w")

        # Available Themes details
        theme_list = [
            ("blue", "Electric Blue 🟦", "#58a6ff"),
            ("purple", "Purple Haze 🟪", "#a855f7"),
            ("amber", "Cyberpunk Amber 🟨", "#ffb020"),
            ("green", "Emerald Green 🟩", "#22c55e")
        ]

        def do_theme_change(t_name):
            config.switch_theme(t_name)
            self._apply_streamer_mode()
            self._refresh_theme()
            self._switch_dash_tab("pro_settings")  # Redraw tab with new colors!

        for t_key, t_title, t_hex in theme_list:
            btn_t = tk.Label(
                f_colors, text=t_title, font=("Segoe UI Semibold" if config.CURRENT_THEME == t_key else "Segoe UI", 9),
                bg=c["border"] if config.CURRENT_THEME == t_key else c["panel_bg"],
                fg=t_hex, padx=12, pady=6, cursor="hand2"
            )
            btn_t.pack(side="left", padx=4)
            btn_t.bind("<Button-1>", lambda e, k=t_key: do_theme_change(k))
            btn_t.config(highlightbackground=t_hex, highlightthickness=1)

    # ── TAB 4: ACTIVATION (LICENSE VERIFICATION) ────────
    def _render_activation_tab(self):
        c = config.COLORS
        win = self._dash_win

        # Title
        hdr = tk.Frame(self.dash_content, bg=c["panel_bg"])
        hdr.pack(fill="x", pady=(0, 10))
        tk.Label(hdr, text="🔑  เปิดใช้งานคีย์สมาชิกระดับ PRO", font=("Segoe UI Semibold", 13), bg=c["panel_bg"], fg=c["text"]).pack(side="left")
        
        close = tk.Label(hdr, text="✕", font=("Segoe UI", 12, "bold"), bg=c["panel_bg"], fg=c["text_dim"], cursor="hand2")
        close.pack(side="right")
        close.bind("<Button-1>", lambda e: win.destroy())

        act_f = tk.Frame(self.dash_content, bg=c["card"], padx=16, pady=16)
        act_f.pack(fill="both", expand=True, pady=10)
        act_f.config(highlightbackground=c["border"], highlightthickness=1)

        status_txt = "สมาชิกระดับ PRO: เปิดใช้งานแล้ว ✅" if config.IS_PRO else "สมาชิกระดับ PRO: ยังไม่ได้เปิดใช้งาน ❌"
        status_col = c["success"] if config.IS_PRO else c["text_dim"]

        tk.Label(act_f, text=status_txt, font=("Segoe UI Semibold", 11), bg=c["card"], fg=status_col).pack(pady=(5, 12))

        # Enter key label
        tk.Label(act_f, text="ระบุ License Key ของคุณด้านล่าง:", font=("Segoe UI", 9), bg=c["card"], fg=c["text"]).pack(anchor="w", padx=12)

        # Key Input
        entry_f = tk.Frame(act_f, bg=c["card"], pady=6)
        entry_f.pack(fill="x", padx=12)
        
        key_entry = tk.Entry(
            entry_f, font=("Consolas", 11),
            bg=c["panel_bg"], fg=c["text"],
            insertbackground=c["text"], relief="flat",
            highlightthickness=1, highlightbackground=c["border"],
            highlightcolor=c["accent"]
        )
        key_entry.pack(fill="x", ipady=4)
        
        if config.IS_PRO and config.LICENSE_KEY:
            # Mask the license key for display security
            masked = config.LICENSE_KEY[:9] + "XXXX-XXXX-XXXX"
            key_entry.insert(0, masked)
            key_entry.config(state="disabled")

        # Action Buttons
        btn_action_f = tk.Frame(act_f, bg=c["card"], pady=8)
        btn_action_f.pack(fill="x", padx=12)

        msg_lbl = tk.Label(act_f, text="", font=("Segoe UI", 9), bg=c["card"])
        msg_lbl.pack(pady=4)

        def do_activate():
            key = key_entry.get().strip()
            if not key:
                msg_lbl.config(text="❌ กรุณาระบุคีย์ของท่าน", fg=c["danger"])
                return
            
            if config.verify_license(key):
                config.save_config_file(license_key=key)
                self._apply_streamer_mode()
                self._refresh_theme()
                self._switch_dash_tab("activation")
                msg_lbl.config(text="✅ ปลดล็อกระดับ PRO สำเร็จแล้ว! ขอบพระคุณที่สนับสนุนเราครับ", fg=c["success"])
            else:
                msg_lbl.config(text="❌ คีย์สมาชิกระดับ PRO ไม่ถูกต้องตามเงื่อนไข", fg=c["danger"])

        def do_deactivate():
            config.save_config_file(license_key="")
            # Set local settings to False
            self.pro_auto_boost = False
            self.pro_auto_clean = False
            self.pro_streamer_mode = False
            config.save_config_file(auto_boost=False, auto_clean=False, streamer_mode=False)
            self._apply_streamer_mode()
            self._refresh_theme()
            self._switch_dash_tab("activation")
            msg_lbl.config(text="⏩ คืนสิทธิ์การเข้าถึงเป็นระดับใช้งานปกติเรียบร้อยแล้ว", fg=c["accent"])

        if config.IS_PRO:
            deact_btn = tk.Label(btn_action_f, text="❌  ยกเลิกการล็อกอินคีย์นี้", font=("Segoe UI Semibold", 10), bg=c["border"], fg=c["danger"], padx=16, pady=8, cursor="hand2")
            deact_btn.pack(side="left")
            deact_btn.bind("<Button-1>", lambda e: do_deactivate())
        else:
            act_btn = tk.Label(btn_action_f, text="🔑  เปิดใช้งาน PRO", font=("Segoe UI Semibold", 10), bg=c["accent_dim"], fg="#fff", padx=16, pady=8, cursor="hand2")
            act_btn.pack(side="left", padx=(0, 10))
            act_btn.bind("<Button-1>", lambda e: do_activate())
            act_btn.bind("<Enter>", lambda e: act_btn.config(bg=c["accent"]))
            act_btn.bind("<Leave>", lambda e: act_btn.config(bg=c["accent_dim"]))

            # Purchase Key Link
            def open_buy():
                try:
                    import webbrowser
                    webbrowser.open(config.APP_WEBSITE)
                except Exception:
                    pass

            buy_lbl = tk.Label(btn_action_f, text="🛒 ยังไม่มีคีย์? ซื้อใช้งานได้ที่นี่ →", font=("Segoe UI", 9, "underline"), bg=c["card"], fg=c["accent"], cursor="hand2")
            buy_lbl.pack(side="right", pady=8)
            buy_lbl.bind("<Button-1>", lambda e: open_buy())

    # ══════════════════════════════════════════════════════
    #   AUTO-UPDATE (with silent auto-update via Boost)
    # ══════════════════════════════════════════════════════
    def _check_update(self):
        """Check GitHub for new version in background"""
        def check():
            try:
                info = updater.check_for_update(config.APP_VERSION)
                if info:
                    self._update_info = info
                    self.root.after(0, lambda: self._show_update_available(info))
            except Exception:
                pass
        threading.Thread(target=check, daemon=True).start()

    def _show_update_available(self, info):
        c = config.COLORS
        version = info["version"]
        size_mb = info.get("size", 0) / (1024 * 1024)
        self.update_label.config(
            text=f"⬆ พบเวอร์ชันใหม่ {version} ({size_mb:.1f} MB)",
            bg="#1a4a1a", fg=c["success"]
        )
        self.update_label.pack(side="left", padx=4, pady=4)
        self.update_label.bind("<Button-1>", lambda e: self._show_update_dialog())
        self.update_label.bind("<Enter>",
                               lambda e: self.update_label.config(bg=c["success"], fg="#fff"))
        self.update_label.bind("<Leave>",
                               lambda e: self.update_label.config(bg="#1a4a1a", fg=c["success"]))
        self._pulse_update_badge()
        self._status(f"🔄 พบเวอร์ชันใหม่ {version}", c["accent"])

    def _pulse_update_badge(self):
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
        c = config.COLORS

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

        # Create dialog window
        win = tk.Toplevel(self.root)
        self._update_win = win
        win.title("อัปเดตใหม่!")
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg=c["panel_bg"])
        w, h = 420, 400
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
        self._protect_window(win)

        border = tk.Frame(win, bg=c["accent"], padx=2, pady=2)
        border.pack(fill="both", expand=True)
        main = tk.Frame(border, bg=c["panel_bg"], padx=16, pady=12)
        main.pack(fill="both", expand=True)

        hdr = tk.Frame(main, bg=c["panel_bg"])
        hdr.pack(fill="x")
        tk.Label(hdr, text="🔄 พบเวอร์ชันใหม่!",
                 font=("Segoe UI Semibold", 14), bg=c["panel_bg"],
                 fg=c["accent"]).pack(side="left")
        close_btn = tk.Label(hdr, text="✕", font=("Segoe UI", 12, "bold"),
                             bg=c["panel_bg"], fg=c["text_dim"], cursor="hand2")
        close_btn.pack(side="right")
        close_btn.bind("<Button-1>", lambda e: win.destroy())

        tk.Frame(main, bg=c["border"], height=1).pack(fill="x", pady=8)

        # Version comparison
        ver_frame = tk.Frame(main, bg=c["card"], padx=12, pady=10)
        ver_frame.pack(fill="x", pady=(0, 8))
        ver_frame.config(highlightbackground=c["border"], highlightthickness=1)
        tk.Label(ver_frame, text=f"เวอร์ชันปัจจุบัน:   v{config.APP_VERSION}",
                 font=("Segoe UI", 10), bg=c["card"],
                 fg=c["text_dim"]).pack(anchor="w")
        tk.Label(ver_frame, text=f"เวอร์ชันใหม่:         {version}",
                 font=("Segoe UI Semibold", 10), bg=c["card"],
                 fg=c["success"]).pack(anchor="w")
        tk.Label(ver_frame, text=f"ขนาดไฟล์:            {size_mb:.1f} MB",
                 font=("Segoe UI", 10), bg=c["card"],
                 fg=c["text_dim"]).pack(anchor="w")

        # Release Notes
        tk.Label(main, text="📋 มีอะไรใหม่:",
                 font=("Segoe UI Semibold", 10), bg=c["panel_bg"],
                 fg=c["text"]).pack(anchor="w", pady=(4, 2))
        notes_frame = tk.Frame(main, bg=c["card"], padx=10, pady=8)
        notes_frame.pack(fill="both", expand=True, pady=(0, 8))
        notes_frame.config(highlightbackground=c["border"], highlightthickness=1)
        display_notes = notes[:500] + ("..." if len(notes) > 500 else "")
        notes_lbl = tk.Label(notes_frame, text=display_notes,
                             font=("Segoe UI", 9), bg=c["card"],
                             fg=c["text_dim"], wraplength=370, justify="left")
        notes_lbl.pack(anchor="w")

        # Progress bar
        prog_frame = tk.Frame(main, bg=c["panel_bg"])
        prog_bar_bg = tk.Frame(prog_frame, bg=c["card"], height=22)
        prog_bar_bg.pack(fill="x")
        prog_bar_bg.pack_propagate(False)
        prog_fill = tk.Frame(prog_bar_bg, bg=c["accent"], width=0)
        prog_fill.place(x=0, y=0, relheight=1, width=0)
        prog_text = tk.Label(prog_bar_bg, text="0%",
                             font=("Segoe UI Semibold", 9), bg=c["card"],
                             fg="#fff")
        prog_text.place(relx=0.5, rely=0.5, anchor="center")
        status_lbl = tk.Label(prog_frame, text="",
                              font=("Segoe UI", 9), bg=c["panel_bg"],
                              fg=c["text_dim"])
        status_lbl.pack(anchor="w", pady=(4, 0))

        btn_frame = tk.Frame(main, bg=c["panel_bg"])
        btn_frame.pack(fill="x", pady=(4, 0))

        def make_btn(parent, text, bg_color, fg_color, cmd):
            b = tk.Label(parent, text=text, font=("Segoe UI Semibold", 10),
                         bg=bg_color, fg=fg_color, padx=16, pady=6,
                         cursor="hand2")
            b.bind("<Button-1>", lambda e: cmd())
            hover_bg = c.get("accent", "#3388ff")
            b.bind("<Enter>", lambda e: b.config(bg=hover_bg))
            b.bind("<Leave>", lambda e: b.config(bg=bg_color))
            return b

        def _countdown_restart(seconds_left, temp_path=None):
            if seconds_left <= 0:
                auto_btn.config(text="🔄 รีสตาร์ทตอนนี้!", bg=c["accent"])
                status_lbl.config(text="🔄 กำลังปิดแอปเพื่ออัปเดต...", fg=c["accent"])
                self.root.after(500, lambda: self._quit(getattr(self, "tray", None)))
                return

            dots = "." * (4 - seconds_left % 4)
            auto_btn.config(
                text=f"⏳ รีสตาร์ทใน {seconds_left} วินาที{dots}",
                bg=c["success"], fg="#fff"
            )
            status_lbl.config(
                text=f"✅ ดาวน์โหลดเสร็จแล้ว! แอปจะปิดและเปิดใหม่เป็นเวอร์ชัน {version} อัตโนมัติ",
                fg=c["success"]
            )
            prog_fill.config(bg=c["success"])
            prog_fill.place(x=0, y=0, relheight=1, relwidth=1)
            prog_text.config(text=f"🔄 {seconds_left}s", bg=c["success"])
            self.root.after(1000, lambda: _countdown_restart(seconds_left - 1, temp_path))

        def do_auto_update():
            auto_btn.config(text="⏳ กำลังดาวน์โหลด...", bg=c["warning"], cursor="")
            auto_btn.unbind("<Button-1>")
            auto_btn.unbind("<Enter>")
            auto_btn.unbind("<Leave>")
            close_btn.unbind("<Button-1>")
            close_btn.config(fg=c["panel_bg"])
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
                        prog_text.config(text=f"{pct}%", bg=c["accent"] if pct > 40 else c["card"])
                        status_lbl.config(text=msg, fg=c["warning"])
                        auto_btn.config(text=f"⏳ ดาวน์โหลด {pct}%")
                    elif status == "downloaded":
                        prog_fill.place(x=0, y=0, relheight=1, relwidth=1)
                        prog_text.config(text="100%", bg=c["accent"])
                        status_lbl.config(text=f"✅ {msg}", fg=c["success"])
                        auto_btn.config(text="✅ ดาวน์โหลดเสร็จ!", bg=c["success"])
                    elif status == "installing":
                        status_lbl.config(text=f"📦 {msg}", fg=c["accent"])
                    elif status == "restarting":
                        status_lbl.config(text=f"✅ {msg}", fg=c["success"])
                    elif status == "error":
                        status_lbl.config(text=f"❌ {msg}", fg=c["danger"])
                        auto_btn.config(text="❌ ล้มเหลว", bg=c["danger"])
                        close_btn.bind("<Button-1>", lambda e: win.destroy())
                        close_btn.config(fg=c["text_dim"])
                        _show_fallback_btn()
                self.root.after(0, ui)

            def run():
                temp_path = updater.download_to_temp(download_url, callback=callback)
                if not temp_path:
                    return
                ok = updater.apply_update_and_restart(temp_path, callback=callback)
                if ok:
                    self.root.after(0, lambda: _countdown_restart(3, temp_path))
                else:
                    self.root.after(0, _show_fallback_btn)

            threading.Thread(target=run, daemon=True).start()

        def do_download_only():
            auto_btn.config(text="⏳ กำลังดาวน์โหลด...", bg=c["warning"], cursor="")
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
                        prog_text.config(text=f"{pct}%", bg=c["accent"] if pct > 40 else c["card"])
                        status_lbl.config(text=msg, fg=c["warning"])
                        auto_btn.config(text=f"⏳ ดาวน์โหลด {pct}%")
                    elif status == "downloaded":
                        prog_fill.place(x=0, y=0, relheight=1, relwidth=1)
                        prog_text.config(text="100%", bg=c["success"])
                    elif status == "error":
                        status_lbl.config(text=f"❌ {msg}", fg=c["danger"])
                        auto_btn.config(text="❌ ล้มเหลว", bg=c["danger"])
                self.root.after(0, ui)

            def run():
                dest = updater.download_to_temp(download_url, callback=callback)
                if dest:
                    def show_done():
                        auto_btn.config(text="✅ ดาวน์โหลดเสร็จ!", bg=c["success"])
                        status_lbl.config(
                            text=f"📂 ไฟล์อยู่ที่: {dest}\nเปิดโฟลเดอร์ให้แล้ว — นำไฟล์ไปแทนที่ตัวเก่าแล้วเปิดใหม่",
                            fg=c["success"]
                        )
                        try:
                            folder = os.path.dirname(dest)
                            os.startfile(folder)
                        except Exception:
                            pass
                    self.root.after(0, show_done)

            threading.Thread(target=run, daemon=True).start()

        def do_open_browser():
            release_url = updater.get_release_url(version)
            try:
                webbrowser.open(release_url)
                status_lbl.config(text="🌐 เปิดหน้าดาวน์โหลดในเบราว์เซอร์แล้ว")
                prog_frame.pack(fill="x", pady=(0, 4), before=btn_frame)
            except Exception:
                status_lbl.config(text="❌ ไม่สามารถเปิดเบราว์เซอร์ได้")

        def _show_fallback_btn():
            fb = tk.Label(btn_frame, text="🌐 ดาวน์โหลดจากเว็บแทน",
                          font=("Segoe UI Semibold", 10),
                          bg="#1a3a5a", fg="#6ab7ff", padx=16, pady=6,
                          cursor="hand2")
            fb.pack(side="left", fill="x", expand=True, padx=(0, 2), pady=(4, 0))
            fb.bind("<Button-1>", lambda e: do_open_browser())

        if is_frozen:
            auto_btn = make_btn(btn_frame, "⬆ อัปเดตและรีสตาร์ทอัตโนมัติ",
                                c["accent_dim"], "#fff", do_auto_update)
            auto_btn.pack(side="left", fill="x", expand=True, padx=(0, 4))
            manual_btn = make_btn(btn_frame, "🌐 เว็บ",
                                  c["card"], c["text_dim"], do_open_browser)
            manual_btn.pack(side="left", padx=(0, 0))
        else:
            auto_btn = make_btn(btn_frame, "⬇ ดาวน์โหลด .exe ใหม่",
                                c["accent_dim"], "#fff", do_download_only)
            auto_btn.pack(side="left", fill="x", expand=True, padx=(0, 4))
            manual_btn = make_btn(btn_frame, "🌐 เว็บ",
                                  c["card"], c["text_dim"], do_open_browser)
            manual_btn.pack(side="left", padx=(0, 0))

        # Draggable header
        hdr.bind("<ButtonPress-1>", lambda e: setattr(win, '_dx', e.x_root - win.winfo_x()) or setattr(win, '_dy', e.y_root - win.winfo_y()))
        hdr.bind("<B1-Motion>", lambda e: win.geometry(f"+{e.x_root - win._dx}+{e.y_root - win._dy}"))

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
        keyboard.add_hotkey(config.HOTKEY, lambda: self.root.after(0, self._toggle_visibility),
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
            self.tray = pystray.Icon(config.APP_NAME, img, config.APP_NAME, menu)
            self.tray.run()
        threading.Thread(target=go, daemon=True).start()

    def _show_wizard(self):
        SetupWizard(self.root, booster, on_complete=None).show()

    def _quit(self, icon=None):
        self.monitor_running = False
        if icon:
            icon.stop()
        self.root.after(0, self.root.destroy)

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW",
                           lambda: self._quit(getattr(self, 'tray', None)))
        print(f"{config.APP_NAME} v{config.APP_VERSION} is running!")
        print(f"Hotkey: {config.HOTKEY} | Bar stays on top of game")
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
