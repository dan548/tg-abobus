from __future__ import annotations
from typing import Optional, Union

async def _resolve_username_with_telethon(tele_client, chat: Union[int, str]) -> Optional[str]:
    try:
        ent = await tele_client.get_entity(chat)
        uname = getattr(ent, "username", None)
        if isinstance(uname, str) and uname.strip():
            return uname.strip()
    except Exception:
        pass
    return None

def _build_tme_c_link_from_numeric(chat_id: int, msg_id: int) -> str:
    abs_id = str(abs(chat_id))
    internal = abs_id[3:] if abs_id.startswith("100") else abs_id
    return f"https://t.me/c/{internal}/{msg_id}"

async def build_origin_link(tele_client, from_chat_identifier: Union[int, str], original_msg_id: int) -> Optional[str]:
    if isinstance(from_chat_identifier, str) and from_chat_identifier.startswith("@"):
        uname = from_chat_identifier[1:]
        return f"https://t.me/{uname}/{original_msg_id}"

    uname = await _resolve_username_with_telethon(tele_client, from_chat_identifier)
    if uname:
        return f"https://t.me/{uname}/{original_msg_id}"

    if isinstance(from_chat_identifier, int):
        return _build_tme_c_link_from_numeric(from_chat_identifier, original_msg_id)

    return None
