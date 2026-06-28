"""
POE2 Booster — Pricer Module
Fetches real-time item prices from poe.ninja API and calculates stash valuations.
"""

import urllib.request
import urllib.parse
import json
import time

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) POE2Booster/1.4.3"

# In-memory price cache (league -> {timestamp, prices_dict, divine_price})
PRICE_CACHE = {}
CACHE_TTL = 600  # 10 minutes


def fetch_poe_ninja_prices(league="Standard"):
    """
    Fetch currency and item prices from poe.ninja for a given league.
    Returns a dictionary mapping item names to their Chaos value.
    """
    now = time.time()
    if league in PRICE_CACHE:
        cache_entry = PRICE_CACHE[league]
        if now - cache_entry["time"] < CACHE_TTL:
            return cache_entry

    prices = {}
    divine_price = 150.0  # fallback default

    # 1. Fetch Currency Overview
    curr_url = f"https://poe.ninja/api/data/currencyoverview?league={urllib.parse.quote(league)}&type=Currency"
    try:
        req = urllib.request.Request(curr_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                for lines in data.get("lines", []):
                    name = lines.get("currencyTypeName")
                    chaos_val = lines.get("chaosEquivalent", 0)
                    if name and chaos_val:
                        prices[name] = float(chaos_val)
                        if name == "Divine Orb":
                            divine_price = float(chaos_val)
    except Exception:
        pass

    # Standard Chaos Orb is always 1 Chaos
    prices["Chaos Orb"] = 1.0

    # 2. Fetch Item Overviews (Fragment, Scarab, DivinationCard, Oil, Essence)
    item_types = ["Fragment", "Scarab", "DivinationCard", "Oil", "Essence", "UniqueJewel", "UniqueWeapon", "UniqueArmour", "UniqueAccessory"]
    for itype in item_types:
        item_url = f"https://poe.ninja/api/data/itemoverview?league={urllib.parse.quote(league)}&type={itype}"
        try:
            req = urllib.request.Request(item_url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=8) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    for lines in data.get("lines", []):
                        name = lines.get("name")
                        chaos_val = lines.get("chaosValue", 0)
                        if name and chaos_val:
                            prices[name] = float(chaos_val)
        except Exception:
            pass

    result = {
        "time": now,
        "prices": prices,
        "divine_price": divine_price
    }
    PRICE_CACHE[league] = result
    return result


def calculate_stash_valuation(items_list, price_data):
    """
    Calculate valuation for a list of items returned by PoE Stash API.
    Returns summary dict with total chaos, total divine, and detailed items list sorted by value.
    """
    prices = price_data.get("prices", {})
    divine_price = price_data.get("divine_price", 150.0)

    evaluated_items = []
    total_chaos = 0.0

    for item in items_list:
        # Item name determination
        name = item.get("typeLine", "")
        base_type = item.get("baseType", "")
        name_clean = name if name else base_type
        
        stack_size = item.get("stackSize", 1)
        
        # Unit price lookup
        unit_price = prices.get(name_clean, 0.0)
        if unit_price == 0.0 and base_type:
            unit_price = prices.get(base_type, 0.0)
            
        total_item_val = unit_price * stack_size
        total_chaos += total_item_val

        if total_item_val > 0:
            evaluated_items.append({
                "name": name_clean,
                "stack": stack_size,
                "unit_price": unit_price,
                "total_price": total_item_val,
                "icon": item.get("icon", "")
            })

    # Sort items by total value descending
    evaluated_items.sort(key=lambda x: x["total_price"], reverse=True)

    total_divine = total_chaos / divine_price if divine_price > 0 else 0.0

    return {
        "total_chaos": total_chaos,
        "total_divine": total_divine,
        "divine_price": divine_price,
        "items_count": len(items_list),
        "valuable_items": evaluated_items
    }
