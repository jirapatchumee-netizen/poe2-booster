"""
POE2 Booster — Auto-Update System
===================================
Checks GitHub Releases for new versions and self-updates the portable .exe.
Flow: Check API → Compare version → Download .exe → Batch self-replace → Restart

Supports two modes:
  - Frozen (.exe): Download → batch replace → auto-restart
  - Python dev:    Download to Downloads folder → user replaces manually
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


def get_release_url(version_tag):
    """Get the GitHub release page URL for a given version"""
    return f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}/releases/tag/{version_tag}"


def download_to_temp(download_url, callback=None):
    """
    Download the new .exe to a temp location next to the current exe.
    Returns the path to the downloaded file, or None on failure.
    Works in both frozen and non-frozen modes.
    """
    try:
        if getattr(sys, "frozen", False) or "__compiled__" in dir():
            dest_dir = os.path.dirname(sys.executable)
            exe_name = os.path.basename(sys.executable)
            dest_path = os.path.join(dest_dir, f"_update_{exe_name}")
        else:
            # Dev mode: download to user's Downloads folder
            downloads = os.path.join(os.path.expanduser("~"), "Downloads")
            os.makedirs(downloads, exist_ok=True)
            dest_path = os.path.join(downloads, "POE2Booster_NEW.exe")

        # Download with progress reporting
        def reporthook(count, block_size, total_size):
            if total_size > 0 and callback:
                percent = min(100, int(count * block_size * 100 / total_size))
                callback("downloading", f"กำลังดาวน์โหลด... {percent}%")

        if callback:
            callback("downloading", "กำลังดาวน์โหลด... 0%")

        urllib.request.urlretrieve(download_url, dest_path, reporthook=reporthook)

        # Verify downloaded file is reasonable size (> 5MB)
        file_size = os.path.getsize(dest_path)
        if file_size < 5 * 1024 * 1024:
            os.remove(dest_path)
            if callback:
                callback("error", "ไฟล์ดาวน์โหลดมีขนาดเล็กเกินไป อาจเสียหาย")
            return None

        if callback:
            size_mb = file_size / (1024 * 1024)
            callback("downloaded", f"ดาวน์โหลดเสร็จ ({size_mb:.1f} MB)")

        return dest_path

    except Exception as e:
        if callback:
            callback("error", f"ดาวน์โหลดล้มเหลว: {e}")
        return None


def apply_update_and_restart(temp_exe_path, callback=None):
    """
    Create a batch script to replace the current .exe and restart.
    Only works when running as frozen .exe.
    Returns True if the restart was initiated.
    """
    if not (getattr(sys, "frozen", False) or "__compiled__" in dir()):
        if callback:
            callback("error", "Auto-restart ใช้ได้เฉพาะไฟล์ .exe เท่านั้น")
        return False

    try:
        current_exe = sys.executable
        exe_dir = os.path.dirname(current_exe)

        # Create batch script with multiple retries for reliable replacement
        batch_path = os.path.join(exe_dir, "_poe2booster_update.bat")
        batch = f'''@echo off
chcp 65001 >nul 2>&1
title POE2 Booster — Updating...

echo.
echo  ========================================
echo   POE2 Booster - Auto Update
echo  ========================================
echo.

REM Wait for the app to fully close
echo  [1/4] Waiting for app to close...
set RETRIES=0

:WAIT_LOOP
tasklist /FI "PID eq %PPID%" 2>nul | find /i "POE2Booster" >nul 2>&1
if %ERRORLEVEL%==0 (
    timeout /t 1 /nobreak >nul
    set /a RETRIES+=1
    if %RETRIES% lss 10 goto WAIT_LOOP
)
timeout /t 2 /nobreak >nul

REM Delete old exe with retries
echo  [2/4] Removing old version...
set RETRIES=0

:DELETE_LOOP
del /f /q "{current_exe}" 2>nul
if exist "{current_exe}" (
    set /a RETRIES+=1
    if %RETRIES% lss 5 (
        echo  Retry %RETRIES%...
        timeout /t 2 /nobreak >nul
        goto DELETE_LOOP
    )
    echo  WARNING: Could not delete old file, forcing move...
)

REM Move new exe into place
echo  [3/4] Installing new version...
move /y "{temp_exe_path}" "{current_exe}"
if %ERRORLEVEL% neq 0 (
    echo  ERROR: Failed to install update!
    echo  The new file is at: {temp_exe_path}
    pause
    goto END
)

REM Start the updated app
echo  [4/4] Starting updated app...
echo.
echo  Update complete!
timeout /t 1 /nobreak >nul
start "" "{current_exe}"

:END
REM Clean up this batch script
del "%~f0" 2>nul
'''
        with open(batch_path, "w", encoding="utf-8") as f:
            f.write(batch)

        if callback:
            callback("installing", "กำลังเตรียมรีสตาร์ท...")

        # Launch the updater batch script (visible briefly so user sees progress)
        subprocess.Popen(
            ["cmd.exe", "/c", batch_path],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        if callback:
            callback("restarting", "อัปเดตสำเร็จ! กำลังรีสตาร์ท...")

        return True

    except Exception as e:
        if callback:
            callback("error", f"รีสตาร์ทล้มเหลว: {e}")
        return False

