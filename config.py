# Telegram bot token
BOT_TOKEN = "XXX:YYY"

# Telethon credentials

# Change to your own API_ID and API_HASH from https://my.telegram.org
API_ID = 1234567
API_HASH = "123456789abcdef123456789abcdef"

# Change to your own Gemini API key from https://developers.generativeai.google.com
GEMINI_API_KEY = "XXXXXXXXXXXXXXXXXXXX"

TELETHON_SESSION=""
TELETHON_SESSION_FILE = "user_session.session"

# Bridge channel where Telethon forwards content before the bot copies to user
# Create a private channel, add your user account as admin, and get its ID via @getidsbot
BRIDGE_CHAT_ID = -1001234567890

# How many logical "textful" posts to show in results
TOP_K = 10

# Read buffer from source before grouping/slicing (larger to ensure enough textful posts)
FETCH_BUFFER_MIN = 200
FETCH_BUFFER_MAX = 2000
FETCH_BUFFER_MULT = 6

# Logging
LOG_LEVEL = "INFO"

FILTERS_PATH = "data/filters.json"
