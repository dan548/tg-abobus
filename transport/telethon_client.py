from __future__ import annotations
import logging
from typing import List, Union, Optional
from telethon import TelegramClient
from telethon.tl.custom.message import Message as TLMessage
from dataclasses import dataclass
from core.models import RawMessage

from core.filter_ads import is_advert, safe_text

log = logging.getLogger("telethon-client")
@dataclass
class TelethonHistoryClient:
    client: TelegramClient

    def process_single_message(self, m: TLMessage) -> Optional[RawMessage]:
        if not m:
            return None
        if getattr(m, "deleted", False):
            return None
        text = safe_text(m)
        if not text.strip() and not getattr(m, "media", None):
            return None
        log.debug(f"Before advert check: {m.message}")
        if is_advert(m, threshold=1488):
            log.debug(f"Message {m} identified as advert, skipping")
            return None
        return RawMessage(
            id=m.id,
            text=(m.message or None),
            grouped_id=getattr(m, "grouped_id", None),
            has_media=bool(getattr(m, "media", None)),
        )


    async def iter_messages(self, chat: Union[int, str], *, fetch: int) -> List[RawMessage]:
        msgs: List[TLMessage] = []
        async for m in self.client.iter_messages(chat, limit=fetch):
            msgs.append(m)
        out: List[RawMessage] = []
        for m in msgs:
            raw_msg = self.process_single_message(m)
            log.debug(f"Processed raw message: {raw_msg}")
            if raw_msg:
                out.append(raw_msg)
        return out
