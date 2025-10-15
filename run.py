#!/usr/bin/env python3
import asyncio
import logging
from typing import Union, Optional

from telegram import Update
from telegram.ext import Application
from telegram.request import HTTPXRequest

from telethon import TelegramClient
from telethon.sessions import StringSession

from config import BOT_TOKEN, API_ID, API_HASH, TELETHON_SESSION, TELETHON_SESSION_FILE, LOG_LEVEL, GEMINI_API_KEY
from transport.telethon_client import TelethonHistoryClient
from bot.handlers import register_handlers
from core.llm import LLMScorer, LLMPolicy

import google.generativeai as genai
from google.generativeai.types import GenerationConfig

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("rent-bot")


async def on_error(update, context):
    # Глобальный обработчик, чтобы не видеть "No error handlers are registered..."
    log.exception(
        "Unhandled error while handling update %s",
        getattr(update, "update_id", None),
        exc_info=context.error,
    )


# ---- implement your actual LLM call here ----

async def my_send_fn(text: str, criterion: Optional[str]) -> Union[str, dict, float, int]:
    crit = criterion or "2br son_tra price<=20m"
    prompt = f"""
Ты специалист по подбору жилья. Тебе даются критерии и текст объявления. Определи, насколько подходит объявление под критерии
(оценка от 0 до 100, где 100 — идеально подходит, 0 — совсем не подходит) и добавь обоснование оценки. 
В ответе в формате json два поля score и reason, без лишних символов. ```json и ``` вокруг не нужны.
Критерии: {crit}
Текст объявления: {text}
    """.strip()
    return await call_llm_api(prompt)

async def call_llm_api(prompt: str) -> Union[str, dict, float, int]:
    genai.configure(api_key=GEMINI_API_KEY)

    short_response_config = GenerationConfig(temperature=0.2, max_output_tokens=10000)
    
    modelG = genai.GenerativeModel('gemini-2.5-flash', generation_config=short_response_config)

    log.info("Запрос к Gemini: %s", prompt)
    response = await modelG.generate_content_async(prompt)

    try:
        log.info("Ответ Gemini: %s", response.text)
        resp = response.text
    except ValueError:
        print("❌ GEMINI FALL!")
        return "Ошибка анализа ("
    return resp


async def init_telethon() -> Optional[TelethonHistoryClient]:
    if not API_ID or not API_HASH:
        log.warning("API_ID/API_HASH not provided. Telethon disabled.")
        return None
    if TELETHON_SESSION:
        client = TelegramClient(StringSession(TELETHON_SESSION), int(API_ID), API_HASH)
    else:
        client = TelegramClient(TELETHON_SESSION_FILE, int(API_ID), API_HASH)
    await client.connect()
    if not await client.is_user_authorized():
        log.warning("Telethon client is not authorized. History reading disabled.")
        await client.disconnect()
        return None
    log.info("Telethon connected and authorized.")
    return TelethonHistoryClient(client)


async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is required")

    # Настраиваем httpx-клиент PTB с адекватными таймаутами и пулом
    request = HTTPXRequest(
        connect_timeout=15.0,
        read_timeout=30.0,
        write_timeout=30.0,
    )

    app = Application.builder().token(BOT_TOKEN).request(request).build()
    register_handlers(app)
    app.add_error_handler(on_error)

    th_client = await init_telethon()
    app.bot_data["telethon_client"] = th_client

    scorer = LLMScorer(send_fn=my_send_fn, policy=LLMPolicy())
    app.bot_data["llm_scorer"] = scorer

    await app.initialize()
    try:
        await app.start()
        # Пробный пинг
        try:
            me = await app.bot.get_me()
            log.info("Bot connected as @%s (%s)", me.username, me.id)
        except Exception as e:
            log.warning("Initial get_me failed: %s", e)

        await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        await asyncio.Event().wait()
    finally:
        if th_client:
            try:
                await th_client.client.disconnect()
            except Exception:
                pass
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Shutdown")
