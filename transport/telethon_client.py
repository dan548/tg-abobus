from __future__ import annotations
from typing import List, Union
from telethon import TelegramClient
from telethon.tl.custom.message import Message as TLMessage
from dataclasses import dataclass
from core.models import RawMessage

@dataclass
class TelethonHistoryClient:
    client: TelegramClient

    async def iter_messages(self, chat: Union[int, str], *, fetch: int) -> List[RawMessage]:
        msgs: List[TLMessage] = []
        async for m in self.client.iter_messages(chat, limit=fetch):
            msgs.append(m)
        out: List[RawMessage] = []
        out.extend(
            RawMessage(
                id=m.id,
                text=(m.message or None),
                grouped_id=getattr(m, "grouped_id", None),
                has_media=bool(getattr(m, "media", None)),
            )
            for m in msgs
        )
        return out
