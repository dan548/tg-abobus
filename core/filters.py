from __future__ import annotations
from pathlib import Path
from typing import Optional, List, Dict, Any
import json
from datetime import datetime, timezone

def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

def read_filters(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []

def append_criterion(path: Path, criterion: str) -> None:
    ensure_parent(path)
    data = read_filters(path)
    data.append({
        "criterion": criterion,
        "ts": datetime.now(timezone.utc).isoformat()
    })
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def read_latest_criterion(path: Path) -> Optional[str]:
    data = read_filters(path)
    if not data:
        return None
    last = data[-1]
    crit = last.get("criterion")
    return crit if isinstance(crit, str) and crit.strip() else None