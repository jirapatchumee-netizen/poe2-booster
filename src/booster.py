"""
POE2 Booster — Boost Engine
All system optimization actions
"""

import os
import subprocess
import time
import psutil


def clear_shader_cache():
    """Clear DirectX/NVIDIA/AMD shader caches"""
    local = os.environ.get("LOCALAPPDATA", "")
    paths = [
        os.path.join(local, "D3DSCache"),
        os.path.join(local, "NVIDIA", "DXCache"),
        os.path.join(local, "NVIDIA", "GLCache"),
        os.path.join(local, "AMD", "DxCache"),
        os.path.join(local, "AMD", "GLCache"),
    ]
    total = 0
    for path in paths:
        if os.path.exists(path):
            for root, dirs, files in os.walk(path):
                for f in files:
                    fp = os.path.join(root, f)
                    try:
                        total += os.path.getsize(fp)
                        os.remove(fp)
                    except Exception:
                        pass
    return total / (1024 * 1024)  # Return MB cleared


def set_high_performance():
    """Set Windows power plan to High Performance"""
    try:
        subprocess.run(
            ["powercfg", "/setactive", "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"],
            capture_output=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return True
    except Exception:
        return False


def kill_background_apps():
    """Kill unnecessary background apps (preserves Discord & Overwolf)"""
    targets = [
        "Teams.exe", "ms-teams.exe", "mscopilot.exe",
        "OneDrive.exe", "AdobeCollabSync.exe",
        "EpicGamesLauncher.exe", "RiotClientServices.exe", "msedge.exe",
    ]
    killed = 0
    for name in targets:
        try:
            r = subprocess.run(
                ["taskkill", "/f", "/im", name],
                capture_output=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if r.returncode == 0:
                killed += 1
        except Exception:
            pass
    return killed


def clear_standby_ram():
    """Clear standby memory"""
    try:
        before = psutil.virtual_memory().available
        subprocess.run(
            ["rundll32.exe", "advapi32.dll,ProcessIdleTasks"],
            capture_output=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        import time
        time.sleep(0.5)  # Give Windows a moment to release memory
        after = psutil.virtual_memory().available
        freed_mb = max(0, (after - before)) / (1024 * 1024)
        return freed_mb
    except Exception:
        return 0


def flush_dns():
    """Flush Windows DNS resolver cache — reduces DNS lookup lag in online games"""
    try:
        r = subprocess.run(
            ["ipconfig", "/flushdns"],
            capture_output=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return r.returncode == 0
    except Exception:
        return False


def clear_temp_files():
    """Clear Windows TEMP files (safely skips locked files)"""
    temp_dirs = [
        os.environ.get("TEMP", ""),
        os.environ.get("TMP", ""),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Temp"),
    ]
    total = 0
    seen = set()
    for temp_dir in temp_dirs:
        real = os.path.realpath(temp_dir) if temp_dir else ""
        if not real or real in seen or not os.path.exists(real):
            continue
        seen.add(real)
        for root, dirs, files in os.walk(real, topdown=False):
            for f in files:
                fp = os.path.join(root, f)
                try:
                    size = os.path.getsize(fp)
                    os.remove(fp)
                    total += size
                except Exception:
                    pass  # Skip locked / in-use files
            # Try removing empty subdirectories too
            for d in dirs:
                try:
                    os.rmdir(os.path.join(root, d))
                except Exception:
                    pass
    return total / (1024 * 1024)  # Return MB cleared


def set_poe2_high_priority():
    """Set POE2 process to high priority if running"""
    for proc in psutil.process_iter(["name"]):
        try:
            name = proc.info["name"]
            if name and "PathOfExile" in name:
                proc.nice(psutil.HIGH_PRIORITY_CLASS)
                return True
        except Exception:
            pass
    return False


def boost_all():
    """Run all safe optimizations in one click (no apps are closed)"""
    results = {}

    # 1. Clear Shader Cache (DirectX/NVIDIA/AMD)
    results["cache_mb"] = clear_shader_cache()

    # 2. Clear Windows TEMP files
    results["temp_mb"] = clear_temp_files()

    # 3. Flush Standby RAM
    results["ram_freed_mb"] = clear_standby_ram()

    # 4. Set POE2 process to High Priority (if running)
    results["priority_set"] = set_poe2_high_priority()

    # 5. Flush DNS cache
    results["dns_flushed"] = flush_dns()

    # 6. Set High Performance power plan
    results["power_set"] = set_high_performance()

    return results


def get_gpu_stats():
    """Get GPU temperature and VRAM usage via nvidia-smi"""
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=temperature.gpu,utilization.memory",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if r.returncode == 0:
            parts = r.stdout.strip().split(",")
            return float(parts[0].strip()), float(parts[1].strip())
    except Exception:
        pass
    return 0, 0


def scan_system_issues():
    """Scan system for shader cache bloat — used in First-Time Wizard"""
    issues = []

    # Check shader cache size
    local = os.environ.get("LOCALAPPDATA", "")
    cache_size = 0
    paths = [
        os.path.join(local, "D3DSCache"),
        os.path.join(local, "NVIDIA", "DXCache"),
        os.path.join(local, "NVIDIA", "GLCache"),
        os.path.join(local, "AMD", "DxCache"),
        os.path.join(local, "AMD", "GLCache"),
    ]
    for path in paths:
        if os.path.exists(path):
            for root, dirs, files in os.walk(path):
                for f in files:
                    try:
                        cache_size += os.path.getsize(os.path.join(root, f))
                    except Exception:
                        pass
    cache_mb = cache_size / (1024 * 1024)
    if cache_mb > 50:  # Show issue if cache is larger than 50MB
        issues.append({
            "icon": "🗑️",
            "title": f"พบไฟล์ Shader Cache {cache_mb:.0f} MB",
            "desc": "ไฟล์ขยะสะสมในระบบเครื่องของคุณ ทำให้เกิดอาการสะดุดและเฟรมร่วงในเกม",
            "fix": "clear_shader_cache",
        })

    return issues
