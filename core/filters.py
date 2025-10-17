from __future__ import annotations
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
import json
from datetime import datetime, timezone

UserId = Union[int, str]


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _read_raw(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def read_filters(path: Path) -> List[Dict[str, Any]]:
    """
    Возвращает весь сырой список записей как есть.
    Элемент имеет схему:
      {
        "criterion": str,
        "ts": ISO8601 str,
        "user_id": int|str   # может отсутствовать у старых записей
      }
    """
    return _read_raw(path)


def append_criterion(path: Path, user_id: Optional[UserId], criterion: str) -> None:
    """
    Добавляет запись с критерием для конкретного пользователя.
    """
    ensure_parent(path)
    data = _read_raw(path)
    entry = {
        "criterion": criterion,
        "ts": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
    }
    data.append(entry)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def read_latest_criterion(path: Path, user_id: UserId) -> Optional[str]:
    """
    Возвращает последний критерий, принадлежащий указанному user_id.
    Старые записи без поля user_id игнорируются.
    Поиск идёт с конца для эффективности.
    """
    data = _read_raw(path)
    for item in reversed(data):
        if not isinstance(item, dict):
            continue
        uid = item.get("user_id")
        if uid == user_id:
            crit = item.get("criterion")
            if isinstance(crit, str) and crit.strip():
                return crit
    return None
