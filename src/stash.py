"""
POE2 Booster — Stash Module
Handles fetching stash tabs and items from Path of Exile character-window API using POESESSID.
"""

import urllib.request
import urllib.parse
import json
import time

BASE_URL = "https://www.pathofexile.com/character-window/get-stash-items"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) POE2Booster/1.4.3"


def fetch_stash_data(poesessid, account_name, league="Standard", tab_index=0, tabs=1):
    """
    Fetch stash items and metadata for a specific tab.
    If tabs=1, returns full list of tabs in the response as well.
    """
    if not poesessid or not account_name:
        return {"error": "กรุณาระบุ Account Name และ POESESSID ในหน้าตั้งค่าขั้นสูงก่อน"}

    params = {
        "accountName": account_name,
        "league": league,
        "tabIndex": tab_index,
        "tabs": tabs
    }
    
    url = f"{BASE_URL}?{urllib.parse.urlencode(params)}"
    
    req = urllib.request.Request(url)
    req.add_header("User-Agent", USER_AGENT)
    req.add_header("Cookie", f"POESESSID={poesessid}")
    
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                return {"success": True, "data": data}
            else:
                return {"error": f"HTTP Error {response.status}"}
    except urllib.error.HTTPError as e:
        if e.code == 403 or e.code == 401:
            return {"error": "POESESSID ไม่ถูกต้อง หรือหมดอายุแล้ว กรุณารีเฟรชคุกกี้ใหม่"}
        elif e.code == 429:
            return {"error": "เรียกข้อมูลถี่เกินไป (Rate Limit) กรุณารอ 1 นาทีแล้วลองใหม่"}
        elif e.code == 400:
            return {"error": "Account Name หรือชื่อ League ไม่ถูกต้อง"}
        else:
            return {"error": f"HTTP Error {e.code}"}
    except Exception as e:
        return {"error": f"เชื่อมต่อล้มเหลว: {str(e)}"}


def get_stash_tabs_list(poesessid, account_name, league="Standard"):
    """Get all available stash tabs metadata (id, name, type, index, color)"""
    res = fetch_stash_data(poesessid, account_name, league=league, tab_index=0, tabs=1)
    if not res.get("success"):
        return res
    
    tabs_data = res["data"].get("tabs", [])
    tabs_list = []
    for t in tabs_data:
        tabs_list.append({
            "index": t.get("i", 0),
            "name": t.get("n", f"Tab {t.get('i', 0)}"),
            "type": t.get("type", "NormalStash"),
            "color": t.get("colour", {}),
            "hidden": t.get("hidden", False)
        })
    return {"success": True, "tabs": tabs_list, "raw_data": res["data"]}
