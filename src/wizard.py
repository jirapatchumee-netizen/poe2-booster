"""
POE2 Booster — First-Time Setup Wizard
Shows on first launch, scans system, offers one-click fix
"""

import tkinter as tk
import threading
import os
import json

from config import COLORS as C, APP_NAME, APP_VERSION


class SetupWizard:
    """First-time setup wizard that scans system and offers fixes"""

    def __init__(self, parent, booster_module, on_complete):
        self.parent = parent
        self.booster = booster_module
        self.on_complete = on_complete
        self.window = None
        self.issues = []

    def show(self):
        self.window = tk.Toplevel(self.parent)
        self.window.title(f"{APP_NAME} — Setup")
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.attributes("-alpha", 0.96)
        self.window.configure(bg=C["wizard_bg"])

        w, h = 460, 520
        sw = self.window.winfo_screenwidth()
        sh = self.window.winfo_screenheight()
        self.window.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

        main = tk.Frame(self.window, bg=C["wizard_bg"], padx=24, pady=20)
        main.pack(fill="both", expand=True)

        # Header
        tk.Label(
            main, text="👋", font=("Segoe UI Emoji", 28),
            bg=C["wizard_bg"], fg=C["accent"]
        ).pack(pady=(0, 4))

        tk.Label(
            main, text=f"Welcome to {APP_NAME}!",
            font=("Segoe UI", 16, "bold"),
            bg=C["wizard_bg"], fg=C["text"]
        ).pack()

        tk.Label(
            main, text=f"v{APP_VERSION}",
            font=("Segoe UI", 9),
            bg=C["wizard_bg"], fg=C["text_dim"]
        ).pack(pady=(0, 12))

        tk.Frame(main, bg=C["border"], height=1).pack(fill="x", pady=(0, 12))

        # Scanning label
        self.scan_label = tk.Label(
            main, text="🔍 กำลังสแกนระบบ...",
            font=("Segoe UI", 10),
            bg=C["wizard_bg"], fg=C["warning"]
        )
        self.scan_label.pack(anchor="w", pady=(0, 8))

        # Issues container
        self.issues_frame = tk.Frame(main, bg=C["wizard_bg"])
        self.issues_frame.pack(fill="both", expand=True)

        # Buttons frame (hidden until scan completes)
        self.btn_frame = tk.Frame(main, bg=C["wizard_bg"])
        self.btn_frame.pack(fill="x", pady=(12, 0))

        # Start scan
        threading.Thread(target=self._scan, daemon=True).start()

    def _scan(self):
        self.issues = self.booster.scan_system_issues()
        self.window.after(0, self._show_results)

    def _show_results(self):
        if not self.issues:
            self.scan_label.config(
                text="✅ ระบบพร้อมใช้งาน! ไม่พบปัญหา",
                fg=C["success"]
            )
            self._add_start_button()
            return

        self.scan_label.config(
            text=f"⚠️ พบปัญหา {len(self.issues)} รายการ:",
            fg=C["warning"]
        )

        for issue in self.issues:
            card = tk.Frame(
                self.issues_frame, bg=C["card"], padx=10, pady=8,
            )
            card.pack(fill="x", pady=3)
            card.config(highlightbackground=C["border"], highlightthickness=1)

            tk.Label(
                card, text=issue["icon"], font=("Segoe UI Emoji", 14),
                bg=C["card"], fg=C["warning"]
            ).pack(side="left", padx=(0, 8))

            text_frame = tk.Frame(card, bg=C["card"])
            text_frame.pack(side="left", fill="x", expand=True)

            tk.Label(
                text_frame, text=issue["title"],
                font=("Segoe UI Semibold", 10),
                bg=C["card"], fg=C["text"], anchor="w"
            ).pack(anchor="w")

            tk.Label(
                text_frame, text=issue["desc"],
                font=("Segoe UI", 8),
                bg=C["card"], fg=C["text_dim"], anchor="w"
            ).pack(anchor="w")

        # Fix All button
        fix_btn = tk.Label(
            self.btn_frame, text="🚀 แก้ทุกอย่าง (กดปุ่มเดียว)",
            font=("Segoe UI Semibold", 11),
            bg=C["accent_dim"], fg="#ffffff",
            padx=20, pady=10, cursor="hand2"
        )
        fix_btn.pack(fill="x", pady=(0, 6))
        fix_btn.bind("<Button-1>", lambda e: self._fix_all())
        fix_btn.bind("<Enter>", lambda e: fix_btn.config(bg=C["accent"]))
        fix_btn.bind("<Leave>", lambda e: fix_btn.config(bg=C["accent_dim"]))

        self._add_start_button(text="ข้าม →")

    def _fix_all(self):
        self.scan_label.config(text="🔄 กำลังแก้ไข...", fg=C["warning"])
        threading.Thread(target=self._run_fixes, daemon=True).start()

    def _run_fixes(self):
        results = self.booster.boost_all()
        self.window.after(0, lambda: self.scan_label.config(
            text="✅ แก้ไขทุกอย่างแล้ว!", fg=C["success"]
        ))

    def _add_start_button(self, text="เริ่มใช้งาน →"):
        start_btn = tk.Label(
            self.btn_frame, text=text,
            font=("Segoe UI", 10),
            bg=C["wizard_bg"], fg=C["text_dim"],
            padx=10, pady=6, cursor="hand2"
        )
        start_btn.pack(fill="x")
        start_btn.bind("<Button-1>", lambda e: self._finish())
        start_btn.bind("<Enter>", lambda e: start_btn.config(fg=C["text"]))
        start_btn.bind("<Leave>", lambda e: start_btn.config(fg=C["text_dim"]))

    def _finish(self):
        # Save first-run flag
        _save_first_run_complete()
        self.window.destroy()
        if self.on_complete:
            self.on_complete()


def is_first_run():
    """Check if this is the first time running the app"""
    config_path = _get_config_path()
    return not os.path.exists(config_path)


def _save_first_run_complete():
    """Mark first run as complete"""
    config_path = _get_config_path()
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, "w") as f:
        json.dump({"first_run_complete": True, "version": APP_VERSION}, f)


def _get_config_path():
    appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
    return os.path.join(appdata, "POE2Booster", "config.json")
