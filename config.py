import keyring

# Telegram bot token
BOT_TOKEN = keyring.get_password("rent-bot", "token")

# Telethon credentials
API_ID = keyring.get_password("telethon", "id")
API_HASH = keyring.get_password("telethon", "hash")

GEMINI_API_KEY = keyring.get_password("gemini", "yuri")

TELETHON_SESSION=""
TELETHON_SESSION_FILE = "user_session.session"

# Bridge channel where Telethon forwards content before the bot copies to user
BRIDGE_CHAT_ID = keyring.get_password("bridge", "id")

# How many logical "textful" posts to show in results
TOP_K = 10

# Read buffer from source before grouping/slicing (larger to ensure enough textful posts)
FETCH_BUFFER_MIN = 200
FETCH_BUFFER_MAX = 2000
FETCH_BUFFER_MULT = 6

# Logging
LOG_LEVEL = "INFO"

FILTERS_PATH = "data/filters.json"
