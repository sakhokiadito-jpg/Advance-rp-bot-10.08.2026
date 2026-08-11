"""
database.py — Полная база данных Advance RP (SQLite).
Все операции с данными только здесь. Никаких JSON-файлов.
Версия: 2.0 — расширенная структура с автомиграцией.
"""

import os
import sqlite3
import random
import string
import shutil
import time
from datetime import datetime, timezone

import config

# ── Константы ─────────────────────────────────────────────────────────────────
TAX_RATE: float = 0.35           # налог на бизнес (35%)
DB_PATH: str    = config.DB_PATH

# Организации (тип → (иконка, название по умолчанию))
ORG_DISPLAY: dict = {
    "mafia":     ("🔫", "Мафия"),
    "police":    ("👮", "Полиция"),
    "government":("🏛️", "Правительство"),
    "fsb":       ("🔵", "ФСБ"),
    "gang":      ("💀", "Банда"),
    "business":  ("💼", "Бизнес-клуб"),
}


# ── Подключение ───────────────────────────────────────────────────────────────
def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    c.execute("PRAGMA synchronous=NORMAL")
    return c

com = _conn()   # глобальное соединение (для совместимости)


def _exec(sql: str, params=(), *, fetch: str = "none"):
    """Безопасное выполнение SQL с параметрами."""
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    try:
        with c:
            cur = c.execute(sql, params)
            if fetch == "one":
                return cur.fetchone()
            if fetch == "all":
                return cur.fetchall()
            return cur.lastrowid
    finally:
        c.close()


# ── init_db: создание всех таблиц ────────────────────────────────────────────
def init_db():
    """Создаёт все таблицы при первом запуске. Безопасно вызывать повторно."""
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    with c:
        # ── Игроки ──────────────────────────────────────────────────────────
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                uid              INTEGER PRIMARY KEY,
                username         TEXT    NOT NULL DEFAULT '',
                spm_id           TEXT    NOT NULL DEFAULT '',
                game_name        TEXT    NOT NULL DEFAULT '',
                balance          INTEGER NOT NULL DEFAULT 0,
                bank             INTEGER NOT NULL DEFAULT 0,
                btc              INTEGER NOT NULL DEFAULT 0,
                job              TEXT,
                last_salary      INTEGER NOT NULL DEFAULT 0,
                banned           INTEGER NOT NULL DEFAULT 0,
                license          TEXT    NOT NULL DEFAULT '',
                garage_slots     INTEGER NOT NULL DEFAULT 2,
                x2               INTEGER NOT NULL DEFAULT 0,
                credit           INTEGER NOT NULL DEFAULT 0,
                bank_last_updated INTEGER NOT NULL DEFAULT 0,
                biz_income_time  INTEGER NOT NULL DEFAULT 0,
                appearance       TEXT    NOT NULL DEFAULT '',
                source           TEXT    NOT NULL DEFAULT '',
                tax_debt         INTEGER NOT NULL DEFAULT 0,
                registered_at    INTEGER NOT NULL DEFAULT (strftime('%s','now')),
                last_seen        INTEGER NOT NULL DEFAULT (strftime('%s','now'))
            )
        """)
        _add_column_if_missing(c, "users", "appearance", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(c, "users", "source",     "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(c, "users", "tax_debt",   "INTEGER NOT NULL DEFAULT 0")
        _add_column_if_missing(c, "users", "registered_at","INTEGER NOT NULL DEFAULT 0")
        _add_column_if_missing(c, "users", "last_seen",  "INTEGER NOT NULL DEFAULT 0")
        _add_column_if_missing(c, "users", "btc",        "INTEGER NOT NULL DEFAULT 0")
        _add_column_if_missing(c, "users", "credit",     "INTEGER NOT NULL DEFAULT 0")
        _add_column_if_missing(c, "users", "bank_last_updated","INTEGER NOT NULL DEFAULT 0")
        _add_column_if_missing(c, "users", "biz_income_time","INTEGER NOT NULL DEFAULT 0")

        # ── Автомобили ──────────────────────────────────────────────────────
        c.execute("""
            CREATE TABLE IF NOT EXISTS cars (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                uid       INTEGER NOT NULL REFERENCES users(uid),
                car_id    INTEGER NOT NULL,
                name      TEXT    NOT NULL,
                price     INTEGER NOT NULL DEFAULT 0,
                plate     TEXT    NOT NULL DEFAULT '',
                token     TEXT    NOT NULL DEFAULT '',
                custom_plate INTEGER NOT NULL DEFAULT 0,
                acquired_at  INTEGER NOT NULL DEFAULT (strftime('%s','now'))
            )
        """)
        _add_column_if_missing(c, "cars", "custom_plate", "INTEGER NOT NULL DEFAULT 0")
        _add_column_if_missing(c, "cars", "acquired_at", "INTEGER NOT NULL DEFAULT 0")
        c.execute("CREATE INDEX IF NOT EXISTS idx_cars_uid ON cars(uid)")
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_cars_token ON cars(token) WHERE token != ''")

        # ── Бизнесы ─────────────────────────────────────────────────────────
        c.execute("""
            CREATE TABLE IF NOT EXISTS businesses (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                uid       INTEGER NOT NULL REFERENCES users(uid),
                biz_id    INTEGER NOT NULL,
                name      TEXT    NOT NULL,
                income    INTEGER NOT NULL DEFAULT 0,
                token     TEXT    NOT NULL DEFAULT '',
                acquired_at INTEGER NOT NULL DEFAULT (strftime('%s','now'))
            )
        """)
        _add_column_if_missing(c, "businesses", "acquired_at", "INTEGER NOT NULL DEFAULT 0")
        c.execute("CREATE INDEX IF NOT EXISTS idx_biz_uid ON businesses(uid)")
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_biz_token ON businesses(token) WHERE token != ''")

        # ── Недвижимость ─────────────────────────────────────────────────────
        c.execute("""
            CREATE TABLE IF NOT EXISTS apartments (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                uid       INTEGER NOT NULL REFERENCES users(uid),
                apt_id    INTEGER NOT NULL,
                name      TEXT    NOT NULL,
                price     INTEGER NOT NULL DEFAULT 0,
                token     TEXT    NOT NULL DEFAULT '',
                acquired_at INTEGER NOT NULL DEFAULT (strftime('%s','now'))
            )
        """)
        _add_column_if_missing(c, "apartments", "acquired_at", "INTEGER NOT NULL DEFAULT 0")
        c.execute("CREATE INDEX IF NOT EXISTS idx_apt_uid ON apartments(uid)")
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_apt_token ON apartments(token) WHERE token != ''")

        # ── Администраторы ──────────────────────────────────────────────────
        c.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                uid       INTEGER PRIMARY KEY REFERENCES users(uid),
                granted_by INTEGER,
                granted_at INTEGER NOT NULL DEFAULT (strftime('%s','now'))
            )
        """)

        # ── Логи ─────────────────────────────────────────────────────────────
        c.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                uid       INTEGER NOT NULL,
                action    TEXT    NOT NULL,
                details   TEXT    NOT NULL DEFAULT '',
                amount    INTEGER NOT NULL DEFAULT 0,
                actor_id  INTEGER,
                ts        INTEGER NOT NULL DEFAULT (strftime('%s','now'))
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_logs_uid ON logs(uid)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_logs_action ON logs(action)")

        # ── Штрафы ───────────────────────────────────────────────────────────
        c.execute("""
            CREATE TABLE IF NOT EXISTS fines (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                uid        INTEGER NOT NULL,
                amount     INTEGER NOT NULL,
                reason     TEXT    NOT NULL DEFAULT '',
                article    TEXT    NOT NULL DEFAULT '',
                officer_id INTEGER,
                paid       INTEGER NOT NULL DEFAULT 0,
                ts         INTEGER NOT NULL DEFAULT (strftime('%s','now'))
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_fines_uid ON fines(uid)")

        # ── Промокоды ────────────────────────────────────────────────────────
        c.execute("""
            CREATE TABLE IF NOT EXISTS promos (
                code      TEXT    PRIMARY KEY,
                bonus     INTEGER NOT NULL DEFAULT 0,
                max_uses  INTEGER NOT NULL DEFAULT 0,
                uses      INTEGER NOT NULL DEFAULT 0,
                active    INTEGER NOT NULL DEFAULT 1,
                created_at INTEGER NOT NULL DEFAULT (strftime('%s','now'))
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS promo_uses (
                uid  INTEGER NOT NULL,
                code TEXT    NOT NULL,
                ts   INTEGER NOT NULL DEFAULT (strftime('%s','now')),
                PRIMARY KEY (uid, code)
            )
        """)

        # ── Ежедневный бонус ─────────────────────────────────────────────────
        c.execute("""
            CREATE TABLE IF NOT EXISTS daily_bonus_rewards (
                day          INTEGER PRIMARY KEY,
                amount       INTEGER NOT NULL DEFAULT 0,
                description  TEXT    NOT NULL DEFAULT '',
                reward_type  TEXT    NOT NULL DEFAULT 'money',
                reward_value TEXT    NOT NULL DEFAULT '0',
                active       INTEGER NOT NULL DEFAULT 1
            )
        """)
        # Миграция старой схемы: amount/description сохраняются для совместимости.
        _add_column_if_missing(c, "daily_bonus_rewards", "reward_type", "TEXT NOT NULL DEFAULT 'money'")
        _add_column_if_missing(c, "daily_bonus_rewards", "reward_value", "TEXT NOT NULL DEFAULT '0'")
        _add_column_if_missing(c, "daily_bonus_rewards", "active", "INTEGER NOT NULL DEFAULT 1")
        c.execute("""
            UPDATE daily_bonus_rewards
            SET reward_type='money',
                reward_value=CAST(amount AS TEXT)
            WHERE (reward_value='' OR reward_value IS NULL OR
                   (reward_type='money' AND reward_value='0' AND amount<>0))
        """)

        # ── Криптовалюта ───────────────────────────────────────────────────────
        c.execute("""
            CREATE TABLE IF NOT EXISTS crypto_wallets (
                uid    INTEGER NOT NULL REFERENCES users(uid) ON DELETE CASCADE,
                asset  TEXT    NOT NULL,
                amount INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (uid, asset)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS crypto_prices (
                asset       TEXT PRIMARY KEY,
                price       REAL NOT NULL,
                updated_at  INTEGER NOT NULL DEFAULT 0
            )
        """)
        # Переносим уже накопленный BTC из старого поля users.btc в новый кошелёк.
        c.execute("""
            INSERT OR IGNORE INTO crypto_wallets(uid, asset, amount)
            SELECT uid, 'BTC', btc FROM users WHERE btc > 0
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS user_bonus (
                uid           INTEGER PRIMARY KEY,
                current_day   INTEGER NOT NULL DEFAULT 0,
                last_claim    INTEGER NOT NULL DEFAULT 0,
                total_claimed INTEGER NOT NULL DEFAULT 0
            )
        """)

        # ── МВД ──────────────────────────────────────────────────────────────
        c.execute("""
            CREATE TABLE IF NOT EXISTS mvd_employees (
                uid        INTEGER PRIMARY KEY REFERENCES users(uid),
                unit       TEXT NOT NULL DEFAULT '',
                role       TEXT NOT NULL DEFAULT '',
                appointed_by INTEGER,
                appointed_at INTEGER NOT NULL DEFAULT (strftime('%s','now'))
            )
        """)

        # ── Правительство ────────────────────────────────────────────────────
        c.execute("""
            CREATE TABLE IF NOT EXISTS gov_employees (
                uid        INTEGER PRIMARY KEY REFERENCES users(uid),
                role       TEXT NOT NULL DEFAULT '',
                appointed_by INTEGER,
                appointed_at INTEGER NOT NULL DEFAULT (strftime('%s','now'))
            )
        """)

        # ── Организации ──────────────────────────────────────────────────────
        c.execute("""
            CREATE TABLE IF NOT EXISTS organizations (
                org_type   TEXT PRIMARY KEY,
                name       TEXT NOT NULL DEFAULT ''
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS org_members (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                org_type TEXT NOT NULL,
                uid      INTEGER NOT NULL REFERENCES users(uid),
                is_owner INTEGER NOT NULL DEFAULT 0,
                joined_at INTEGER NOT NULL DEFAULT (strftime('%s','now')),
                UNIQUE(org_type, uid)
            )
        """)

        # ── Игрок-организации ────────────────────────────────────────────────
        c.execute("""
            CREATE TABLE IF NOT EXISTS player_orgs (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_uid INTEGER NOT NULL,
                name      TEXT    NOT NULL UNIQUE,
                icon      TEXT    NOT NULL DEFAULT '🏢',
                created_at INTEGER NOT NULL DEFAULT (strftime('%s','now'))
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS player_org_members (
                org_id INTEGER NOT NULL,
                uid    INTEGER NOT NULL,
                joined_at INTEGER NOT NULL DEFAULT (strftime('%s','now')),
                PRIMARY KEY (org_id, uid)
            )
        """)

        # ── Тотализатор ──────────────────────────────────────────────────────
        c.execute("""
            CREATE TABLE IF NOT EXISTS toto_matches (
                match_id   TEXT PRIMARY KEY,
                home       TEXT NOT NULL,
                away       TEXT NOT NULL,
                league     TEXT NOT NULL DEFAULT '',
                start_ts   INTEGER NOT NULL,
                status     TEXT NOT NULL DEFAULT 'upcoming',
                result     TEXT,
                odds_home  REAL NOT NULL DEFAULT 2.0,
                odds_draw  REAL NOT NULL DEFAULT 3.0,
                odds_away  REAL NOT NULL DEFAULT 2.0,
                updated_at INTEGER NOT NULL DEFAULT (strftime('%s','now'))
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS toto_bets (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                uid      INTEGER NOT NULL,
                match_id TEXT NOT NULL,
                outcome  TEXT NOT NULL,
                amount   INTEGER NOT NULL,
                odds     REAL NOT NULL DEFAULT 1.0,
                resolved INTEGER NOT NULL DEFAULT 0,
                won      INTEGER,
                payout   INTEGER NOT NULL DEFAULT 0,
                ts       INTEGER NOT NULL DEFAULT (strftime('%s','now'))
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_toto_bets_uid ON toto_bets(uid)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_toto_bets_match ON toto_bets(match_id)")

        # ── Казна ────────────────────────────────────────────────────────────
        c.execute("""
            CREATE TABLE IF NOT EXISTS treasury (
                id      INTEGER PRIMARY KEY CHECK(id=1),
                balance INTEGER NOT NULL DEFAULT 0
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS treasury_logs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                amount      INTEGER NOT NULL,
                source_type TEXT    NOT NULL DEFAULT '',
                source_uid  INTEGER,
                description TEXT    NOT NULL DEFAULT '',
                ts          INTEGER NOT NULL DEFAULT (strftime('%s','now'))
            )
        """)
        c.execute("INSERT OR IGNORE INTO treasury(id, balance) VALUES(1, 0)")

        # ── Лицензии ─────────────────────────────────────────────────────────
        c.execute("""
            CREATE TABLE IF NOT EXISTS licenses (
                uid      INTEGER NOT NULL,
                license  TEXT    NOT NULL,
                active   INTEGER NOT NULL DEFAULT 1,
                issued_at INTEGER NOT NULL DEFAULT (strftime('%s','now')),
                PRIMARY KEY(uid, license)
            )
        """)

        # ── Каталог (admin-добавленные объекты) ──────────────────────────────
        c.execute("""
            CREATE TABLE IF NOT EXISTS catalog (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                type    TEXT    NOT NULL,
                game_id INTEGER NOT NULL,
                name    TEXT    NOT NULL,
                price   INTEGER NOT NULL DEFAULT 0,
                income  INTEGER NOT NULL DEFAULT 0,
                active  INTEGER NOT NULL DEFAULT 1,
                UNIQUE(type, game_id)
            )
        """)

        # ── Казино ───────────────────────────────────────────────────────────
        c.execute("""
            CREATE TABLE IF NOT EXISTS casino_plays (
                uid  INTEGER NOT NULL,
                date TEXT    NOT NULL,
                plays INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(uid, date)
            )
        """)

        # ── Кейсы ────────────────────────────────────────────────────────────
        c.execute("""
            CREATE TABLE IF NOT EXISTS cases (
                uid        INTEGER NOT NULL,
                case_type  TEXT    NOT NULL,
                count      INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(uid, case_type)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS case_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                uid         INTEGER NOT NULL,
                case_type   TEXT    NOT NULL,
                reward_type TEXT    NOT NULL,
                reward_label TEXT   NOT NULL DEFAULT '',
                reward_value TEXT   NOT NULL DEFAULT '',
                ts          INTEGER NOT NULL DEFAULT (strftime('%s','now'))
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_case_history_uid ON case_history(uid)")

        # ── Статистика ───────────────────────────────────────────────────────
        c.execute("""
            CREATE TABLE IF NOT EXISTS statistics (
                uid             INTEGER PRIMARY KEY,
                total_earned    INTEGER NOT NULL DEFAULT 0,
                total_spent     INTEGER NOT NULL DEFAULT 0,
                cars_bought     INTEGER NOT NULL DEFAULT 0,
                biz_bought      INTEGER NOT NULL DEFAULT 0,
                apts_bought     INTEGER NOT NULL DEFAULT 0,
                cases_opened    INTEGER NOT NULL DEFAULT 0,
                casino_wins     INTEGER NOT NULL DEFAULT 0,
                casino_losses   INTEGER NOT NULL DEFAULT 0,
                toto_wins       INTEGER NOT NULL DEFAULT 0,
                toto_losses     INTEGER NOT NULL DEFAULT 0
            )
        """)

        # ── Кредиты ──────────────────────────────────────────────────────────
        c.execute("""
            CREATE TABLE IF NOT EXISTS credits (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                uid         INTEGER NOT NULL,
                amount      INTEGER NOT NULL,
                interest_rate REAL NOT NULL DEFAULT 5.0,
                term_days   INTEGER NOT NULL DEFAULT 30,
                paid        INTEGER NOT NULL DEFAULT 0,
                due_date    INTEGER NOT NULL,
                issued_at   INTEGER NOT NULL DEFAULT (strftime('%s','now'))
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_credits_uid ON credits(uid)")

        # ── Настройки проекта ────────────────────────────────────────────────
        c.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT ''
            )
        """)


        # ── Банковские операции ──────────────────────────────────────────────
        c.execute("""
            CREATE TABLE IF NOT EXISTS bank_operations (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                uid         INTEGER NOT NULL,
                type        TEXT    NOT NULL,
                amount      INTEGER NOT NULL,
                balance_after INTEGER NOT NULL DEFAULT 0,
                bank_after  INTEGER NOT NULL DEFAULT 0,
                description TEXT    NOT NULL DEFAULT '',
                ts          INTEGER NOT NULL DEFAULT (strftime('%s','now'))
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_bank_ops_uid ON bank_operations(uid)")

        # ── История ежедневных бонусов ───────────────────────────────────────
        c.execute("""
            CREATE TABLE IF NOT EXISTS bonus_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                uid         INTEGER NOT NULL,
                day         INTEGER NOT NULL,
                reward_type TEXT    NOT NULL DEFAULT 'money',
                reward_value TEXT   NOT NULL DEFAULT '',
                ts          INTEGER NOT NULL DEFAULT (strftime('%s','now'))
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_bonus_hist_uid ON bonus_history(uid)")

        # ── Настройки бонусов ────────────────────────────────────────────────
        c.execute("""
            CREATE TABLE IF NOT EXISTS bonus_settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT ''
            )
        """)
    c.close()
    print(f"✅ База данных инициализирована: {DB_PATH}")


def _add_column_if_missing(c: sqlite3.Connection, table: str, col: str, definition: str):
    """Добавляет колонку, если её ещё нет (автомиграция)."""
    cols = [row[1] for row in c.execute(f"PRAGMA table_info({table})")]
    if col not in cols:
        c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {definition}")


# ── Вспомогательные ───────────────────────────────────────────────────────────
def _gen_token(length: int = 16) -> str:
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def gen_ru_plate() -> str:
    """Генерирует случайный российский госномер."""
    letters = "АВЕКМНОРСТУХ"
    digits  = "0123456789"
    regions = ["77", "78", "50", "99", "197", "750", "777", "199"]
    l = random.choice(letters)
    n = ''.join(random.choices(digits, k=3))
    ll = random.choices(letters, k=2)
    r = random.choice(regions)
    return f"{l}{n}{''.join(ll)}{r}"


# ═══════════════════════════════════════════════════════════════════════════════
# ПОЛЬЗОВАТЕЛИ
# ═══════════════════════════════════════════════════════════════════════════════

def register_user(uid: int, username: str, spm_id: str, game_name: str,
                  appearance: str = "", source: str = ""):
    _exec("""
        INSERT OR IGNORE INTO users
          (uid, username, spm_id, game_name, balance, appearance, source)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (uid, username, spm_id, game_name, config.START_BALANCE, appearance, source))
    _exec("""
        INSERT OR IGNORE INTO statistics(uid) VALUES(?)
    """, (uid,))


def get_user(uid: int):
    row = _exec("""
        SELECT uid, username, spm_id, game_name, balance, bank, btc, job,
               last_salary, banned, license, garage_slots, x2, credit,
               bank_last_updated, biz_income_time, appearance
        FROM users WHERE uid=?
    """, (uid,), fetch="one")
    return tuple(row) if row else None


def get_user_by_username(username: str):
    username = username.lstrip("@")
    row = _exec("""
        SELECT uid, username, spm_id, game_name, balance, bank, btc, job,
               last_salary, banned, license, garage_slots, x2, credit,
               bank_last_updated, biz_income_time, appearance
        FROM users WHERE LOWER(username)=LOWER(?)
    """, (username,), fetch="one")
    return tuple(row) if row else None


def get_all_users() -> list[int]:
    rows = _exec("SELECT uid FROM users WHERE banned=0", fetch="all")
    return [r[0] for r in rows]


def get_all_users_info():
    return _exec("""
        SELECT uid, username, game_name, balance, bank, job, banned
        FROM users ORDER BY balance DESC
    """, fetch="all")


def update_balance(uid: int, amount: int):
    _exec("UPDATE users SET balance = balance + ? WHERE uid=?", (amount, uid))


def update_btc(uid: int, amount: int):
    """Добавить / отнять BTC в legacy-поле пользователя (микро-BTC)."""
    _exec("UPDATE users SET btc = btc + ? WHERE uid=?", (amount, uid))


# ═══════════════════════════════════════════════════════════════════════════════
# КРИПТОВАЛЮТА
# ═══════════════════════════════════════════════════════════════════════════════

CRYPTO_SCALE = 1_000_000  # 1.000000 единица актива = 1_000_000 внутренних единиц
CRYPTO_ASSETS = ("BTC", "ETH")


def _crypto_asset(asset: str) -> str:
    asset = str(asset).upper()
    if asset not in CRYPTO_ASSETS:
        raise ValueError("Неизвестная криптовалюта")
    return asset


def get_crypto_price(asset: str, default: float = 0.0) -> float:
    asset = _crypto_asset(asset)
    row = _exec("SELECT price FROM crypto_prices WHERE asset=?", (asset,), fetch="one")
    return float(row[0]) if row else float(default)


def set_crypto_price(asset: str, price: float):
    asset = _crypto_asset(asset)
    _exec("""
        INSERT INTO crypto_prices(asset, price, updated_at)
        VALUES(?,?,?)
        ON CONFLICT(asset) DO UPDATE SET price=excluded.price, updated_at=excluded.updated_at
    """, (asset, float(price), int(time.time())))


def get_crypto_prices() -> dict[str, float]:
    rows = _exec("SELECT asset, price FROM crypto_prices", fetch="all") or []
    return {str(r[0]): float(r[1]) for r in rows}


def get_crypto_balance(uid: int, asset: str) -> int:
    asset = _crypto_asset(asset)
    row = _exec("SELECT amount FROM crypto_wallets WHERE uid=? AND asset=?", (uid, asset), fetch="one")
    return int(row[0]) if row else 0


def get_crypto_portfolio(uid: int) -> dict[str, int]:
    rows = _exec("SELECT asset, amount FROM crypto_wallets WHERE uid=?", (uid,), fetch="all") or []
    result = {asset: 0 for asset in CRYPTO_ASSETS}
    for r in rows:
        result[str(r[0])] = int(r[1])
    return result


def crypto_trade(uid: int, asset: str, amount: int, rub_value: int, side: str) -> bool:
    """Атомарно покупает/продаёт криптовалюту за рубли.
    amount — внутренние микро-единицы; rub_value — сумма сделки."""
    asset = _crypto_asset(asset)
    amount = int(amount)
    rub_value = int(rub_value)
    side = str(side).lower()
    if amount <= 0 or rub_value <= 0 or side not in {"buy", "sell"}:
        return False

    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    try:
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA foreign_keys=ON")
        with c:
            user = c.execute("SELECT balance FROM users WHERE uid=?", (uid,)).fetchone()
            if not user:
                return False
            row = c.execute(
                "SELECT amount FROM crypto_wallets WHERE uid=? AND asset=?",
                (uid, asset)
            ).fetchone()
            current = int(row[0]) if row else 0

            if side == "buy":
                if int(user[0]) < rub_value:
                    return False
                new_amount = current + amount
                c.execute("UPDATE users SET balance=balance-? WHERE uid=?", (rub_value, uid))
            else:
                if current < amount:
                    return False
                new_amount = current - amount
                c.execute("UPDATE users SET balance=balance+? WHERE uid=?", (rub_value, uid))

            c.execute("""
                INSERT INTO crypto_wallets(uid, asset, amount) VALUES(?,?,?)
                ON CONFLICT(uid, asset) DO UPDATE SET amount=excluded.amount
            """, (uid, asset, new_amount))
            if asset == "BTC":
                c.execute("UPDATE users SET btc=? WHERE uid=?", (new_amount, uid))
        return True
    finally:
        c.close()


def set_balance(uid: int, amount: int):
    _exec("UPDATE users SET balance=? WHERE uid=?", (amount, uid))


def update_salary_time(uid: int):
    _exec("UPDATE users SET last_salary=? WHERE uid=?", (int(time.time()), uid))


def ban_user(uid: int):
    _exec("UPDATE users SET banned=1 WHERE uid=?", (uid,))


def unban_user(uid: int):
    _exec("UPDATE users SET banned=0 WHERE uid=?", (uid,))


def reset_user(uid: int):
    _exec("""
        UPDATE users SET balance=?, bank=0, btc=0, job=NULL,
            last_salary=0, banned=0, license='', garage_slots=2,
            x2=0, credit=0, bank_last_updated=0, biz_income_time=0,
            tax_debt=0
        WHERE uid=?
    """, (config.START_BALANCE, uid))
    _exec("DELETE FROM cars WHERE uid=?", (uid,))
    _exec("DELETE FROM businesses WHERE uid=?", (uid,))
    _exec("DELETE FROM apartments WHERE uid=?", (uid,))
    _exec("DELETE FROM crypto_wallets WHERE uid=?", (uid,))


def set_job(uid: int, job: str | None):
    _exec("UPDATE users SET job=? WHERE uid=?", (job, uid))


def get_top(limit: int = 10):
    return _exec("""
        SELECT uid, username, game_name, balance
        FROM users WHERE banned=0 ORDER BY balance DESC LIMIT ?
    """, (limit,), fetch="all")


# ── X2 / бонус ────────────────────────────────────────────────────────────────
def has_x2(uid: int) -> bool:
    row = _exec("SELECT x2 FROM users WHERE uid=?", (uid,), fetch="one")
    return bool(row and row[0])


def set_x2(uid: int, value: bool):
    _exec("UPDATE users SET x2=? WHERE uid=?", (int(value), uid))


def has_x(uid: int, key: str) -> bool:
    if key == "x2":
        return has_x2(uid)
    row = _exec("SELECT value FROM settings WHERE key=?", (f"x_{uid}_{key}",), fetch="one")
    return bool(row and row[0] == "1")


def set_x(uid: int, key: str, value):
    if key == "x2":
        set_x2(uid, bool(value))
        return
    _exec("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)",
          (f"x_{uid}_{key}", "1" if value else "0"))


# ═══════════════════════════════════════════════════════════════════════════════
# БАНК
# ═══════════════════════════════════════════════════════════════════════════════

def bank_deposit(uid: int, amount: int):
    _exec("""
        UPDATE users SET balance=balance-?, bank=bank+?,
               bank_last_updated=? WHERE uid=?
    """, (amount, amount, int(time.time()), uid))


def bank_withdraw(uid: int, amount: int):
    _exec("""
        UPDATE users SET bank=bank-?, balance=balance+?,
               bank_last_updated=? WHERE uid=?
    """, (amount, amount, int(time.time()), uid))


def apply_bank_interest(uid: int):
    """Начисляет проценты по вкладу. Вызывать периодически."""
    row = _exec("SELECT bank, bank_last_updated FROM users WHERE uid=?", (uid,), fetch="one")
    if not row or not row[0]:
        return
    bank, last = row
    if not last:
        _exec("UPDATE users SET bank_last_updated=? WHERE uid=?", (int(time.time()), uid))
        return
    now = int(time.time())
    hours = (now - last) / 3600
    interest = int(bank * config.BANK_DEPOSIT_RATE_PER_HOUR * hours)
    if interest > 0:
        _exec("""
            UPDATE users SET bank=bank+?, bank_last_updated=? WHERE uid=?
        """, (interest, now, uid))


# ═══════════════════════════════════════════════════════════════════════════════
# АВТОМОБИЛИ
# ═══════════════════════════════════════════════════════════════════════════════

def add_car(uid: int, car_id: int, name: str, price: int, plate: str = "") -> int:
    if not plate:
        plate = gen_ru_plate()
    token = _gen_token()
    row_id = _exec("""
        INSERT INTO cars(uid, car_id, name, price, plate, token, acquired_at)
        VALUES(?,?,?,?,?,?,?)
    """, (uid, car_id, name, price, plate, token, int(time.time())))
    _exec("UPDATE statistics SET cars_bought=cars_bought+1 WHERE uid=?", (uid,))
    return row_id


def get_cars(uid: int):
    rows = _exec("SELECT car_id, name, price FROM cars WHERE uid=? ORDER BY id", (uid,), fetch="all")
    return [(r[0], r[1], r[2]) for r in rows] if rows else []


def get_cars_full(uid: int):
    return _exec("SELECT * FROM cars WHERE uid=? ORDER BY id", (uid,), fetch="all")


def get_car_ids(uid: int) -> list[int]:
    rows = _exec("SELECT car_id FROM cars WHERE uid=?", (uid,), fetch="all")
    return [r[0] for r in rows]


def get_car_by_token(token: str):
    return _exec("SELECT * FROM cars WHERE token=?", (token,), fetch="one")


def get_car_by_dbid(dbid: int):
    return _exec("SELECT * FROM cars WHERE id=?", (dbid,), fetch="one")


def get_last_car(uid: int):
    return _exec("SELECT * FROM cars WHERE uid=? ORDER BY id DESC LIMIT 1", (uid,), fetch="one")


def remove_car_db(dbid: int):
    _exec("DELETE FROM cars WHERE id=?", (dbid,))


def remove_all_cars(uid: int) -> int:
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    try:
        with c:
            cur = c.execute("DELETE FROM cars WHERE uid=?", (uid,))
            return cur.rowcount
    finally:
        c.close()


def transfer_car(dbid: int, new_uid: int):
    _exec("UPDATE cars SET uid=? WHERE id=?", (new_uid, dbid))


def get_garage_slots(uid: int) -> int:
    row = _exec("SELECT garage_slots FROM users WHERE uid=?", (uid,), fetch="one")
    return row[0] if row else 2


def update_garage_slots(uid: int, slots: int):
    _exec("UPDATE users SET garage_slots=? WHERE uid=?", (slots, uid))


def set_custom_plate(dbid: int, plate: str):
    _exec("UPDATE cars SET plate=?, custom_plate=1 WHERE id=?", (plate, dbid))


def update_car_plate(dbid: int, plate: str):
    _exec("UPDATE cars SET plate=? WHERE id=?", (plate, dbid))


# ═══════════════════════════════════════════════════════════════════════════════
# БИЗНЕСЫ
# ═══════════════════════════════════════════════════════════════════════════════

def add_business(uid: int, biz_id: int, name: str, income: int) -> int:
    token = _gen_token()
    row_id = _exec("""
        INSERT INTO businesses(uid, biz_id, name, income, token, acquired_at)
        VALUES(?,?,?,?,?,?)
    """, (uid, biz_id, name, income, token, int(time.time())))
    _exec("UPDATE statistics SET biz_bought=biz_bought+1 WHERE uid=?", (uid,))
    return row_id


def get_businesses(uid: int):
    rows = _exec("SELECT name, income FROM businesses WHERE uid=? ORDER BY id", (uid,), fetch="all")
    return [(r[0], r[1]) for r in rows] if rows else []


def get_businesses_full(uid: int):
    return _exec("SELECT * FROM businesses WHERE uid=? ORDER BY id", (uid,), fetch="all")


def get_biz_ids(uid: int) -> list[int]:
    rows = _exec("SELECT biz_id FROM businesses WHERE uid=?", (uid,), fetch="all")
    return [r[0] for r in rows]


def get_biz_owner(biz_id: int) -> int | None:
    row = _exec("SELECT uid FROM businesses WHERE biz_id=?", (biz_id,), fetch="one")
    return row[0] if row else None


def get_business_by_token(token: str):
    return _exec("SELECT * FROM businesses WHERE token=?", (token,), fetch="one")


def remove_business_db(dbid: int):
    _exec("DELETE FROM businesses WHERE id=?", (dbid,))


def remove_all_businesses(uid: int) -> int:
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    try:
        with c:
            cur = c.execute("DELETE FROM businesses WHERE uid=?", (uid,))
            return cur.rowcount
    finally:
        c.close()


def transfer_business(dbid: int, new_uid: int):
    _exec("UPDATE businesses SET uid=? WHERE id=?", (new_uid, dbid))


def get_biz_slots(uid: int) -> int:
    """Максимальное число бизнесов у игрока (базово 3)."""
    row = _exec("SELECT value FROM settings WHERE key=?", (f"biz_slots_{uid}",), fetch="one")
    return int(row[0]) if row else 3


def get_biz_income_time(uid: int) -> int:
    row = _exec("SELECT biz_income_time FROM users WHERE uid=?", (uid,), fetch="one")
    return row[0] if row else 0


def update_biz_income_time(uid: int):
    _exec("UPDATE users SET biz_income_time=? WHERE uid=?", (int(time.time()), uid))


def add_tax_debt(uid: int, amount: int):
    _exec("UPDATE users SET tax_debt=tax_debt+? WHERE uid=?", (amount, uid))


def get_tax_debt(uid: int) -> int:
    row = _exec("SELECT tax_debt FROM users WHERE uid=?", (uid,), fetch="one")
    return row[0] if row else 0


def pay_tax_debt(uid: int, amount: int) -> int:
    current = get_tax_debt(uid)
    paid = max(0, min(int(amount), current))
    if paid:
        _exec("UPDATE users SET tax_debt=MAX(0, tax_debt-?) WHERE uid=?", (paid, uid))
    return paid


# ═══════════════════════════════════════════════════════════════════════════════
# НЕДВИЖИМОСТЬ
# ═══════════════════════════════════════════════════════════════════════════════

def add_apartment(uid: int, apt_id: int, name: str, price: int) -> int:
    token = _gen_token()
    row_id = _exec("""
        INSERT INTO apartments(uid, apt_id, name, price, token, acquired_at)
        VALUES(?,?,?,?,?,?)
    """, (uid, apt_id, name, price, token, int(time.time())))
    _exec("UPDATE statistics SET apts_bought=apts_bought+1 WHERE uid=?", (uid,))
    return row_id


def get_apartments_full(uid: int):
    return _exec("SELECT * FROM apartments WHERE uid=? ORDER BY id", (uid,), fetch="all")


def get_apt_ids(uid: int) -> list[int]:
    rows = _exec("SELECT apt_id FROM apartments WHERE uid=?", (uid,), fetch="all")
    return [r[0] for r in rows]


def get_apartment_by_token(token: str):
    return _exec("SELECT * FROM apartments WHERE token=?", (token,), fetch="one")


def remove_apartment_db(dbid: int):
    _exec("DELETE FROM apartments WHERE id=?", (dbid,))


def remove_all_apartments(uid: int) -> int:
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    try:
        with c:
            cur = c.execute("DELETE FROM apartments WHERE uid=?", (uid,))
            return cur.rowcount
    finally:
        c.close()


def transfer_apartment(dbid: int, new_uid: int):
    _exec("UPDATE apartments SET uid=? WHERE id=?", (new_uid, dbid))


def get_apt_slots(uid: int) -> int:
    row = _exec("SELECT value FROM settings WHERE key=?", (f"apt_slots_{uid}",), fetch="one")
    return int(row[0]) if row else 2


# ═══════════════════════════════════════════════════════════════════════════════
# АДМИНИСТРАТОРЫ
# ═══════════════════════════════════════════════════════════════════════════════

def get_admins() -> list[int]:
    rows = _exec("SELECT uid FROM admins", fetch="all")
    return [r[0] for r in rows]


def grant_admin(uid: int, granted_by: int = 0):
    _exec("INSERT OR IGNORE INTO admins(uid, granted_by) VALUES(?,?)", (uid, granted_by))


def revoke_admin(uid: int) -> bool:
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    try:
        with c:
            cur = c.execute("DELETE FROM admins WHERE uid=?", (uid,))
            return cur.rowcount > 0
    finally:
        c.close()


def is_db_admin(uid: int) -> bool:
    row = _exec("SELECT uid FROM admins WHERE uid=?", (uid,), fetch="one")
    return row is not None


# ═══════════════════════════════════════════════════════════════════════════════
# ЛОГИ
# ═══════════════════════════════════════════════════════════════════════════════

def add_log(uid: int, action: str, details: str = "", amount: int = 0, actor_id: int = 0):
    _exec("""
        INSERT INTO logs(uid, action, details, amount, actor_id, ts)
        VALUES(?,?,?,?,?,?)
    """, (uid, action, details, amount, actor_id, int(time.time())))


# ═══════════════════════════════════════════════════════════════════════════════
# ШТРАФЫ
# ═══════════════════════════════════════════════════════════════════════════════

def add_fine(uid: int, amount: int, reason: str, article: str = "", officer_id: int = 0):
    _exec("""
        INSERT INTO fines(uid, amount, reason, article, officer_id, ts)
        VALUES(?,?,?,?,?,?)
    """, (uid, amount, reason, article, officer_id, int(time.time())))


def get_fines(uid: int, unpaid_only: bool = False):
    sql = "SELECT id, amount, reason, article, officer_id, paid, ts FROM fines WHERE uid=?"
    if unpaid_only:
        sql += " AND paid=0"
    return _exec(sql, (uid,), fetch="all")


def pay_fine(fine_id: int):
    _exec("UPDATE fines SET paid=1 WHERE id=?", (fine_id,))


def _ensure_fines_penalized_col():
    try:
        _exec("ALTER TABLE fines ADD COLUMN penalized INTEGER NOT NULL DEFAULT 0")
    except Exception:
        pass


def get_all_unpaid_old_fines():
    """Штрафы неоплаченные >24ч и ещё не оштрафованные повторно."""
    _ensure_fines_penalized_col()
    cutoff = int(time.time()) - 86400
    return _exec("""
        SELECT id, uid, amount FROM fines
        WHERE paid=0 AND ts < ? AND penalized=0
    """, (cutoff,), fetch="all") or []


def update_fine_amount(fine_id: int, new_amount: int):
    _ensure_fines_penalized_col()
    _exec("UPDATE fines SET amount=?, penalized=1 WHERE id=?", (new_amount, fine_id))


def get_unpaid_fines_total(uid: int) -> int:
    rows = _exec("SELECT amount FROM fines WHERE uid=? AND paid=0", (uid,), fetch="all")
    return sum(r[0] for r in rows) if rows else 0


def pay_all_fines_from_bank(uid: int) -> dict:
    """Погашает все неоплаченные штрафы с банка. Возвращает {'paid': X, 'remaining': Y}."""
    user = get_user(uid)
    if not user:
        return {"paid": 0, "remaining": 0}
    bank = user[5]
    fines = _exec("SELECT id, amount FROM fines WHERE uid=? AND paid=0 ORDER BY ts", (uid,), fetch="all") or []
    total_paid = 0
    remaining = 0
    for fine_id, amount in fines:
        if bank >= amount:
            bank -= amount
            total_paid += amount
            _exec("UPDATE users SET bank=bank-? WHERE uid=?", (amount, uid))
            pay_fine(fine_id)
            update_treasury(amount, "fine_payment", uid, "Оплата штрафа")
        else:
            # Частичное погашение
            if bank > 0:
                amount_left = amount - bank
                _exec("UPDATE fines SET amount=? WHERE id=?", (amount_left, fine_id))
                _exec("UPDATE users SET bank=0 WHERE uid=?", (uid,))
                update_treasury(bank, "fine_payment", uid, "Частичная оплата штрафа")
                total_paid += bank
                bank = 0
            remaining += (amount if total_paid == 0 else _exec("SELECT amount FROM fines WHERE id=?", (fine_id,), fetch="one")[0])
    return {"paid": total_paid, "remaining": remaining}


def pay_partial_fine_from_bank(uid: int, amount: int) -> dict:
    """Погашает часть штрафов на указанную сумму с банка. Возвращает {'paid': X, 'remaining': Y}."""
    user = get_user(uid)
    if not user:
        return {"paid": 0, "remaining": 0}
    bank = user[5]
    to_pay = min(amount, bank)
    if to_pay <= 0:
        return {"paid": 0, "remaining": get_unpaid_fines_total(uid)}
    fines = _exec("SELECT id, amount FROM fines WHERE uid=? AND paid=0 ORDER BY ts", (uid,), fetch="all") or []
    paid = 0
    left = to_pay
    for fine_id, fine_amt in fines:
        if left <= 0:
            break
        if left >= fine_amt:
            left -= fine_amt
            paid += fine_amt
            pay_fine(fine_id)
            update_treasury(fine_amt, "fine_payment", uid, "Оплата штрафа")
        else:
            new_amt = fine_amt - left
            _exec("UPDATE fines SET amount=? WHERE id=?", (new_amt, fine_id))
            update_treasury(left, "fine_payment", uid, "Частичная оплата штрафа")
            paid += left
            left = 0
    if paid > 0:
        _exec("UPDATE users SET bank=bank-? WHERE uid=?", (paid, uid))
    return {"paid": paid, "remaining": get_unpaid_fines_total(uid)}


# ═══════════════════════════════════════════════════════════════════════════════
# ПРОМОКОДЫ
# ═══════════════════════════════════════════════════════════════════════════════

def add_promo_code(code: str, bonus: int, max_uses: int = 0):
    _exec("""
        INSERT OR REPLACE INTO promos(code, bonus, max_uses, uses, active)
        VALUES(?, ?, ?, 0, 1)
    """, (code.upper(), bonus, max_uses))


def get_active_promos():
    return _exec("SELECT code, bonus, max_uses, uses FROM promos WHERE active=1", fetch="all")


def use_promo_code(uid: int, code: str) -> int | None:
    """Использует промокод. Возвращает сумму бонуса или None при ошибке."""
    code = code.upper()
    row = _exec("SELECT bonus, max_uses, uses, active FROM promos WHERE code=?", (code,), fetch="one")
    if not row:
        return None
    bonus, max_uses, uses, active = row
    if not active:
        return None
    if max_uses > 0 and uses >= max_uses:
        return None
    used = _exec("SELECT 1 FROM promo_uses WHERE uid=? AND code=?", (uid, code), fetch="one")
    if used:
        return None
    _exec("INSERT INTO promo_uses(uid, code) VALUES(?,?)", (uid, code))
    _exec("UPDATE promos SET uses=uses+1 WHERE code=?", (code,))
    if max_uses > 0:
        _exec("UPDATE promos SET active=CASE WHEN uses>=max_uses THEN 0 ELSE 1 END WHERE code=?", (code,))
    update_balance(uid, bonus)
    return bonus


# ═══════════════════════════════════════════════════════════════════════════════
# ЕЖЕДНЕВНЫЙ БОНУС
# ═══════════════════════════════════════════════════════════════════════════════

def init_daily_bonus_defaults():
    """Заполняет таблицу ежедневных бонусов значениями по умолчанию."""
    defaults = [
        (1,  50_000,  "День 1"),
        (2,  75_000,  "День 2"),
        (3,  100_000, "День 3"),
        (4,  125_000, "День 4"),
        (5,  150_000, "День 5"),
        (6,  200_000, "День 6"),
        (7,  300_000, "День 7 — Бонус недели!"),
    ]
    for day, amount, desc in defaults:
        _exec("""
            INSERT OR IGNORE INTO daily_bonus_rewards(
                day, amount, description, reward_type, reward_value, active
            ) VALUES(?,?,?,?,?,1)
        """, (day, amount, desc, "money", str(amount)))


def get_all_daily_bonus_rewards():
    return _exec("""
        SELECT day, reward_type, reward_value, description, active
        FROM daily_bonus_rewards ORDER BY day
    """, fetch="all") or []


def get_active_daily_bonus_rewards():
    return _exec("""
        SELECT day, reward_type, reward_value, description, active
        FROM daily_bonus_rewards WHERE active=1 ORDER BY day
    """, fetch="all") or []


def get_daily_bonus_reward(day: int):
    return _exec("""
        SELECT day, reward_type, reward_value, description, active
        FROM daily_bonus_rewards WHERE day=?
    """, (day,), fetch="one")


def get_max_bonus_day() -> int:
    row = _exec("SELECT MAX(day) FROM daily_bonus_rewards WHERE active=1", fetch="one")
    return row[0] if row and row[0] else 7


def upsert_daily_bonus_reward(
    day: int,
    reward_type: str,
    reward_value: str,
    description: str = "",
    active: bool = True,
):
    """Сохраняет награду в едином формате, сохраняя старое поле amount."""
    reward_type = str(reward_type or "money")
    reward_value = str(reward_value if reward_value is not None else "0")
    amount = 0
    if reward_type == "money":
        try:
            amount = int(float(reward_value))
        except (TypeError, ValueError):
            amount = 0
    _exec("""
        INSERT INTO daily_bonus_rewards(
            day, amount, description, reward_type, reward_value, active
        ) VALUES(?,?,?,?,?,?)
        ON CONFLICT(day) DO UPDATE SET
            amount=excluded.amount,
            description=excluded.description,
            reward_type=excluded.reward_type,
            reward_value=excluded.reward_value,
            active=excluded.active
    """, (int(day), amount, description or "", reward_type, reward_value, int(bool(active))))


def delete_daily_bonus_reward(day: int):
    _exec("DELETE FROM daily_bonus_rewards WHERE day=?", (day,))


def get_user_bonus_state(uid: int):
    row = _exec("SELECT current_day, last_claim, total_claimed FROM user_bonus WHERE uid=?", (uid,), fetch="one")
    if row:
        return {
            "current_day": row[0],
            "last_claim": row[1],
            "last_claimed": row[1],
            "total_claimed": row[2],
            "streak": row[0],
        }
    return {"current_day": 0, "last_claim": 0, "last_claimed": 0, "total_claimed": 0, "streak": 0}


def claim_daily_bonus(uid: int) -> dict:
    """Только фиксирует получение. Саму награду выдаёт bot._give_bonus_reward()."""
    now = int(time.time())
    state = get_user_bonus_state(uid)
    last = state["last_claim"]
    today_start = now - (now % 86400)
    if last >= today_start:
        return {"success": False}

    max_day = get_max_bonus_day()
    reset = last > 0 and (now - last) > 48 * 3600
    next_day = 1 if reset else (state["current_day"] % max_day) + 1
    reward_row = get_daily_bonus_reward(next_day)
    if not reward_row or not reward_row[4]:
        active = get_active_daily_bonus_rewards()
        reward_row = active[0] if active else None
    if not reward_row:
        return {"success": False}

    _, rtype, rvalue, desc, _active = reward_row
    claimed_value = 0
    if rtype == "money":
        try:
            claimed_value = int(float(rvalue))
        except (TypeError, ValueError):
            claimed_value = 0

    _exec("""
        INSERT OR REPLACE INTO user_bonus(uid, current_day, last_claim, total_claimed)
        VALUES(?, ?, ?, ?)
    """, (uid, next_day, now, state["total_claimed"] + claimed_value))
    return {
        "success": True,
        "day": next_day,
        "reward": tuple(reward_row),
        "reset": reset,
        "next_day": (next_day % max_day) + 1,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# МВД / ПРАВИТЕЛЬСТВО
# ═══════════════════════════════════════════════════════════════════════════════

def get_mvd_employee(uid: int) -> dict | None:
    row = _exec("SELECT uid, unit, role FROM mvd_employees WHERE uid=?", (uid,), fetch="one")
    return {"uid": row[0], "unit": row[1], "role": row[2]} if row else None


def set_mvd_employee(uid: int, unit: str, role: str, appointed_by: int = 0):
    _exec("""
        INSERT OR REPLACE INTO mvd_employees(uid, unit, role, appointed_by, appointed_at)
        VALUES(?,?,?,?,?)
    """, (uid, unit, role, appointed_by, int(time.time())))


def is_mvd_employee(uid: int) -> bool:
    return _exec("SELECT uid FROM mvd_employees WHERE uid=?", (uid,), fetch="one") is not None


def get_gov_employee(uid: int) -> dict | None:
    row = _exec("SELECT uid, role FROM gov_employees WHERE uid=?", (uid,), fetch="one")
    return {"uid": row[0], "role": row[1]} if row else None


def set_gov_employee(uid: int, role: str, appointed_by: int = 0):
    _exec("""
        INSERT OR REPLACE INTO gov_employees(uid, role, appointed_by, appointed_at)
        VALUES(?,?,?,?)
    """, (uid, role, appointed_by, int(time.time())))


def is_gov_employee(uid: int) -> bool:
    return _exec("SELECT uid FROM gov_employees WHERE uid=?", (uid,), fetch="one") is not None


# ═══════════════════════════════════════════════════════════════════════════════
# ОРГАНИЗАЦИИ
# ═══════════════════════════════════════════════════════════════════════════════

def get_org_name(org_type: str) -> str:
    row = _exec("SELECT name FROM organizations WHERE org_type=?", (org_type,), fetch="one")
    if row and row[0]:
        return row[0]
    return ORG_DISPLAY.get(org_type, ("🏢", org_type))[1]


def set_org_name(org_type: str, name: str):
    _exec("INSERT OR REPLACE INTO organizations(org_type, name) VALUES(?,?)", (org_type, name))


def add_org_member(org_type: str, uid: int, is_owner: bool = False):
    _exec("""
        INSERT OR IGNORE INTO org_members(org_type, uid, is_owner, joined_at)
        VALUES(?,?,?,?)
    """, (org_type, uid, int(is_owner), int(time.time())))


def remove_org_member(org_type: str, uid: int):
    _exec("DELETE FROM org_members WHERE org_type=? AND uid=?", (org_type, uid))


def get_org_members(org_type: str):
    return _exec("SELECT uid, is_owner FROM org_members WHERE org_type=?", (org_type,), fetch="all")


def get_user_orgs(uid: int):
    rows = _exec("SELECT org_type, is_owner FROM org_members WHERE uid=?", (uid,), fetch="all")
    return [(r[0], bool(r[1])) for r in rows] if rows else []


# ── Игрок-организации ─────────────────────────────────────────────────────────

def create_player_org(owner_uid: int, name: str, icon: str = "🏢") -> int:
    return _exec("""
        INSERT INTO player_orgs(owner_uid, name, icon, created_at) VALUES(?,?,?,?)
    """, (owner_uid, name, icon, int(time.time())))


def delete_player_org(org_id: int):
    _exec("DELETE FROM player_org_members WHERE org_id=?", (org_id,))
    _exec("DELETE FROM player_orgs WHERE id=?", (org_id,))


def get_player_org_by_id(org_id: int):
    return _exec("SELECT * FROM player_orgs WHERE id=?", (org_id,), fetch="one")


def get_player_org_by_name(name: str):
    return _exec("SELECT * FROM player_orgs WHERE LOWER(name)=LOWER(?)", (name,), fetch="one")


def get_player_org_members(org_id: int):
    return _exec("SELECT uid, joined_at FROM player_org_members WHERE org_id=?", (org_id,), fetch="all")


def get_player_orgs_for_user(uid: int) -> list[dict]:
    rows = _exec("""
        SELECT po.id, po.owner_uid, po.name, po.icon
        FROM player_orgs po
        LEFT JOIN player_org_members pom ON pom.org_id=po.id AND pom.uid=?
        WHERE po.owner_uid=? OR pom.uid=?
    """, (uid, uid, uid), fetch="all")
    if not rows:
        return []
    return [{"id": r[0], "owner_uid": r[1], "name": r[2], "icon": r[3]} for r in rows]


def get_orgs_owned_by(uid: int):
    return _exec("SELECT * FROM player_orgs WHERE owner_uid=?", (uid,), fetch="all")


def add_player_org_member(org_id: int, uid: int):
    _exec("""
        INSERT OR IGNORE INTO player_org_members(org_id, uid, joined_at) VALUES(?,?,?)
    """, (org_id, uid, int(time.time())))


def is_player_org_member(org_id: int, uid: int) -> bool:
    row = _exec("SELECT 1 FROM player_org_members WHERE org_id=? AND uid=?", (org_id, uid), fetch="one")
    return row is not None


# ═══════════════════════════════════════════════════════════════════════════════
# ТОТАЛИЗАТОР
# ═══════════════════════════════════════════════════════════════════════════════

def _toto_ensure_league_flag_col():
    """Добавляет колонку league_flag если её ещё нет."""
    try:
        _exec("ALTER TABLE toto_matches ADD COLUMN league_flag TEXT DEFAULT ''")
    except Exception:
        pass  # already exists


def toto_upsert_matches(matches: list[dict]):
    _toto_ensure_league_flag_col()
    for m in matches:
        # Поддерживаем оба формата ключей (home/home_team, start_ts/match_time)
        home      = m.get("home_team") or m.get("home", "")
        away      = m.get("away_team") or m.get("away", "")
        start_ts  = m.get("match_time") or m.get("start_ts", 0)
        flag      = m.get("league_flag", "")
        _exec("""
            INSERT OR REPLACE INTO toto_matches
              (match_id, home, away, league, league_flag, start_ts, status,
               odds_home, odds_draw, odds_away, updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)
        """, (m["match_id"], home, away, m.get("league", ""), flag,
              start_ts, m.get("status", "upcoming"),
              m.get("odds_home", 2.0), m.get("odds_draw", 3.0), m.get("odds_away", 2.0),
              int(time.time())))


def _toto_row_to_dict(r) -> dict:
    """Превращает кортеж toto_matches в dict с ключами, которых ждёт UI."""
    # Порядок: match_id, home, away, league, start_ts, status, result,
    #          odds_home, odds_draw, odds_away, updated_at, [league_flag]
    league_flag = r[11] if len(r) > 11 else ""
    return {
        "match_id":    r[0],
        "home_team":   r[1],
        "away_team":   r[2],
        "league":      r[3],
        "match_time":  r[4],
        "status":      r[5],
        "result":      r[6],
        "odds_home":   r[7],
        "odds_draw":   r[8],
        "odds_away":   r[9],
        "updated_at":  r[10],
        "league_flag": league_flag,
    }


def toto_get_upcoming_matches():
    _toto_ensure_league_flag_col()
    now = int(time.time())
    rows = _exec("""
        SELECT match_id, home, away, league, start_ts, status, result,
               odds_home, odds_draw, odds_away, updated_at,
               COALESCE(league_flag, '') AS league_flag
        FROM toto_matches WHERE status='upcoming' AND start_ts>?
        ORDER BY start_ts LIMIT 20
    """, (now,), fetch="all")
    return [_toto_row_to_dict(r) for r in rows] if rows else []


def toto_get_match(match_id: str):
    _toto_ensure_league_flag_col()
    r = _exec("""
        SELECT match_id, home, away, league, start_ts, status, result,
               odds_home, odds_draw, odds_away, updated_at,
               COALESCE(league_flag, '') AS league_flag
        FROM toto_matches WHERE match_id=?
    """, (match_id,), fetch="one")
    return _toto_row_to_dict(r) if r else None


def toto_place_bet(uid: int, match_id: str, outcome: str, amount: int, odds: float = 1.0):
    _exec("""
        INSERT INTO toto_bets(uid, match_id, outcome, amount, odds, ts)
        VALUES(?,?,?,?,?,?)
    """, (uid, match_id, outcome, amount, odds, int(time.time())))
    update_balance(uid, -amount)


def toto_get_user_bets(uid: int, status: str = None):
    _toto_ensure_league_flag_col()
    rows = _exec("""
        SELECT tb.id, tb.uid, tb.match_id, tb.outcome, tb.amount, tb.odds,
               tb.resolved, tb.won, tb.payout, tb.ts,
               tm.home, tm.away, tm.league, tm.start_ts, tm.status,
               COALESCE(tm.league_flag, '') AS league_flag
        FROM toto_bets tb JOIN toto_matches tm ON tb.match_id=tm.match_id
        WHERE tb.uid=? ORDER BY tb.ts DESC LIMIT 20
    """, (uid,), fetch="all")
    if not rows:
        return []
    result = []
    for r in rows:
        resolved, won, payout = r[6], r[7], r[8]
        if resolved == 0:
            bet_status = "pending"
        elif won == 1:
            bet_status = "won"
        else:
            bet_status = "lost"
        # odds хранит реальный коэффициент; потенциальный выигрыш = ставка × коэффициент.
        potential = int(payout) if (resolved == 1 and won == 1) else int(r[4] * r[5])
        result.append({
            "id": r[0], "uid": r[1], "match_id": r[2],
            "bet_type": r[3], "amount": r[4],
            "potential_win": potential,
            "payout": payout, "ts": r[9],
            "home_team": r[10], "away_team": r[11], "league": r[12],
            "match_time": r[13], "league_flag": r[15],
            "status": bet_status,
            "home_score": -1, "away_score": -1,
        })
    if status is not None:
        result = [b for b in result if b["status"] == status]
    return result


def toto_get_pending_for_resolution(match_id: str):
    rows = _exec("""
        SELECT id, uid, match_id, outcome, amount, odds, resolved, won, payout, ts
        FROM toto_bets WHERE match_id=? AND resolved=0
    """, (match_id,), fetch="all")
    if not rows:
        return []
    return [{"id": r[0], "uid": r[1], "match_id": r[2], "outcome": r[3],
             "amount": r[4], "odds": r[5], "resolved": r[6], "won": r[7],
             "payout": r[8], "ts": r[9]}
            for r in rows]


def toto_get_pending_match_ids():
    rows = _exec(
        "SELECT DISTINCT match_id FROM toto_bets WHERE resolved=0",
        fetch="all"
    ) or []
    return [str(r[0]) for r in rows]


def toto_resolve_match(match_id: str, outcome: str, multiplier: float = 1.0):
    bets = toto_get_pending_for_resolution(match_id)
    _exec("UPDATE toto_matches SET status='finished', result=? WHERE match_id=?", (outcome, match_id))
    for bet in bets:
        bet_id, uid = bet["id"], bet["uid"]
        won = bet["outcome"] == outcome
        payout = int(bet["amount"] * bet["odds"]) if won else 0
        if payout:
            update_balance(uid, payout)
        _exec("""
            UPDATE toto_bets SET resolved=1, won=?, payout=? WHERE id=?
        """, (int(won), payout, bet_id))


# ═══════════════════════════════════════════════════════════════════════════════
# КАЗНА
# ═══════════════════════════════════════════════════════════════════════════════

def get_treasury() -> int:
    row = _exec("SELECT balance FROM treasury WHERE id=1", fetch="one")
    return row[0] if row else 0


def update_treasury(amount: int, source_type: str = "", source_uid: int = 0, description: str = ""):
    _exec("UPDATE treasury SET balance=balance+? WHERE id=1", (amount,))
    if source_type:
        _exec("""
            INSERT INTO treasury_logs(amount, source_type, source_uid, description, ts)
            VALUES(?,?,?,?,?)
        """, (amount, source_type, source_uid, description, int(time.time())))


def get_treasury_logs(limit: int = 50):
    limit = max(1, min(int(limit), 500))
    return _exec(
        "SELECT id, amount, source_type, source_uid, description, ts "
        "FROM treasury_logs ORDER BY ts DESC LIMIT ?",
        (limit,), fetch="all"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ЛИЦЕНЗИИ
# ═══════════════════════════════════════════════════════════════════════════════

def has_license(uid: int, license_type: str) -> bool:
    row = _exec("SELECT active FROM licenses WHERE uid=? AND license=?", (uid, license_type), fetch="one")
    return bool(row and row[0])


def set_license(uid: int, license_type: str, value: bool = True):
    if value:
        _exec("""
            INSERT OR REPLACE INTO licenses(uid, license, active, issued_at) VALUES(?,?,1,?)
        """, (uid, license_type, int(time.time())))
    else:
        _exec("DELETE FROM licenses WHERE uid=? AND license=?", (uid, license_type))


# ═══════════════════════════════════════════════════════════════════════════════
# КАТАЛОГ (admin-добавленные объекты)
# ═══════════════════════════════════════════════════════════════════════════════

def add_catalog_item(item_type: str, game_id: int, name: str, price: int, income: int = 0):
    _exec("""
        INSERT OR REPLACE INTO catalog(type, game_id, name, price, income, active)
        VALUES(?,?,?,?,?,1)
    """, (item_type, game_id, name, price, income))


def get_catalog_items(item_type: str):
    return _exec("""
        SELECT id, type, game_id, name, price, income FROM catalog WHERE type=? AND active=1
    """, (item_type,), fetch="all")


# ═══════════════════════════════════════════════════════════════════════════════
# КАЗИНО
# ═══════════════════════════════════════════════════════════════════════════════

def get_casino_plays(uid: int, date: str) -> int:
    row = _exec("SELECT plays FROM casino_plays WHERE uid=? AND date=?", (uid, date), fetch="one")
    return row[0] if row else 0


def increment_casino_plays(uid: int, date: str):
    _exec("""
        INSERT INTO casino_plays(uid, date, plays) VALUES(?,?,1)
        ON CONFLICT(uid, date) DO UPDATE SET plays=plays+1
    """, (uid, date))


# ═══════════════════════════════════════════════════════════════════════════════
# КЕЙСЫ
# ═══════════════════════════════════════════════════════════════════════════════

def get_cases(uid: int) -> dict[str, int]:
    """Возвращает {case_type: count} для игрока."""
    rows = _exec("SELECT case_type, count FROM cases WHERE uid=? AND count>0", (uid,), fetch="all")
    return {r[0]: r[1] for r in rows} if rows else {}


def get_case_count(uid: int, case_type: str) -> int:
    row = _exec("SELECT count FROM cases WHERE uid=? AND case_type=?", (uid, case_type), fetch="one")
    return row[0] if row else 0


def add_cases(uid: int, case_type: str, count: int = 1):
    """Добавляет кейсы в инвентарь игрока."""
    _exec("""
        INSERT INTO cases(uid, case_type, count) VALUES(?,?,?)
        ON CONFLICT(uid, case_type) DO UPDATE SET count=count+?
    """, (uid, case_type, count, count))


def remove_cases(uid: int, case_type: str, count: int = 1) -> bool:
    """Удаляет кейсы. Возвращает False если недостаточно."""
    current = get_case_count(uid, case_type)
    if current < count:
        return False
    _exec("UPDATE cases SET count=count-? WHERE uid=? AND case_type=?", (count, uid, case_type))
    return True


def log_case_open(uid: int, case_type: str, reward_type: str, reward_label: str, reward_value: str):
    _exec("""
        INSERT INTO case_history(uid, case_type, reward_type, reward_label, reward_value, ts)
        VALUES(?,?,?,?,?,?)
    """, (uid, case_type, reward_type, reward_label, reward_value, int(time.time())))
    _exec("UPDATE statistics SET cases_opened=cases_opened+1 WHERE uid=?", (uid,))




# ═══════════════════════════════════════════════════════════════════════════════
# БАНКОВСКИЕ ОПЕРАЦИИ
# ═══════════════════════════════════════════════════════════════════════════════

def add_bank_operation(uid: int, type_: str, amount: int, balance_after: int, bank_after: int, description: str = ""):
    _exec("""
        INSERT INTO bank_operations(uid, type, amount, balance_after, bank_after, description, ts)
        VALUES(?,?,?,?,?,?,?)
    """, (uid, type_, amount, balance_after, bank_after, description, int(time.time())))


def get_bank_operations(uid: int, limit: int = 20):
    return _exec("""
        SELECT type, amount, balance_after, bank_after, description, ts
        FROM bank_operations WHERE uid=? ORDER BY ts DESC LIMIT ?
    """, (uid, limit), fetch="all")


# ═══════════════════════════════════════════════════════════════════════════════
# ИСТОРИЯ БОНУСОВ
# ═══════════════════════════════════════════════════════════════════════════════

def log_bonus_received(uid: int, day: int, reward_type: str, reward_value: str):
    _exec("""
        INSERT INTO bonus_history(uid, day, reward_type, reward_value, ts)
        VALUES(?,?,?,?,?)
    """, (uid, day, reward_type, reward_value, int(time.time())))


def get_bonus_history(uid: int, limit: int = 50):
    return _exec("""
        SELECT day, reward_type, reward_value, ts
        FROM bonus_history WHERE uid=? ORDER BY ts DESC LIMIT ?
    """, (uid, limit), fetch="all")


def get_max_bonus_day_reached(uid: int) -> int:
    row = _exec("SELECT MAX(day) FROM bonus_history WHERE uid=?", (uid,), fetch="one")
    return row[0] if row and row[0] else 0


# ═══════════════════════════════════════════════════════════════════════════════
# СПОРТИВНЫЕ КОМАНДЫ (Ф1 / Футбол)
# ═══════════════════════════════════════════════════════════════════════════════

def create_sports_team(owner_uid: int, team_type: str, name: str, logo: str = "") -> int:
    """Создаёт спортивную команду. team_type: 'f1' или 'football'"""
    return _exec("""
        INSERT INTO player_orgs(owner_uid, name, icon, created_at)
        VALUES(?,?,?,?)
    """, (owner_uid, f"[{team_type.upper()}] {name}", logo, int(time.time())))


def get_sports_teams_for_user(uid: int) -> list[dict]:
    """Возвращает спортивные команды пользователя."""
    rows = _exec("""
        SELECT id, owner_uid, name, icon, created_at
        FROM player_orgs WHERE owner_uid=? AND (name LIKE '[F1] %' OR name LIKE '[FOOTBALL] %')
    """, (uid,), fetch="all")
    if not rows:
        return []
    result = []
    for r in rows:
        name = r[2]
        team_type = "f1" if name.startswith("[F1] ") else "football"
        display_name = name[5:] if name.startswith("[F1] ") else (name[11:] if name.startswith("[FOOTBALL] ") else name)
        result.append({
            "id": r[0], "owner_uid": r[1], "type": team_type,
            "name": display_name, "icon": r[3], "created_at": r[4]
        })
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# КРЕДИТЫ
# ═══════════════════════════════════════════════════════════════════════════════

def add_credit(uid: int, amount: int, interest_rate: float, term_days: int):
    """Выдаёт кредит."""
    due_date = int(time.time()) + term_days * 86400
    _exec("""
        INSERT INTO credits(uid, amount, interest_rate, term_days, due_date, issued_at)
        VALUES(?,?,?,?,?,?)
    """, (uid, amount, interest_rate, term_days, due_date, int(time.time())))
    update_balance(uid, amount)


def get_credits(uid: int, active_only: bool = True):
    sql = "SELECT id, amount, interest_rate, term_days, paid, due_date, issued_at FROM credits WHERE uid=?"
    if active_only:
        sql += " AND paid < amount"
    sql += " ORDER BY issued_at DESC"
    return _exec(sql, (uid,), fetch="all")


def get_credit_debt(uid: int) -> int:
    """Возвращает сумму непогашенного кредита с процентами."""
    rows = _exec("SELECT amount, interest_rate, term_days, paid, issued_at FROM credits WHERE uid=? AND paid < amount", (uid,), fetch="all")
    total = 0
    now = int(time.time())
    for amount, rate, term, paid, issued in rows:
        days_passed = (now - issued) / 86400
        interest = int(amount * (rate / 100) * (days_passed / term))
        total += amount + interest - paid
    return max(0, total)


def pay_credit(credit_id: int, amount: int) -> int:
    """Погашает часть кредита. Возвращает остаток долга."""
    row = _exec("SELECT amount, paid FROM credits WHERE id=?", (credit_id,), fetch="one")
    if not row:
        return 0
    total, paid = row
    new_paid = min(paid + amount, total * 2)  # max 2x (100% interest)
    _exec("UPDATE credits SET paid=? WHERE id=?", (new_paid, credit_id))
    return max(0, total * 2 - new_paid)

# ═══════════════════════════════════════════════════════════════════════════════
# НАСТРОЙКИ (key-value)
# ═══════════════════════════════════════════════════════════════════════════════

def set_setting(key: str, value: str):
    _exec("INSERT OR REPLACE INTO settings(key, value) VALUES(?,?)", (key, value))


def get_setting(key: str, default: str = "") -> str:
    row = _exec("SELECT value FROM settings WHERE key=?", (key,), fetch="one")
    return row[0] if row else default


# ═══════════════════════════════════════════════════════════════════════════════
# РЕЗЕРВНОЕ КОПИРОВАНИЕ
# ═══════════════════════════════════════════════════════════════════════════════

def backup_db():
    """Создаёт резервную копию базы данных."""
    os.makedirs(config.DB_BACKUP_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(config.DB_BACKUP_DIR, f"advance_rp_{ts}.db")
    shutil.copy2(DB_PATH, dest)
    # Оставляем последние 24 бэкапа
    backups = sorted(
        [f for f in os.listdir(config.DB_BACKUP_DIR) if f.endswith(".db")],
        reverse=True
    )
    for old in backups[24:]:
        try:
            os.remove(os.path.join(config.DB_BACKUP_DIR, old))
        except Exception:
            pass
    return dest
