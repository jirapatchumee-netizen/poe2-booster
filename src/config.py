"""
POE2 Booster — Config Module
Handles app metadata, color themes, and global settings persistence.
ฟีเจอร์ทั้งหมดเปิดใช้งานฟรี — ไม่ต้องใช้ License Key
"""

import os
import json

APP_NAME = "POE2 Booster"
APP_VERSION = "1.4.3"  # ปลดล็อกฟีเจอร์ทั้งหมดให้ใช้ฟรี
APP_AUTHOR = "POE2 Booster Team"
APP_WEBSITE = "https://poe2booster.com"
HOTKEY = "F4"

# สถานะ Pro — เปิดถาวร (ฟีเจอร์ทุกตัวปลดล็อกแล้ว)
IS_PRO = True
CURRENT_THEME = "blue"
POESESSID = ""
ACCOUNT_NAME = ""

# ── Themes Palette ───────────────────────────────────────
THEMES = {
    "blue": {
        "bar_bg": "#0f141c",
        "bar_border": "#21262d",
        "panel_bg": "#0d1117",
        "card": "#161b22",
        "card_hover": "#1f242c",
        "accent": "#58a6ff",
        "accent_dim": "#1f6feb",
        "text": "#e6edf3",
        "text_dim": "#8b949e",
        "border": "#30363d",
        "separator": "#21262d",
        "success": "#3fb950",
        "warning": "#d29922",
        "danger": "#f85149",
        "pro_badge": "#8a2be2",
    },
    "purple": {
        "bar_bg": "#120e1e",
        "bar_border": "#2c1a4d",
        "panel_bg": "#0c0816",
        "card": "#171224",
        "card_hover": "#251d38",
        "accent": "#d380ff",
        "accent_dim": "#a855f7",
        "text": "#f3e8ff",
        "text_dim": "#a78bfa",
        "border": "#3b226e",
        "separator": "#2c1a4d",
        "success": "#34d399",
        "warning": "#fbbf24",
        "danger": "#f87171",
        "pro_badge": "#ec4899",
    },
    "amber": {
        "bar_bg": "#14110b",
        "bar_border": "#33220f",
        "panel_bg": "#0f0c08",
        "card": "#18140e",
        "card_hover": "#282015",
        "accent": "#ffb020",
        "accent_dim": "#d97706",
        "text": "#fef3c7",
        "text_dim": "#f59e0b",
        "border": "#451a03",
        "separator": "#33220f",
        "success": "#10b981",
        "warning": "#fbbf24",
        "danger": "#ef4444",
        "pro_badge": "#d97706",
    },
    "green": {
        "bar_bg": "#0a120c",
        "bar_border": "#1a3322",
        "panel_bg": "#050d06",
        "card": "#0d1a0f",
        "card_hover": "#162e1a",
        "accent": "#4ade80",
        "accent_dim": "#16a34a",
        "text": "#f0fdf4",
        "text_dim": "#4ade80",
        "border": "#1f5c35",
        "separator": "#1a3322",
        "success": "#22c55e",
        "warning": "#eab308",
        "danger": "#ef4444",
        "pro_badge": "#10b981",
    }
}

COLORS = THEMES[CURRENT_THEME]


def get_config_path():
    """Get the path to the app's config file in AppData"""
    appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
    return os.path.join(appdata, "POE2Booster", "config.json")


def load_config():
    """โหลดการตั้งค่าจากไฟล์ config"""
    global CURRENT_THEME, COLORS, POESESSID, ACCOUNT_NAME
    path = get_config_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            theme = data.get("theme", "blue")
            if theme in THEMES:
                CURRENT_THEME = theme
                COLORS = THEMES[theme]

            POESESSID = data.get("poesessid", "")
            ACCOUNT_NAME = data.get("account_name", "")
            return data
        except Exception:
            pass
    return {}


def save_config_file(theme=None, auto_start=None, first_run_complete=True, poesessid=None, account_name=None, **kwargs):
    """บันทึกการตั้งค่าลงไฟล์ config"""
    global CURRENT_THEME, COLORS, POESESSID, ACCOUNT_NAME

    path = get_config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)

    # โหลดข้อมูลเดิมเพื่อ merge
    data = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass

    if theme is not None:
        if theme in THEMES:
            data["theme"] = theme
            CURRENT_THEME = theme
            COLORS = THEMES[theme]

    if poesessid is not None:
        data["poesessid"] = poesessid
        POESESSID = poesessid

    if account_name is not None:
        data["account_name"] = account_name
        ACCOUNT_NAME = account_name

    if auto_start is not None:
        data["auto_start"] = auto_start

    data["first_run_complete"] = first_run_complete
    data["version"] = APP_VERSION

    # Merge ค่าเพิ่มเติม (Auto-Boost, Streamer mode ฯลฯ)
    for k, v in kwargs.items():
        if v is not None:
            data[k] = v

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        return True
    except Exception:
        return False


def switch_theme(theme_name):
    """เปลี่ยนธีมสีแบบ Dynamic และบันทึก config"""
    global CURRENT_THEME, COLORS
    if theme_name in THEMES:
        CURRENT_THEME = theme_name
        COLORS = THEMES[theme_name]
        save_config_file(theme=theme_name)
        return True
    return False


# โหลดอัตโนมัติเมื่อ import
load_config()
