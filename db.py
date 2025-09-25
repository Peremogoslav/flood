# db.py
import sqlite3
import os
from constants import DB_FILE
from rich.console import Console

console = Console()
_conn = None

def get_conn():
    global _conn
    if _conn is None:
        os.makedirs(os.path.dirname(DB_FILE) or ".", exist_ok=True)
        _conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
    return _conn

def init_db():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone TEXT UNIQUE,
        session_file TEXT
    )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS ip_ranges (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        prefix TEXT UNIQUE NOT NULL
    )
    ''')
    conn.commit()

    cursor.execute("SELECT COUNT(*) as c FROM ip_ranges")
    if cursor.fetchone()["c"] == 0:
        default_prefixes = [('10.244.102.',), ('10.244.112.',), ('10.241.119.',), ('10.244.82.',)]
        cursor.executemany("INSERT INTO ip_ranges (prefix) VALUES (?)", default_prefixes)
        conn.commit()
        console.print("[green][INFO][/green] Таблица IP-диапазонов заполнена значениями по умолчанию.")

def delete_session(session_file: str):
    try:
        conn = get_conn()
        cursor = conn.cursor()

        # Приводим к basename (без пути)
        base_name = os.path.basename(session_file)
        if not base_name.endswith(".session"):
            base_name = f"{base_name}.session"

        # Удаляем либо по basename, либо по полному пути
        cursor.execute(
            "DELETE FROM sessions WHERE session_file = ? OR session_file = ?",
            (session_file, base_name)
        )
        conn.commit()

        return cursor.rowcount > 0
    except Exception as e:
        console.print(f"[red][DB ERROR][/red] {e}")
        return False



def close_conn():
    global _conn
    if _conn:
        _conn.close()
        _conn = None
        console.print("[blue][INFO][/blue] Соединение с базой данных закрыто.")
