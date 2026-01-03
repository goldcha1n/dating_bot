from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
LOCATIONS_FILE = BASE_DIR / "data" / "locations_ua.json"

# Fallback мінімального довідника, якщо json не знайдено
_FALLBACK: Dict[str, Dict[str, List[str]]] = {
    "Kyiv City": {"Kyiv": ["Kyiv"]},
    "Kyiv Oblast": {
        "Kyiv Raion": ["Vyshneve", "Boiarka", "Irpin"],
        "Bila Tserkva Raion": ["Bila Tserkva", "Uzin", "Rokytne"],
    },
    "Lviv Oblast": {
        "Lviv Raion": ["Lviv", "Pustomyty", "Dubliany"],
        "Drohobych Raion": ["Drohobych", "Truskavets", "Boryslav"],
    },
    "Odesa Oblast": {
        "Odesa Raion": ["Odesa", "Chornomorsk", "Teplodar"],
        "Bilhorod-Dnistrovskyi Raion": ["Bilhorod-Dnistrovskyi", "Zatoka", "Serhiivka"],
    },
}


def _load_locations() -> Dict[str, Dict[str, List[str]]]:
    if LOCATIONS_FILE.exists():
        try:
            data = json.loads(LOCATIONS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {str(k): v for k, v in data.items()}
        except Exception:
            pass
    return _FALLBACK


@lru_cache(maxsize=1)
def get_locations() -> Dict[str, Dict[str, List[str]]]:
    return _load_locations()


def list_regions() -> List[str]:
    return sorted(get_locations().keys())


def list_districts(region: str) -> List[str]:
    return sorted(get_locations().get(region, {}).keys())


def list_settlements(region: str, district: str) -> List[str]:
    return sorted(get_locations().get(region, {}).get(district, []))


def normalize_choice(value: str, options: List[str]) -> Optional[str]:
    """Повертає точний варіант зі списку (case-insensitive) або None."""
    target = (value or "").strip().lower()
    for opt in options:
        if opt.lower() == target:
            return opt
    return None


def normalize_text(value: str) -> str:
    return (value or "").strip()


def default_location() -> dict:
    """Безпечні дефолти для заповнення нових полів."""
    return {
        "region": "Kyiv",
        "district": None,
        "hromada": None,
        "settlement": "Kyiv",
        "search_scope": "region",
    }
