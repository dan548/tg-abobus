from __future__ import annotations
import logging
from typing import Optional, Union, List

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, ConversationHandler, ContextTypes, filters
from telegram.error import TimedOut

from config import TOP_K, FILTERS_PATH
from core.models import ScoreResult
from core.llm import LLMScorer, score_logical_messages
from core.filters import append_criterion, read_latest_criterion
from bot.pipeline import read_logical_messages, send_ranked_item

log = logging.getLogger("rent-bot")

BUTTON_ANALYZE = "🔎 Поиск по чату"
BUTTON_SAVE_FILTER = "💾 Сохранить фильтр"
MAIN_KB = ReplyKeyboardMarkup([[BUTTON_ANALYZE, BUTTON_SAVE_FILTER]], resize_keyboard=True)

STATE_WAIT_CHAT_ID, STATE_WAIT_PARAMS, STATE_WAIT_FILTER = range(3)


async def _safe_reply(update: Update, text: str, **kwargs):
    # Небольшой локальный ретрай на случай кратковременной просадки сети
    for attempt in (1, 2):
        try:
            return await update.message.reply_text(text, **kwargs)
        except TimedOut:
            if attempt == 2:
                raise
            import asyncio
            await asyncio.sleep(1.0)
    return None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _safe_reply(update, "Выбирай действие.", reply_markup=MAIN_KB)


async def ask_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await _safe_reply(
        update,
        "Введи numeric chat_id или @username канала/чата. Пример: -1001234567890 или @rentals_dn.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return STATE_WAIT_CHAT_ID


def _parse_chat_identifier(text: str) -> Optional[Union[int, str]]:
    t = (text or "").strip()
    if not t:
        return None
    if t.startswith("@"):
        return t
    try:
        return int(t)
    except ValueError:
        return None


def _parse_k_offset(text: str) -> tuple[int, int]:
    t = (text or "").strip()
    if not t:
        return TOP_K, 0
    parts = t.split()
    try:
        if len(parts) == 1:
            k = max(1, int(parts[0]))
            return k, 0
        k = min(100, max(1, int(parts[0])))
        off = max(0, int(parts[1]))
        return k, off
    except Exception:
        return TOP_K, 0


async def handle_chat_id_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = update.message.text or ""
    chat_identifier = _parse_chat_identifier(raw)
    if chat_identifier is None:
        await _safe_reply(update, "Это не похоже на chat_id/@username. Введи корректно или /cancel.")
        return STATE_WAIT_CHAT_ID

    context.user_data["chat_identifier"] = chat_identifier
    await _safe_reply(
        update,
        "Сколько объявлений анализировать и с какого отступа? Формат: `K` или `K OFFSET`.\n"
        f"Например: `10` или `10 5`. По умолчанию K={TOP_K}, OFFSET=0.",
        parse_mode="Markdown",
    )
    return STATE_WAIT_PARAMS


async def handle_params(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_identifier = context.user_data.get("chat_identifier")
    if chat_identifier is None:
        await _safe_reply(update, "Не вижу chat_id. Начни заново.", reply_markup=MAIN_KB)
        return ConversationHandler.END

    k, offset = _parse_k_offset(update.message.text or "")
    dest_user_id = update.effective_user.id
    th_client = context.bot_data.get("telethon_client")  # TelethonHistoryClient or None
    tele_client = getattr(th_client, "client", None)
    scorer: Optional[LLMScorer] = context.bot_data.get("llm_scorer")

    if not scorer:
        await _safe_reply(update, "LLM анализатор не настроен.", reply_markup=MAIN_KB)
        return ConversationHandler.END

    # читаем K логсообщений (с текстом) с заданным offset
    logical_msgs = await read_logical_messages(
        th_client, from_chat=chat_identifier, limit_textful=k, offset_textful=offset
    )
    if not logical_msgs:
        await _safe_reply(update, "Не удалось прочитать сообщения или они пусты.", reply_markup=MAIN_KB)
        return ConversationHandler.END

    # читаем последний сохранённый критерий
    from pathlib import Path

    criterion = read_latest_criterion(Path(FILTERS_PATH))

    # скорим с данным критерием, сортируем по убыванию
    scored: List[ScoreResult] = await score_logical_messages(scorer, logical_msgs, criterion)
    scored.sort(key=lambda s: s.score, reverse=True)

    # отправляем пользователю
    for sr in scored:
        await send_ranked_item(context.bot, tele_client, chat_identifier, dest_user_id, sr)

    await _safe_reply(
        update,
        f"Готово. Проанализировано {len(scored)} и отправлено в порядке убывания оценки.",
        reply_markup=MAIN_KB,
    )
    return ConversationHandler.END


# ---------- Сохранение фильтра ----------
async def save_filter_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await _safe_reply(
        update,
        "Отправь строку с критериями для поиска. Она буде сохранена и использована в анализе.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return STATE_WAIT_FILTER


async def handle_filter_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()
    if not text:
        await _safe_reply(update, "Пустой критерий не сохраняю. Возвращаю кнопки.", reply_markup=MAIN_KB)
        return ConversationHandler.END
    from pathlib import Path

    append_criterion(Path(FILTERS_PATH), text)
    await _safe_reply(update, "Критерий сохранён.", reply_markup=MAIN_KB)
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await _safe_reply(update, "Отменено.", reply_markup=MAIN_KB)
    return ConversationHandler.END


def register_handlers(app: Application) -> None:
    conv_analyze = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(f"^{BUTTON_ANALYZE}$"), ask_chat_id)],
        states={
            STATE_WAIT_CHAT_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_chat_id_input)],
            STATE_WAIT_PARAMS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_params)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        name="analyze-chat",
        persistent=False,
    )
    conv_save = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(f"^{BUTTON_SAVE_FILTER}$"), save_filter_entry)],
        states={STATE_WAIT_FILTER: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_filter_text)]},
        fallbacks=[CommandHandler("cancel", cancel)],
        name="save-filter",
        persistent=False,
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_analyze)
    app.add_handler(conv_save)
