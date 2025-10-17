import logging
import re
from typing import Iterable, Optional

INVITE_LINK_RE = re.compile(r"(t\.me/(joinchat/|\+)|chat\.whatsapp\.com/|discord\.gg/|zalo\.me/g/)", re.I)
URL_RE = re.compile(r"(https?://|t\.me/|bit\.ly/|goo\.gl/|tinyurl\.com/)", re.I)
HASHTAG_RE = re.compile(r"(?<!\w)#\w+")
MENTION_RE = re.compile(r"@\w+")
PHONE_RE = re.compile(r"(?<!\d)(\+?\d[\d\-\s]{8,}\d)(?!\d)")
PERCENT_RE = re.compile(r"\d{1,3}\s?%")

# Частые рекламные клише на RU/EN/VN (дополняй под свой поток)
AD_PHRASES = [
    r"\b(скидк\w+|распродаж\w+|промо\w*код|купить\s+сейчас|успей(?:\s+купить)?|подписывайтесь|реклама)\b",
    r"\b(sale|discount|limited\s+time|subscribe|sponsored|promo\s?code)\b",
    r"\b(khuyến\s?mãi|giảm\s?giá|ưu\s?đãi|mã\s?giảm\s?giá|quảng\s?cáo)\b",
]
AD_RE = re.compile("|".join(AD_PHRASES), re.I | re.U)

# Белый/чёрный списки — на твой вкус
WHITELIST_SENDERS = set()       # usernames/id каналов, кого не трогаем
BLACKLIST_SENDERS = set()       # явно рекламные каналы/боты

log = logging.getLogger("filter_ads")

def safe_text(message) -> str:
    return (getattr(message, "message", None)
            or getattr(message, "raw_text", None)
            or getattr(message, "text", None)
            or "") or ""

def has_url_buttons(message) -> bool:
    km = getattr(message, "reply_markup", None)
    if not km or not getattr(km, "rows", None):
        return False
    try:
        # Telethon: reply_markup.rows -> [KeyboardButtonRow], .buttons -> [Button]
        for row in km.rows:
            for btn in getattr(row, "buttons", []):
                url = getattr(btn, "url", None)
                if url and URL_RE.search(url):
                    return True
    except Exception:
        pass
    return False

def sender_username(message) -> Optional[str]:
    try:
        # для каналов: .peer_id / .chat / .sender
        ent = getattr(message, "sender", None) or getattr(message, "chat", None)
        username = getattr(ent, "username", None)
        if username:
            return username.lower()
    except Exception:
        pass
    return None

def is_from_bot(message) -> bool:
    try:
        ent = getattr(message, "sender", None)
        if ent and getattr(ent, "bot", False):
            return True
        uname = sender_username(message)
        if uname and uname.endswith("bot"):
            return True
    except Exception:
        pass
    return False

def ad_score(text: str) -> int:
    score = 0
    # плотность ссылок/хэштегов/упоминаний
    urls = len(URL_RE.findall(text))
    tags = len(HASHTAG_RE.findall(text))
    mentions = len(MENTION_RE.findall(text))
    percents = len(PERCENT_RE.findall(text))
    phones = len(PHONE_RE.findall(text))

    # грубые веса, подруливай под себя
    score += urls * 3
    score += tags * 2
    score += mentions
    score += percents * 2
    score += phones

    # инвайт-линки — жирный флаг
    if INVITE_LINK_RE.search(text):
        score += 6
    # три и больше ссылок в коротком тексте — почти наверняка промо
    if urls >= 3 and len(text) < 500:
        score += 4
    # клише
    if AD_RE.search(text):
        score += 5
    # слишком короткий текст с одной ссылкой
    if urls >= 1 and len(text.strip()) < 40:
        score += 3
    return score

def is_advert(message, threshold: int = 7) -> bool:
    # мгновенные стоп-факторы
    uname = sender_username(message)
    if uname in BLACKLIST_SENDERS:
        log.debug(f"Sender {uname} is in blacklist, marking as advert")
        return True
    if uname in WHITELIST_SENDERS:
        log.debug(f"Sender {uname} is in whitelist, skipping advert check")
        return False
    if is_from_bot(message):
        log.debug(f"Sender {uname} is a bot, marking as advert")
        return True
    if getattr(message, "via_bot_id", None):
        log.debug(f"Message {message.id} has via_bot_id, marking as advert")
        return True
    if has_url_buttons(message):
        log.debug(f"Message {message.id} has URL buttons, marking as advert")
        return True

    text = safe_text(message)
    # медиасообщение с пустым/минимальным текстом и ссылкой
    if getattr(message, "media", None) and URL_RE.search(text) and len(text) < 60:
        log.debug(f"Message {message.id} is media with short text and URL, marking as advert")
        return True

    # скоринг
    score = ad_score(text)
    log.debug(f"Message {message.id} scored {score} against threshold {threshold}")
    return score >= threshold
