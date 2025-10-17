# storage/user_chats.py
import json
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict

_DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))
_DATA_DIR.mkdir(parents=True, exist_ok=True)
_FILE = _DATA_DIR / "user_chats.jsonl"

@dataclass
class ChatRecord:
    ts: int
    user_id: int
    chat_username: str  # допускаем username (@name), numeric id (12345) или invite ссылку

def _iter_all() -> List[ChatRecord]:
    if not _FILE.exists():
        return []
    items: List[ChatRecord] = []
    with _FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                items.append(ChatRecord(**d))
            except Exception:
                # файл переживёт многое, мы — нет
                continue
    return items

def list_user_chats(user_id: int) -> List[ChatRecord]:
    return [rec for rec in _iter_all() if rec.user_id == user_id]

def add_chat(user_id: int, chat_identifier: str) -> ChatRecord:
    rec = ChatRecord(ts=int(time.time()), user_id=user_id, chat_username=chat_identifier.strip())
    # атомарная дозапись
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = _FILE.with_suffix(".jsonl.tmp")
    with tmp.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(rec), ensure_ascii=False) + "\n")
    # склеиваем tmp в основной файл, чтобы не ловить гонки
    with _FILE.open("a", encoding="utf-8") as out, tmp.open("r", encoding="utf-8") as inp:
        for line in inp:
            out.write(line)
    try:
        tmp.unlink()
    except FileNotFoundError:
        pass
    return rec
