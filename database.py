
import sqlite3
import random
from contextlib import contextmanager

DB_NAME = "giveaway.db"


@contextmanager
def connect():
    db = sqlite3.connect(DB_NAME, timeout=15)
    db.execute("PRAGMA foreign_keys = ON")

    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# -------------------------
# ИНИЦИАЛИЗАЦИЯ И МИГРАЦИЯ
# -------------------------

def init_db():
    with connect() as db:

        # Каналы
        db.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                chat_id INTEGER PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                title TEXT
            )
        """)

        # Все розыгрыши
        db.execute("""
            CREATE TABLE IF NOT EXISTS giveaways (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                status TEXT NOT NULL DEFAULT 'active'
                    CHECK(status IN ('active', 'completed')),
                registration_closed INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        """)

        # Участники каждого розыгрыша
        db.execute("""
            CREATE TABLE IF NOT EXISTS giveaway_participants (
                giveaway_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                username TEXT,
                full_name TEXT,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                PRIMARY KEY (giveaway_id, user_id),

                FOREIGN KEY (giveaway_id)
                    REFERENCES giveaways(id)
            )
        """)

        # Победители каждого розыгрыша
        db.execute("""
            CREATE TABLE IF NOT EXISTS giveaway_winners (
                giveaway_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                username TEXT,
                full_name TEXT,
                selected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                PRIMARY KEY (giveaway_id, user_id),

                FOREIGN KEY (giveaway_id)
                    REFERENCES giveaways(id)
            )
        """)

        # Проверяем, есть ли старая база с одним розыгрышем
        old_giveaway = db.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name = 'giveaway'
        """).fetchone()

        giveaways_count = db.execute("""
            SELECT COUNT(*) FROM giveaways
        """).fetchone()[0]

        # Переносим старые данные только при первой миграции
        if giveaways_count == 0:

            old_state = db.execute("""
                SELECT registration_closed
                FROM giveaway
                WHERE id = 1
            """).fetchone() if old_giveaway else None

            registration_closed = (
                int(old_state[0]) if old_state else 0
            )

            db.execute("""
                INSERT INTO giveaways
                (id, status, registration_closed)
                VALUES (1, 'active', ?)
            """, (registration_closed,))

            # Перенос старых участников
            old_participants = db.execute("""
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'participants'
            """).fetchone()

            if old_participants:
                db.execute("""
                    INSERT OR IGNORE INTO giveaway_participants
                    (giveaway_id, user_id, username, full_name, joined_at)
                    SELECT 1, user_id, username, full_name, joined_at
                    FROM participants
                """)

            # Перенос старых победителей
            old_winners = db.execute("""
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'winners'
            """).fetchone()

            if old_winners:
                db.execute("""
                    INSERT OR IGNORE INTO giveaway_winners
                    (giveaway_id, user_id, username, full_name, selected_at)
                    SELECT 1, user_id, username, full_name, selected_at
                    FROM winners
                """)

        db.execute("""
            CREATE INDEX IF NOT EXISTS idx_participants_giveaway
            ON giveaway_participants(giveaway_id)
        """)

        db.execute("""
            CREATE INDEX IF NOT EXISTS idx_winners_giveaway
            ON giveaway_winners(giveaway_id)
        """)


# -------------------------
# КАНАЛЫ
# -------------------------

def add_channel(chat_id, username, title):
    with connect() as db:
        try:
            db.execute("""
                INSERT INTO channels (chat_id, username, title)
                VALUES (?, ?, ?)
            """, (chat_id, username.lower().lstrip("@"), title))
            return True
        except sqlite3.IntegrityError:
            return False


def remove_channel(username):
    with connect() as db:
        cursor = db.execute("""
            DELETE FROM channels
            WHERE username = ?
        """, (username.lower().lstrip("@"),))

        return cursor.rowcount > 0


def get_channels():
    with connect() as db:
        return db.execute("""
            SELECT chat_id, username, title
            FROM channels
            ORDER BY username
        """).fetchall()


# -------------------------
# РОЗЫГРЫШИ
# -------------------------

def get_active_giveaway():
    with connect() as db:
        return db.execute("""
            SELECT id, status, registration_closed, created_at
            FROM giveaways
            WHERE status = 'active'
            ORDER BY id DESC
            LIMIT 1
        """).fetchone()


def create_giveaway():
    """
    Создаёт новый розыгрыш.
    Возвращает ID нового розыгрыша.
    Если предыдущий ещё активен, возвращает None.
    """

    with connect() as db:
        db.execute("BEGIN IMMEDIATE")

        active = db.execute("""
            SELECT id FROM giveaways
            WHERE status = 'active'
            LIMIT 1
        """).fetchone()

        if active:
            return None

        cursor = db.execute("""
            INSERT INTO giveaways
            (status, registration_closed)
            VALUES ('active', 0)
        """)

        return cursor.lastrowid


def finish_giveaway():
    """
    Завершает текущий розыгрыш.
    Возвращает True при успехе, иначе False.
    """

    with connect() as db:
        db.execute("BEGIN IMMEDIATE")

        cursor = db.execute("""
            UPDATE giveaways
            SET status = 'completed',
                registration_closed = 1,
                completed_at = CURRENT_TIMESTAMP
            WHERE status = 'active'
        """)

        return cursor.rowcount > 0


def get_giveaways_history():
    with connect() as db:
        return db.execute("""
            SELECT id, status, created_at, completed_at
            FROM giveaways
            ORDER BY id DESC
        """).fetchall()


def _get_giveaway_id(db, giveaway_id=None):
    if giveaway_id is not None:
        return giveaway_id

    result = db.execute("""
        SELECT id FROM giveaways
        WHERE status = 'active'
        ORDER BY id DESC
        LIMIT 1
    """).fetchone()

    if result:
        return result[0]

    result = db.execute("""
        SELECT id FROM giveaways
        ORDER BY id DESC
        LIMIT 1
    """).fetchone()

    return result[0] if result else None


# -------------------------
# УЧАСТНИКИ
# -------------------------

def add_participant(user_id, username, full_name):
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")

        giveaway = db.execute("""
            SELECT id
            FROM giveaways
            WHERE status = 'active'
              AND registration_closed = 0
            ORDER BY id DESC
            LIMIT 1
        """).fetchone()

        if not giveaway:
            return False

        cursor = db.execute("""
            INSERT OR IGNORE INTO giveaway_participants
            (giveaway_id, user_id, username, full_name)
            VALUES (?, ?, ?, ?)
        """, (giveaway[0], user_id, username, full_name))

        return cursor.rowcount == 1


def get_participants_count(giveaway_id=None):
    with connect() as db:
        giveaway_id = _get_giveaway_id(db, giveaway_id)

        if giveaway_id is None:
            return 0

        return db.execute("""
            SELECT COUNT(*)
            FROM giveaway_participants
            WHERE giveaway_id = ?
        """, (giveaway_id,)).fetchone()[0]


# -------------------------
# РЕГИСТРАЦИЯ
# -------------------------

def is_registration_closed():
    with connect() as db:
        result = db.execute("""
            SELECT registration_closed
            FROM giveaways
            WHERE status = 'active'
            ORDER BY id DESC
            LIMIT 1
        """).fetchone()

        return True if not result else bool(result[0])


# -------------------------
# ВЫБОР ПОБЕДИТЕЛЯ
# -------------------------

def draw_winner():
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")

        giveaway = db.execute("""
            SELECT id, registration_closed
            FROM giveaways
            WHERE status = 'active'
            ORDER BY id DESC
            LIMIT 1
        """).fetchone()

        if not giveaway:
            return None, "error"

        giveaway_id, registration_closed = giveaway

        participants = db.execute("""
            SELECT p.user_id, p.username, p.full_name
            FROM giveaway_participants p
            LEFT JOIN giveaway_winners w
                ON p.giveaway_id = w.giveaway_id
                AND p.user_id = w.user_id
            WHERE p.giveaway_id = ?
              AND w.user_id IS NULL
        """, (giveaway_id,)).fetchall()

        if not participants:
            return None, "empty"

        # Первый выбор закрывает регистрацию
        db.execute("""
            UPDATE giveaways
            SET registration_closed = 1
            WHERE id = ?
        """, (giveaway_id,))

        winner = random.SystemRandom().choice(participants)

        db.execute("""
            INSERT INTO giveaway_winners
            (giveaway_id, user_id, username, full_name)
            VALUES (?, ?, ?, ?)
        """, (giveaway_id, *winner))

        return winner, "success"


# -------------------------
# СПИСОК ПОБЕДИТЕЛЕЙ
# -------------------------

def get_winners(giveaway_id=None):
    with connect() as db:
        giveaway_id = _get_giveaway_id(db, giveaway_id)

        if giveaway_id is None:
            return []

        return db.execute("""
            SELECT user_id, username, full_name, selected_at
            FROM giveaway_winners
            WHERE giveaway_id = ?
            ORDER BY selected_at, rowid
        """, (giveaway_id,)).fetchall()


def get_winners_count(giveaway_id=None):
    with connect() as db:
        giveaway_id = _get_giveaway_id(db, giveaway_id)

        if giveaway_id is None:
            return 0

        return db.execute("""
            SELECT COUNT(*)
            FROM giveaway_winners
            WHERE giveaway_id = ?
        """, (giveaway_id,)).fetchone()[0]
