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

    # 7. Optimize conflicting overlay priorities (Discord/Overwolf)
    results["overlays_optimized"] = optimize_overlay_priorities()

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


def get_poe2_config_path():
    """Locate the POE2 config file path dynamically"""
    try:
        import ctypes.wintypes
        CSIDL_PERSONAL = 5       # My Documents
        SHGFP_TYPE_CURRENT = 0
        buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
        ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_PERSONAL, None, SHGFP_TYPE_CURRENT, buf)
        docs = buf.value
        path = os.path.join(docs, "My Games", "Path of Exile 2", "poe2_production_Config.ini")
        if os.path.exists(path):
            return path
    except Exception:
        pass
    # Fallback to standard path
    userprofile = os.environ.get("USERPROFILE", "")
    if userprofile:
        path = os.path.join(userprofile, "Documents", "My Games", "Path of Exile 2", "poe2_production_Config.ini")
        if os.path.exists(path):
            return path
    return None


def get_poe2_config_optimizations():
    """Get the mapping of optimal settings for POE2"""
    return {
        "DISPLAY": {
            "renderer_type": "Vulkan",
            "use_dynamic_resolution": "true",
            "water_detail": "0",
            "shadow_type": "Low",
            "light_quality": "0",
            "global_illumination_detail": "0",
            "texture_quality": "TextureQualityLow",
            "use_dynamic_particle_culling2": "true",
        },
        "SOUND": {
            "channel_count": "low",
            "reverb_enabled2": "false",
            "music_volume2": "0",
            "ambient_sound_volume2": "0",
            "dialogue_sound_volume2": "0",
        },
        "GENERAL": {
            "engine_multithreading_mode": "enabled",
        }
    }


def check_poe2_config_status(file_path):
    """Check which recommended settings are already applied. Returns (is_fully_optimized, current_values)"""
    if not file_path or not os.path.exists(file_path):
        return False, {}

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        optimizations = get_poe2_config_optimizations()
        current_values = {}
        current_section = None

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                current_section = stripped[1:-1]
                continue
            if current_section in optimizations and "=" in stripped:
                key, val = stripped.split("=", 1)
                key = key.strip()
                val = val.strip()
                if key in optimizations[current_section]:
                    if current_section not in current_values:
                        current_values[current_section] = {}
                    current_values[current_section][key] = val

        # Check completeness
        fully_optimized = True
        for sec, keys in optimizations.items():
            for key, opt_val in keys.items():
                curr_val = current_values.get(sec, {}).get(key)
                if curr_val != opt_val:
                    fully_optimized = False
                    break

        return fully_optimized, current_values
    except Exception:
        return False, {}


def optimize_poe2_config(file_path):
    """Safely edit the POE2 ini file to apply optimal settings"""
    if not file_path or not os.path.exists(file_path):
        return False, "ไม่พบไฟล์ตั้งค่าของเกม"

    try:
        # Create a backup first
        backup_path = file_path + ".backup"
        import shutil
        shutil.copy2(file_path, backup_path)
        
        # Read current lines
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        
        optimizations = get_poe2_config_optimizations()
        
        # Parse and modify
        new_lines = []
        current_section = None
        applied = {sec: set() for sec in optimizations}
        
        for line in lines:
            stripped = line.strip()
            # Detect section
            if stripped.startswith("[") and stripped.endswith("]"):
                # If we are leaving a section, and there are missing optimizations, append them
                if current_section in optimizations:
                    for key, val in optimizations[current_section].items():
                        if key not in applied[current_section]:
                            new_lines.append(f"{key}={val}\n")
                            applied[current_section].add(key)
                
                current_section = stripped[1:-1]
                new_lines.append(line)
                continue
            
            # If we are inside an optimization section, check if this line is a key to optimize
            if current_section in optimizations and "=" in stripped:
                key, val = stripped.split("=", 1)
                key = key.strip()
                if key in optimizations[current_section]:
                    opt_val = optimizations[current_section][key]
                    new_lines.append(f"{key}={opt_val}\n")
                    applied[current_section].add(key)
                    continue
            
            new_lines.append(line)
        
        # Handle the very last section if it was one of our optimized sections
        if current_section in optimizations:
            for key, val in optimizations[current_section].items():
                if key not in applied[current_section]:
                    new_lines.append(f"{key}={val}\n")
                    applied[current_section].add(key)
        
        # If any section was missing completely, append the section and its values
        for sec, keys in optimizations.items():
            if not any(k in applied[sec] for k in keys):
                # Section didn't exist or wasn't processed
                new_lines.append(f"\n[{sec}]\n")
                for key, val in keys.items():
                    new_lines.append(f"{key}={val}\n")
        
        # Write back
        with open(file_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
            
        return True, "สำรองไฟล์เดิมและปรับแต่งสำเร็จ!"
    except Exception as e:
        return False, f"เกิดข้อผิดพลาด: {str(e)}"


def revert_poe2_config(file_path):
    """Revert the POE2 config file to the backup version"""
    backup_path = file_path + ".backup"
    if not os.path.exists(backup_path):
        return False, "ไม่พบไฟล์สำรอง (.backup)"
    try:
        import shutil
        shutil.copy2(backup_path, file_path)
        return True, "คืนค่าการตั้งค่าเดิมสำเร็จ!"
    except Exception as e:
        return False, f"เกิดข้อผิดพลาด: {str(e)}"


def optimize_overlay_priorities():
    """Lower the priority of overlay processes to BELOW_NORMAL to reduce stuttering in POE2"""
    targets = ["Discord.exe", "Overwolf.exe", "OverwolfHelper.exe", "Awakened PoE Trade.exe", "AwakenedPoETrade.exe"]
    optimized_count = 0
    for proc in psutil.process_iter(["name"]):
        try:
            name = proc.info["name"]
            if name and any(t.lower() == name.lower() for t in targets):
                # Set priority to BELOW_NORMAL
                proc.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
                optimized_count += 1
        except Exception:
            pass
    return optimized_count


def scan_overlay_conflicts():
    """Scan running processes for active overlays. Returns list of dicts with name, display_name, and tip"""
    conflicts = []
    targets = {
        "Discord.exe": {
            "name": "Discord",
            "tip": "แนะนำให้ปิด 'Discord Overlay' ในตั้งค่าของ Discord (Settings -> Game Overlay) เพื่อความเสถียร"
        },
        "Overwolf.exe": {
            "name": "Overwolf",
            "tip": "แนะนำให้เปิดเฉพาะตัวเช็กราคา และหลีกเลี่ยงการกดเช็กราคาขณะดึงฝูงมอนสเตอร์"
        },
        "OverwolfHelper.exe": {
            "name": "Overwolf Helper",
            "tip": "แนะนำให้เปิดเฉพาะตัวเช็กราคา และหลีกเลี่ยงการกดเช็กราคาขณะดึงฝูงมอนสเตอร์"
        },
        "Awakened PoE Trade.exe": {
            "name": "Awakened PoE Trade",
            "tip": "หลีกเลี่ยงการกดเช็กราคาขณะดึงฝูงมอนสเตอร์เพื่อป้องกันปัญหา CPU spikes และเฟรมร่วง"
        },
        "AwakenedPoETrade.exe": {
            "name": "Awakened PoE Trade",
            "tip": "หลีกเลี่ยงการกดเช็กราคาขณะดึงฝูงมอนสเตอร์เพื่อป้องกันปัญหา CPU spikes และเฟรมร่วง"
        }
    }
    
    seen = set()
    for proc in psutil.process_iter(["name"]):
        try:
            name = proc.info["name"]
            if name and name.lower() in (t.lower() for t in targets):
                matched_key = next(k for k in targets if k.lower() == name.lower())
                disp_name = targets[matched_key]["name"]
                if disp_name not in seen:
                    seen.add(disp_name)
                    conflicts.append({
                        "process_name": name,
                        "display_name": disp_name,
                        "tip": targets[matched_key]["tip"]
                    })
        except Exception:
            pass
    return conflicts


