
import sqlite3
import random

DB_NAME = "giveaway.db"


def connect():
    return sqlite3.connect(DB_NAME, timeout=15)


def init_db():
    with connect() as db:

        db.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                chat_id INTEGER PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                title TEXT
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS participants (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS giveaway (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                registration_closed INTEGER DEFAULT 0
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS winners (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                selected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        db.execute("""
            INSERT OR IGNORE INTO giveaway
            (id, registration_closed)
            VALUES (1, 0)
        """)


# -------------------------
# КАНАЛЫ
# -------------------------

def add_channel(chat_id, username, title):

    with connect() as db:
        try:
            db.execute("""
                INSERT INTO channels
                (chat_id, username, title)
                VALUES (?, ?, ?)
            """, (chat_id, username.lower(), title))

            return True

        except sqlite3.IntegrityError:
            return False


def remove_channel(username):

    with connect() as db:
        cursor = db.execute("""
            DELETE FROM channels
            WHERE username = ?
        """, (username.lower(),))

        return cursor.rowcount > 0


def get_channels():

    with connect() as db:
        return db.execute("""
            SELECT chat_id, username, title
            FROM channels
            ORDER BY username
        """).fetchall()


# -------------------------
# УЧАСТНИКИ
# -------------------------

def add_participant(user_id, username, full_name):

    with connect() as db:

        state = db.execute("""
            SELECT registration_closed
            FROM giveaway WHERE id = 1
        """).fetchone()

        if not state or state[0]:
            return False

        cursor = db.execute("""
            INSERT OR IGNORE INTO participants
            (user_id, username, full_name)
            VALUES (?, ?, ?)
        """, (user_id, username, full_name))

        return cursor.rowcount == 1


def get_participants_count():

    with connect() as db:
        return db.execute("""
            SELECT COUNT(*)
            FROM participants
        """).fetchone()[0]


# -------------------------
# РЕГИСТРАЦИЯ
# -------------------------

def is_registration_closed():

    with connect() as db:
        result = db.execute("""
            SELECT registration_closed
            FROM giveaway WHERE id = 1
        """).fetchone()

        return bool(result[0])


# -------------------------
# ВЫБОР ПОБЕДИТЕЛЯ
# -------------------------


def draw_winner():

    with connect() as db:

        db.execute("BEGIN IMMEDIATE")

        state = db.execute("""
            SELECT registration_closed
            FROM giveaway WHERE id = 1
        """).fetchone()

        if not state:
            db.rollback()
            return None, "error"

        participants = db.execute("""
            SELECT p.user_id, p.username, p.full_name
            FROM participants p
            LEFT JOIN winners w
            ON p.user_id = w.user_id
            WHERE w.user_id IS NULL
        """).fetchall()

        if not participants:
            db.rollback()
            return None, "empty"

        # Закрываем регистрацию только при успешном выборе.
        db.execute("""
            UPDATE giveaway
            SET registration_closed = 1
            WHERE id = 1
        """)

        winner = random.SystemRandom().choice(participants)

        db.execute("""
            INSERT INTO winners
            (user_id, username, full_name)
            VALUES (?, ?, ?)
        """, winner)

        db.commit()

        return winner, "success"



def get_winners():

    with connect() as db:
        return db.execute("""
            SELECT user_id, username, full_name, selected_at
            FROM winners
            ORDER BY selected_at, rowid
        """).fetchall()


def get_winners_count():

    with connect() as db:
        return db.execute("""
            SELECT COUNT(*) FROM winners
        """).fetchone()[0]
