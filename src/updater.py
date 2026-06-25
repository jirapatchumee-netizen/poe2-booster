"""
POE2 Booster — Auto-Update System
===================================
Checks GitHub Releases for new versions and self-updates the portable .exe.
Flow: Check API → Compare version → Download .exe → Batch self-replace → Restart
"""

import os
import sys
import json
import subprocess
import urllib.request

GITHUB_USER = "jirapatchumee-netizen"
GITHUB_REPO = "poe2-booster"
API_URL = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/releases/latest"


def _parse_version(v_str):
    """Parse version string '1.1.0' or 'v1.1.0' to comparable tuple"""
    return tuple(int(x) for x in v_str.lstrip("v").split("."))


def check_for_update(current_version):
    """
    Check GitHub Releases for a newer version.
    Returns dict with update info if available, None otherwise.
    """
    try:
        req = urllib.request.Request(
            API_URL,
            headers={
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "POE2Booster-Updater",
            },
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        latest_tag = data.get("tag_name", "")
        if not latest_tag:
            return None

        latest = _parse_version(latest_tag)
        current = _parse_version(current_version)

        if latest > current:
            # Find .exe in release assets (skip installer/setup files)
            for asset in data.get("assets", []):
                name = asset.get("name", "")
                if name.lower().endswith(".exe") and "setup" not in name.lower():
                    return {
                        "version": latest_tag,
                        "download_url": asset["browser_download_url"],
                        "asset_name": name,
                        "size": asset.get("size", 0),
                        "notes": data.get("body", ""),
                    }
        return None
    except Exception:
        return None


def download_and_replace(download_url, callback=None):
    """
    Download new .exe and create a batch script to replace the current one.
    Returns True if the batch script was launched (app should exit after).
    """
    # Only works when running as frozen .exe
    if not getattr(sys, "frozen", False):
        if callback:
            callback("error", "Auto-update ใช้ได้เฉพาะในโหมด .exe เท่านั้น")
        return False

    temp_exe = None
    try:
        current_exe = sys.executable
        exe_dir = os.path.dirname(current_exe)
        exe_name = os.path.basename(current_exe)
        temp_exe = os.path.join(exe_dir, f"_update_{exe_name}")

        # Download with progress reporting
        def reporthook(count, block_size, total_size):
            if total_size > 0 and callback:
                percent = min(100, int(count * block_size * 100 / total_size))
                callback("downloading", f"กำลังดาวน์โหลด... {percent}%")

        if callback:
            callback("downloading", "กำลังดาวน์โหลด... 0%")

        urllib.request.urlretrieve(download_url, temp_exe, reporthook=reporthook)

        # Verify downloaded file is reasonable size (> 5MB)
        file_size = os.path.getsize(temp_exe)
        if file_size < 5 * 1024 * 1024:
            os.remove(temp_exe)
            if callback:
                callback("error", "ไฟล์ดาวน์โหลดมีขนาดเล็กเกินไป")
            return False

        if callback:
            size_mb = file_size / (1024 * 1024)
            callback("installing", f"ดาวน์โหลดเสร็จ ({size_mb:.1f} MB) กำลังติดตั้ง...")

        # Create batch script for self-replace after app exits
        batch_path = os.path.join(exe_dir, "_poe2booster_update.bat")
        batch = f'''@echo off
title POE2 Booster — Updating...
echo.
echo  ========================================
echo   POE2 Booster - Auto Update
echo  ========================================
echo.
echo  Waiting for app to close...
timeout /t 2 /nobreak >nul
del "{current_exe}" 2>nul
if exist "{current_exe}" (
    echo  Retrying...
    timeout /t 3 /nobreak >nul
    del "{current_exe}" 2>nul
)
move /y "{temp_exe}" "{current_exe}"
echo.
echo  Update complete! Restarting...
timeout /t 1 /nobreak >nul
start "" "{current_exe}"
del "%~f0"
'''
        with open(batch_path, "w", encoding="utf-8") as f:
            f.write(batch)

        # Launch the updater batch script
        subprocess.Popen(
            ["cmd.exe", "/c", batch_path],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        if callback:
            callback("restarting", "อัปเดตสำเร็จ! กำลังรีสตาร์ท...")

        return True

    except Exception as e:
        # Clean up temp file on error
        if temp_exe:
            try:
                if os.path.exists(temp_exe):
                    os.remove(temp_exe)
            except Exception:
                pass
        if callback:
            callback("error", f"อัปเดตล้มเหลว: {e}")
        return False
