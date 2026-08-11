"""
Конфигурация Advance RP бота.
Все настройки здесь — не меняйте bot.py для базовых параметров.
"""

# ── Telegram ──────────────────────────────────────────────────────────────────
TOKEN = "8777063629:AAH8NOBxJ1TFz5ei7AaTgFtjAHMnzlvCi5I"

# ID основателя(-ей) — неизменяемые суперадмины
FOUNDER_IDS: list[int] = []

# Начальные ID администраторов (можно добавлять через бота)
ADMIN_IDS: list[int] = [8413337840]

# ── Чаты ──────────────────────────────────────────────────────────────────────
GAME_CHAT_ID: int | None = None  # Автоустанавливается при первом сообщении от админа в группе
REGISTRATION_CHAT_ID: int | None = -1003736855356
REGISTRATION_TOPIC_ID: int | None = 31

BONUS_CHAT_ID: int | None = -1003736855356
BONUS_TOPIC_ID: int | None = 4412

FINES_CHAT_ID: int | None = -1003736855356
FINES_TOPIC_ID: int | None = 2504

BANK_CHAT_ID: int | None = -1003736855356
BANK_TOPIC_ID: int | None = 1263

TOTO_CHAT_ID: int | None = -1003736855356
TOTO_TOPIC_ID: int | None = 6843

# ── Экономика ─────────────────────────────────────────────────────────────────
START_BALANCE: int       = 100_000
SALARY_COOLDOWN: int     = 3 * 3600
BIZ_COOLDOWN: int        = 24 * 3600
BANK_DEPOSIT_RATE_PER_HOUR: float = 0.001

# ── Казино ────────────────────────────────────────────────────────────────────
CASINO_DAILY_LIMIT: int = 10

# ── Кейсы ────────────────────────────────────────────────────────────────────
CASES_CONFIG_FILE: str = "cases_config.json"

# ── Криптовалюта ─────────────────────────────────────────────────────────────
CRYPTO_UPDATE_INTERVAL: int = 60  # секунд между обновлениями цен

# ── База данных ───────────────────────────────────────────────────────────────
DB_PATH: str = "advance_rp.db"
DB_BACKUP_INTERVAL: int = 6 * 3600
DB_BACKUP_DIR: str = "backups"
