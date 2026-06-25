"""
POE2 Booster — First-Time Setup Wizard
Shows on first launch, scans system, offers one-click fix
======================================================
"""

import tkinter as tk
import threading
import os
import json
import ctypes

import config


class SetupWizard:
    """First-time setup wizard that scans system and offers fixes"""

    def __init__(self, parent, booster_module, on_complete):
        self.parent = parent
        self.booster = booster_module
        self.on_complete = on_complete
        self.window = None
        self.issues = []

    def show(self):
        c = config.COLORS
        self.window = tk.Toplevel(self.parent)
        self.window.title(f"{config.APP_NAME} — Setup")
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.attributes("-alpha", 0.96)
        self.window.configure(bg=c["panel_bg"])

        w, h = 460, 520
        sw = self.window.winfo_screenwidth()
        sh = self.window.winfo_screenheight()
        self.window.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

        # Streamer mode protection if enabled (though first run usually not enabled yet)
        if config.IS_PRO:
            try:
                self.window.update_idletasks()
                hwnd = int(self.window.wm_frame(), 16)
                ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 0x00000011)
            except Exception:
                pass

        # Border
        border = tk.Frame(self.window, bg=c["border"], padx=1, pady=1)
        border.pack(fill="both", expand=True)

        main = tk.Frame(border, bg=c["panel_bg"], padx=24, pady=20)
        main.pack(fill="both", expand=True)

        # Header
        tk.Label(
            main, text="👋", font=("Segoe UI Emoji", 28),
            bg=c["panel_bg"], fg=c["accent"]
        ).pack(pady=(0, 4))

        tk.Label(
            main, text=f"ยินดีต้อนรับสู่ {config.APP_NAME}!",
            font=("Segoe UI Semibold", 14),
            bg=c["panel_bg"], fg=c["text"]
        ).pack()

        tk.Label(
            main, text=f"เวอร์ชัน {config.APP_VERSION} — สำหรับผู้เล่น Path of Exile 2",
            font=("Segoe UI", 9),
            bg=c["panel_bg"], fg=c["text_dim"]
        ).pack(pady=(2, 10))

        # Divider
        tk.Frame(main, bg=c["border"], height=1).pack(fill="x", pady=6)

        # Scan Area
        self.scan_label = tk.Label(
            main, text="🔍 กำลังสแกนประสิทธิภาพระบบของเครื่องคุณ...",
            font=("Segoe UI", 10),
            bg=c["panel_bg"], fg=c["warning"]
        )
        self.scan_label.pack(pady=6)

        # Issues Container
        self.issues_frame = tk.Frame(main, bg=c["panel_bg"])
        self.issues_frame.pack(fill="both", expand=True, pady=6)

        # Actions buttons area
        self.btn_frame = tk.Frame(main, bg=c["panel_bg"])
        self.btn_frame.pack(fill="x", side="bottom")

        # Draggable
        main.bind("<ButtonPress-1>", lambda e: setattr(self.window, '_dx', e.x_root - self.window.winfo_x()) or setattr(self.window, '_dy', e.y_root - self.window.winfo_y()))
        main.bind("<B1-Motion>", lambda e: self.window.geometry(f"+{e.x_root - self.window._dx}+{e.y_root - self.window._dy}"))

        # Start scan in thread
        threading.Thread(target=self._run_scan, daemon=True).start()

    def _run_scan(self):
        c = config.COLORS
        self.issues = self.booster.scan_system_issues()
        self.window.after(0, self._render_scan_results)

    def _render_scan_results(self):
        c = config.COLORS
        # Clear loading label
        self.scan_label.pack_forget()

        if not self.issues:
            # All Optimized
            self.scan_label.config(text="✅ ไม่พบไฟล์ขยะหรือระบบคอขวดสะสม! ระบบพร้อมเล่นแล้ว", fg=c["success"])
            self.scan_label.pack(pady=12)

            info = tk.Frame(self.issues_frame, bg=c["card"], padx=16, pady=16)
            info.pack(fill="both", expand=True, pady=10)
            info.config(highlightbackground=c["border"], highlightthickness=1)
            tk.Label(info, text="🎉 ระบบของคุณได้รับการปรับแต่งระดับดีเยี่ยมอยู่แล้ว", font=("Segoe UI Semibold", 10), bg=c["card"], fg=c["text"]).pack(pady=4)
            tk.Label(info, text="กดปุ่ม 'เริ่มใช้งาน' เพื่อสลับเข้าสู่หน้าต่างทำงาน Overlay ในเกม", font=("Segoe UI", 9), bg=c["card"], fg=c["text_dim"]).pack()

            self._add_start_button("เริ่มใช้งาน →")
        else:
            # Issues found
            self.scan_label.config(text=f"⚠️ ตรวจพบปัญหาประสิทธิภาพ {len(self.issues)} รายการที่แก้ไขได้!", fg=c["warning"])
            self.scan_label.pack(pady=6)

            for issue in self.issues:
                card = tk.Frame(self.issues_frame, bg=c["card"], padx=12, pady=10)
                card.pack(fill="x", pady=4)
                card.config(highlightbackground=c["border"], highlightthickness=1)

                hdr = tk.Frame(card, bg=c["card"])
                hdr.pack(fill="x")
                tk.Label(hdr, text=issue["icon"], font=("Segoe UI Emoji", 12), bg=c["card"]).pack(side="left")
                tk.Label(
                    hdr, text=issue["title"],
                    font=("Segoe UI Semibold", 10),
                    bg=c["card"], fg=c["text"]
                ).pack(side="left", padx=8)

                tk.Label(
                    card, text=issue["desc"],
                    font=("Segoe UI", 8),
                    bg=c["card"], fg=c["text_dim"],
                    wraplength=380, justify="left"
                ).pack(anchor="w", padx=24, pady=(2, 0))

            # Fix All button
            fix_btn = tk.Label(
                self.btn_frame, text="⚡  ล้างไฟล์ขยะและเพิ่มสปีดทันที (ปุ่มเดียว)",
                font=("Segoe UI Semibold", 10),
                bg=c["accent_dim"], fg="#ffffff",
                padx=20, pady=8, cursor="hand2"
            )
            fix_btn.pack(fill="x", pady=6)
            fix_btn.bind("<Button-1>", lambda e: self._fix_all())
            fix_btn.bind("<Enter>", lambda e: fix_btn.config(bg=c["accent"]))
            fix_btn.bind("<Leave>", lambda e: fix_btn.config(bg=c["accent_dim"]))

            # Skip button
            skip_btn = tk.Label(
                self.btn_frame, text="ข้ามการปรับแต่ง (ข้าพเจ้าปรับแต่งเอง)",
                font=("Segoe UI", 9),
                bg=c["panel_bg"], fg=c["text_dim"],
                cursor="hand2"
            )
            skip_btn.pack(pady=4)
            skip_btn.bind("<Button-1>", lambda e: self._finish())

    def _fix_all(self):
        c = config.COLORS
        self.scan_label.config(text="🔄 กำลังปรับแต่งและล้างแคช...", fg=c["warning"])
        threading.Thread(target=self._run_fixes, daemon=True).start()

    def _run_fixes(self):
        results = self.booster.boost_all()
        self.window.after(0, self._render_fix_complete)

    def _render_fix_complete(self):
        c = config.COLORS
        self.scan_label.config(text="✅ ปรับแต่งระบบสำเร็จแล้ว!", fg=c["success"])
        
        # Clear buttons
        for w in self.btn_frame.winfo_children():
            w.destroy()

        info = tk.Frame(self.issues_frame, bg=c["card"], padx=16, pady=16)
        # Clear issue list cards
        for w in self.issues_frame.winfo_children():
            w.destroy()
        
        info.pack(fill="both", expand=True, pady=10)
        info.config(highlightbackground=c["border"], highlightthickness=1)
        tk.Label(info, text="🎉 ปรับปรุงเรียบร้อย!", font=("Segoe UI Semibold", 10), bg=c["card"], fg=c["success"]).pack(pady=4)
        tk.Label(info, text="ระบบล้าง Shader cache, จัด Power plan สำเร็จ\n"
                              "กรุณากดเปิดใช้ Overlay ในเกม และบูสต์อีกครั้งเมื่อเปิดเกมจริง", font=("Segoe UI", 9), bg=c["card"], fg=c["text_dim"], justify="center").pack()

        self._add_start_button("เข้าสู่หน้าต่างหลัก →")

    def _add_start_button(self, text="เริ่มใช้งาน →"):
        c = config.COLORS
        start_btn = tk.Label(
            self.btn_frame, text=text,
            font=("Segoe UI Semibold", 10),
            bg=c["accent_dim"], fg="#fff",
            padx=16, pady=8, cursor="hand2"
        )
        start_btn.pack(fill="x", pady=6)
        start_btn.bind("<Button-1>", lambda e: self._finish())
        start_btn.bind("<Enter>", lambda e: start_btn.config(bg=c["accent"]))
        start_btn.bind("<Leave>", lambda e: start_btn.config(bg=c["accent_dim"]))

    def _finish(self):
        _save_first_run_complete()
        self.window.destroy()
        if self.on_complete:
            self.on_complete()


def is_first_run():
    """Check if this is the first time running the app"""
    config_path = config.get_config_path()
    return not os.path.exists(config_path)


def _save_first_run_complete():
    """Mark first run as complete"""
    config.save_config_file(first_run_complete=True)
