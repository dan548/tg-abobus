from __future__ import annotations
from typing import List, Union, Optional, Iterable
import logging
import os

from telethon.tl.types import Message as TLMessage

from telegram.error import BadRequest, TimedOut
from telethon.errors import ChannelPrivateError, ChatAdminRequiredError, MessageIdInvalidError

from config import BRIDGE_CHAT_ID, BRIDGE_CHAT_ID_NUMBER, FETCH_BUFFER_MIN, FETCH_BUFFER_MAX, FETCH_BUFFER_MULT
from core.models import LogicalMessage, RawMessage, ScoreResult
from core.grouping import group_into_logical_messages, slice_logical_by_offset_limit_textful
from core.link import build_origin_link

log = logging.getLogger("rent-bot")

async def resolve_peer(client, ident: Union[str, int]):
    # 1) Юзернейм/ссылка → норм
    if isinstance(ident, str) and not ident.lstrip("-").isdigit():
        return await client.get_input_entity(ident)

    # 2) Цифры → пробуем найти в диалогах (клиент должен быть участником)
    try:
        cid = int(ident)
    except Exception:
        raise ValueError(f"Bad chat identifier: {ident!r}")

    # Bot API формат: -100xxxxxxxxxx → Telethon id: xxxxxxxxxx
    if str(cid).startswith("-100"):
        cid = int(str(cid)[4:])

    for d in await client.get_dialogs():
        if getattr(d.entity, "id", None) == cid:
            return d.input_entity

    raise ValueError(
        "Chat id not found in entity cache. "
        "Убедись, что этот аккаунт вступил в канал/чат, "
        "или укажи @username/инвайт-ссылку в BRIDGE_CHAT."
    )


async def read_logical_messages(history_client, from_chat: Union[int, str], limit_textful: int, offset_textful: int) -> List[LogicalMessage]:
    if history_client is None:
        log.warning("History client is None")
        return []
    target = max(FETCH_BUFFER_MIN, min(FETCH_BUFFER_MAX, (limit_textful + offset_textful) * FETCH_BUFFER_MULT))
    raws: List[RawMessage] = await history_client.iter_messages(from_chat, fetch=target)
    logical_all = group_into_logical_messages(raws)  # old->new
    return slice_logical_by_offset_limit_textful(logical_all, limit=limit_textful, offset=offset_textful)


async def forward_via_bridge(tele_client, src_chat_identifier: Union[str, int], msg_ids: Iterable[int]) -> List[int]:
    """
    Форвардит сообщения в бридж через Telethon и возвращает **только Bot-совместимые message_id (int)**.
    """
    # целевой чат для Telethon — по юзернейму/инвайту
    target_entity = await tele_client.get_input_entity(BRIDGE_CHAT_ID)
    src_entity = await tele_client.get_input_entity(src_chat_identifier)

    res = await tele_client.forward_messages(target_entity, list(msg_ids), from_peer=src_entity)

    # Telethon может вернуть Message или список Message
    if isinstance(res, TLMessage):
        return [res.id]
    elif isinstance(res, list):
        return [m.id for m in res if isinstance(m, TLMessage)]
    else:
        raise RuntimeError(f"Unexpected return from forward_messages: {type(res)}")

async def send_ranked_item(
    bot, tele_client, from_chat_identifier: Union[int, str], dest_user_id: int,
    sr: ScoreResult
) -> None:
    """
    Sends one ranked item to user:
      - if has media: forward whole set to bridge, then copy exactly the caption-carrying message to user
      - if text only: send text
      - append origin link and score in a short trailing message
    """
    lm = sr.lm
    if not (lm and lm.text and lm.text.strip()):
        return

    origin_url = await build_origin_link(tele_client, from_chat_identifier, lm.caption_src_id or lm.ids[0])

    if lm.has_media:
        try:
            bridge_ids = await forward_via_bridge(tele_client, from_chat_identifier, lm.ids)
        except (ChannelPrivateError, ChatAdminRequiredError, MessageIdInvalidError) as te:
            log.warning("Forward to bridge failed for %s: %s", lm.ids, te)
            # fallback: send text with link+score
            await _send_text_with_link_and_score(bot, dest_user_id, lm.text, origin_url, sr.score, sr.reason)
            return

        if not bridge_ids or not lm.caption_src_id:
            await _send_text_with_link_and_score(bot, dest_user_id, lm.text, origin_url, sr.score, sr.reason)
            return

        try:
            idx = lm.ids.index(lm.caption_src_id)
            bridge_msg_id = bridge_ids[idx]
        except Exception:
            bridge_msg_id = None

        if bridge_msg_id:
            try:
                await bot.copy_message(chat_id=dest_user_id, from_chat_id=BRIDGE_CHAT_ID_NUMBER, message_id=bridge_msg_id)
                await _send_link_and_score(bot, dest_user_id, origin_url, sr.score, sr.reason)
            except BadRequest as e:
                log.info("copy_message from bridge failed %s: %s", bridge_msg_id, e)
                await _send_text_with_link_and_score(bot, dest_user_id, lm.text, origin_url, sr.score, sr.reason)
        else:
            await _send_text_with_link_and_score(bot, dest_user_id, lm.text, origin_url, sr.score, sr.reason)
    else:
        await _send_text_with_link_and_score(bot, dest_user_id, lm.text, origin_url, sr.score, sr.reason)


async def _send_text_with_link_and_score(bot, chat_id: int, text: str, origin_url: Optional[str], score: float, reason: Optional[str]):
    tail = f"🔗 Оригинал: {origin_url}\n⭐ Оценка: {score:.2f}"
    if reason:
        tail += f" — {reason}"
    for attempt in (1, 2):
        try:
            return await bot.send_message(chat_id=chat_id, text=f"{text}\n\n{tail}")
        except TimedOut:
            if attempt == 2:
                raise
            import asyncio
            await asyncio.sleep(1.0)


async def _send_link_and_score(bot, chat_id: int, origin_url: Optional[str], score: float, reason: Optional[str]):
    tail = f"🔗 Оригинал: {origin_url}\n⭐ Оценка: {score:.2f}"
    if reason:
        tail += f" — {reason}"
    for attempt in (1, 2):
        try:
            return await bot.send_message(chat_id=chat_id, text=tail)
        except TimedOut:
            if attempt == 2:
                raise
            import asyncio
            await asyncio.sleep(1.0)
