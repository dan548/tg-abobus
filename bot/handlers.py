from enum import IntEnum, auto
from typing import List, Optional
from telegram import Update
from telegram.ext import (
    ContextTypes, CallbackQueryHandler, MessageHandler, filters,
    ConversationHandler, CommandHandler
)
from bot.pipeline import read_logical_messages, send_ranked_item
from core.keyboards import main_menu_kb, search_submenu_kb
from core.llm import score_logical_messages
from core.models import ScoreResult
from core.storage import get_user_chats, add_user_chat, add_user_query, get_user_queries
from core.parsing import parse_index_selection

class S(IntEnum):
    IDLE = auto()
    AWAIT_CHAT_IDENTIFIER = auto()
    AWAIT_QUERY_TEXT = auto()
    AWAIT_SELECTED_INDEXES = auto()


async def run_search_for_user(user_id: int, chat_list: List[str], context: ContextTypes.DEFAULT_TYPE) -> str:
    th_client = context.bot_data.get("telethon_client")
    scorer = context.bot_data.get("llm_scorer")
    for chat in chat_list:
        msgs = await read_logical_messages(
            th_client, from_chat=chat, limit_textful=50, offset_textful=0
        )
        queries = get_user_queries(user_id=user_id)
    
        scored: List[ScoreResult] = await score_logical_messages(scorer, msgs, queries[0]["criterion"] if queries else "")
        scored.sort(key=lambda s: s.score, reverse=True)

        # отправляем пользователю
        for sr in scored:
            await send_ranked_item(context.bot, th_client, chat, user_id, sr)

    return f"Готов анализ по {len(chat_list)} чатам:\n" + "\n".join(f"• {c}" for c in chat_list)

# ——— Команды ———
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (
        "Привет. Да, снова кнопки. Снова ты. Главное меню ниже.\n"
        "Выбирай действие, постараюсь не упасть."
    )
    if update.message:
        await update.message.reply_text(text, reply_markup=main_menu_kb())
    else:
        await update.effective_chat.send_message(text, reply_markup=main_menu_kb())
    return S.IDLE

# ——— Кнопки главного меню ———
async def cb_main_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    data = q.data

    user_id = update.effective_user.id

    if data == "search_chats":
        chats = get_user_chats(user_id)
        if not chats:
            await q.edit_message_text(
                "У тебя нет сохранённых чатов. Сюрприз. Добавь хоть один.",
                reply_markup=search_submenu_kb()
            )
        else:
            lines = ["Сохранённые чаты (нумерация с 1):"]
            for i, c in enumerate(chats, 1):
                lines.append(f"{i}. {c['chat']}")
            await q.edit_message_text(
                "\n".join(lines),
                reply_markup=search_submenu_kb()
            )
        return S.IDLE

    if data == "add_query":
        await q.edit_message_text(
            "Введи текст запроса. Сохраню это в твой вечный архив гениальности.\n"
            "Пример: \"1BR near An Hải, до 400$\""
        )
        return S.AWAIT_QUERY_TEXT

    if data == "add_chat":
        await q.edit_message_text(
            "Отправь идентификатор чата: @username, числовой id или ссылку-приглашение."
        )
        return S.AWAIT_CHAT_IDENTIFIER

    if data == "show_queries":
        queries = get_user_queries(user_id)
        if not queries:
            await q.edit_message_text("Сохранённых запросов нет. Пустота и эхо.")
        else:
            msg = "Твои сохранённые запросы (последние сверху):\n\n"
            for i, s in enumerate(reversed(queries), 1):
                msg += f"{i}. {s["criterion"]}\n"
            await q.edit_message_text(msg, reply_markup=main_menu_kb())
        return S.IDLE

    if data == "back_main":
        await q.edit_message_text("Окей, назад в главное меню.", reply_markup=main_menu_kb())
        return S.IDLE

    if data == "search_all":
        chats = [c["chat"] for c in get_user_chats(user_id)]
        if not chats:
            await q.edit_message_text(
                "Нет чатов для поиска. Добавь хотя бы один.",
                reply_markup=search_submenu_kb()
            )
            return S.IDLE
        res = await run_search_for_user(user_id, chats, context=context)
        await q.edit_message_text(res, reply_markup=main_menu_kb())
        return S.IDLE

    if data == "search_selected":
        chats = get_user_chats(user_id)
        if not chats:
            await q.edit_message_text(
                "Нет чатов для выбора. Добавь чат.",
                reply_markup=search_submenu_kb()
            )
            return S.IDLE
        lines = ["Введи номера чатов через запятую и/или диапазоны:",
                 "Например: 1,3-5,7"]
        await q.edit_message_text("\n".join(lines))
        return S.AWAIT_SELECTED_INDEXES

    # на всякий
    await q.edit_message_text("Не понял кнопку. Жизнь боль. Возвращаю меню.", reply_markup=main_menu_kb())
    return S.IDLE

# ——— Обработчики текстовых ответов по диалогам ———
async def on_chat_identifier(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text("Пусто. Дай хоть что-то: @username, id или ссылку.")
        return S.AWAIT_CHAT_IDENTIFIER

    add_user_chat(user_id, text)
    await update.message.reply_text(
        f"Чат сохранён: {text}\nЧто дальше?", reply_markup=main_menu_kb()
    )
    return S.IDLE

async def on_query_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text("Пустой запрос не сохраняю. Напиши нормальный текст.")
        return S.AWAIT_QUERY_TEXT

    add_user_query(user_id, text)
    await update.message.reply_text("Запрос сохранён. Вернулся в меню.", reply_markup=main_menu_kb())
    return S.IDLE

async def on_selected_indexes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    chats = get_user_chats(user_id)
    s = (update.message.text or "").strip()
    idxs = parse_index_selection(s, total=len(chats))
    if not idxs:
        await update.message.reply_text(
            "Не смог распарсить номера. Пример: 1,3-5,7\nПопробуй снова."
        )
        return S.AWAIT_SELECTED_INDEXES

    chosen = [chats[i]["chat"] for i in idxs]
    res = await run_search_for_user(user_id, chosen, context=context)
    await update.message.reply_text(res, reply_markup=main_menu_kb())
    return S.IDLE

# ——— Фоллбэк ———
async def unknown_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Не это сейчас. Используй кнопки ниже.", reply_markup=main_menu_kb())
    return S.IDLE

def build_conversation():
    return ConversationHandler(
        entry_points=[CommandHandler("start", cmd_start)],
        states={
            S.IDLE: [
                CallbackQueryHandler(cb_main_router),
            ],
            S.AWAIT_CHAT_IDENTIFIER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, on_chat_identifier),
                CallbackQueryHandler(cb_main_router),
            ],
            S.AWAIT_QUERY_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, on_query_text),
                CallbackQueryHandler(cb_main_router),
            ],
            S.AWAIT_SELECTED_INDEXES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, on_selected_indexes),
                CallbackQueryHandler(cb_main_router),
            ],
        },
        fallbacks=[
            CommandHandler("start", cmd_start),
            MessageHandler(filters.TEXT & ~filters.COMMAND, unknown_text),
        ],
        allow_reentry=True,
    )
