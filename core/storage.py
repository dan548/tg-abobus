from __future__ import annotations
from pathlib import Path
from typing import Any, Iterable, Iterator
import json
import tempfile
import time
import os
from config import CHATS_FILE, QUERIES_FILE

# ---------- чтение ----------

def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Загрузить все записи JSONL в память."""
    if not path.exists():
        return []
    data: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if isinstance(obj, dict):
                data.append(obj)
            else:
                # если вдруг лежит не объект — пропускаем, не устраиваем драму
                continue
    return data

def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    """Ленивый итератор по записям JSONL."""
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    yield obj

# ---------- запись ----------

def save_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    """Атомарно перезаписать файл всем набором записей."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # пишем во временный файл и заменяем — без полубитых файлов
    with tempfile.NamedTemporaryFile("w", delete=False, dir=path.parent, encoding="utf-8") as tmp:
        tmp_name = tmp.name
        for rec in records:
            tmp.write(json.dumps(rec, ensure_ascii=False))
            tmp.write("\n")
    os.replace(tmp_name, path)

def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    """Безопасно дописать одну запись в конец файла."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False))
        f.write("\n")

def get_user_chats(user_id: int) -> list[dict[str, Any]]:
    dataList = load_jsonl(Path(CHATS_FILE))
    res = []
    for item in dataList:
        if item.get("user_id") == user_id:
            res.append(item)
    return res

def add_user_chat(user_id: int, chat_id: str) -> None:
    item = {
        "ts": int(time.time()),
        "user_id": user_id,
        "chat": chat_id.strip(),
    }
    arr = get_user_chats(user_id)
    if not any(x.get("chat") == item["chat"] for x in arr):
        append_jsonl(Path(CHATS_FILE), item)

def get_user_queries(user_id: int) -> list[dict[str, Any]]:
    dataList = load_jsonl(Path(QUERIES_FILE))
    res = []
    for item in dataList:
        if item.get("user_id") == user_id:
            res.append(item)
    return res

def add_user_query(user_id: int, query: str) -> None:
    item = {
        "criterion": query.strip(),
        "ts": int(time.time()),
        "user_id": user_id,
    }
    arr = get_user_queries(user_id)
    if not any(x.get("criterion") == item["criterion"] for x in arr):
        append_jsonl(Path(QUERIES_FILE), item)
