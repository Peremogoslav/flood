# utils.py
import socket
import pwinput
from rich.console import Console
from db import get_conn
from constants import DEFAULT_PASSWORD

console = Console()

def get_local_ipv4():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 1))
        ip = s.getsockname()[0]
    except Exception:
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            ip = "127.0.0.1"
    finally:
        s.close()
    return ip

def check_access():
    conn = get_conn()
    cursor = conn.cursor()
    ip = get_local_ipv4()
    cursor.execute("SELECT prefix FROM ip_ranges")
    allowed_prefixes = [row["prefix"] for row in cursor.fetchall()]
    if any(ip.startswith(prefix) for prefix in allowed_prefixes):
        console.print(f"[green][INFO][/green] Доступ разрешен. Ваш IP: {ip}")
        return True

    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        entered_password = pwinput.pwinput(
            prompt=f"Ваш IP ({ip}) не входит в диапазон. Попытка {attempt}/{max_attempts}.\nВведите пароль для продолжения: ",
            mask="*"
        )
        if entered_password == DEFAULT_PASSWORD:
            console.print("[green][SUCCESS][/green] Пароль принят. Доступ разрешен.")
            return True
        else:
            console.print("[red][FAILED][/red] Неверный пароль!")
    console.print("[red][FAILED][/red] Превышено число попыток. Доступ запрещен.")
    return False
