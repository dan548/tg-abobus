from telegram import InlineKeyboardMarkup, InlineKeyboardButton

def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Поиск по чатам", callback_data="search_chats")],
        [InlineKeyboardButton("Добавить запрос", callback_data="add_query")],
        [InlineKeyboardButton("Добавить чат", callback_data="add_chat")],
        [InlineKeyboardButton("Показать сохранённые запросы", callback_data="show_queries")],
    ])

def search_submenu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Искать по всем чатам", callback_data="search_all")],
        [InlineKeyboardButton("Искать по выбранным", callback_data="search_selected")],
        [InlineKeyboardButton("Добавить новый чат", callback_data="add_chat")],
        [InlineKeyboardButton("« Назад", callback_data="back_main")],
    ])
