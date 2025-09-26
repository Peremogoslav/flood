import asyncio
import os
import sys
import pwinput
import requests
from rich.console import Console
from rich.panel import Panel
from rich import box


API_BASE = os.getenv("API_BASE", "http://localhost:8000")
console = Console()


def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


def print_header():
    console.print(Panel.fit("[bold cyan]TELEGRAM MANAGER CLI (API)[/bold cyan]", box=box.DOUBLE, padding=(1, 2)))


def wait_key():
    input("\nНажмите Enter для продолжения...")


def menu_accounts():
    while True:
        clear_screen()
        print_header()
        console.print("[bold magenta]Аккаунты[/bold magenta]\n")
        console.print("1. Показать аккаунты")
        console.print("2. Начать авторизацию (отправить код)")
        console.print("3. Подтвердить авторизацию (код/2FA)")
        console.print("4. Удалить аккаунт")
        console.print("0. Назад\n")
        ch = input("Выберите действие: ").strip()
        if ch == "1":
            r = requests.get(f"{API_BASE}/accounts/")
            if r.ok:
                data = r.json()
                if not data:
                    console.print("[yellow]Нет аккаунтов[/yellow]")
                else:
                    for a in data:
                        console.print(f"- {a['id']}: {a['phone']}")
            else:
                console.print(f"[red]Ошибка: {r.status_code} {r.text}")
            wait_key()
        elif ch == "2":
            phone = input("Телефон (+7...): ").strip()
            r = requests.post(f"{API_BASE}/auth/start", json={"phone": phone})
            console.print(r.json() if r.ok else f"[red]Ошибка: {r.status_code} {r.text}")
            wait_key()
        elif ch == "3":
            phone = input("Телефон (+7...): ").strip()
            code = input("Код (если есть, иначе Enter): ").strip()
            password = pwinput.pwinput(prompt="Пароль 2FA (если есть, иначе Enter): ", mask="*")
            payload = {"phone": phone, "code": code or None, "password": password or None}
            r = requests.post(f"{API_BASE}/auth/verify", json=payload)
            console.print(r.json() if r.ok else f"[red]Ошибка: {r.status_code} {r.text}")
            wait_key()
        elif ch == "4":
            acc_id = input("ID аккаунта для удаления: ").strip()
            r = requests.delete(f"{API_BASE}/accounts/{acc_id}")
            console.print("Удалено" if r.status_code == 204 else f"[red]Ошибка: {r.status_code} {r.text}")
            wait_key()
        elif ch == "0":
            break


def menu_config():
    while True:
        clear_screen()
        print_header()
        console.print("[bold magenta]Настройки[/bold magenta]\n")
        r = requests.get(f"{API_BASE}/config/")
        cfg = r.json() if r.ok else {}
        console.print(str(cfg))
        console.print("\n1. Обновить настройки")
        console.print("0. Назад\n")
        ch = input("Выберите действие: ").strip()
        if ch == "1":
            try:
                min_delay = int(input("min_delay: ").strip() or cfg.get("min_delay", 10))
                max_delay = int(input("max_delay: ").strip() or cfg.get("max_delay", 15))
            except ValueError:
                console.print("[red]Неверные значения[/red]")
                wait_key()
                continue
            randomize = input(f"randomize_chats (y/n, сейчас {cfg.get('randomize_chats')}): ").strip().lower() in ("y", "да", "1", "true")
            use_images = input(f"use_images (y/n, сейчас {cfg.get('use_images')}): ").strip().lower() in ("y", "да", "1", "true")
            payload = {"min_delay": min_delay, "max_delay": max_delay, "randomize_chats": randomize, "use_images": use_images}
            r2 = requests.put(f"{API_BASE}/config/", json=payload)
            console.print(r2.json() if r2.ok else f"[red]Ошибка: {r2.status_code} {r2.text}")
            wait_key()
        elif ch == "0":
            break


def menu_folders():
    while True:
        clear_screen()
        print_header()
        console.print("[bold magenta]Папки[/bold magenta]\n")
        console.print("1. Подключить addlist к выбранным аккаунтам")
        console.print("0. Назад\n")
        ch = input("Выберите действие: ").strip()
        if ch == "1":
            r = requests.get(f"{API_BASE}/accounts/")
            accs = r.json() if r.ok else []
            if not accs:
                console.print("[yellow]Нет аккаунтов[/yellow]")
                wait_key()
                continue
            console.print("Доступные аккаунты:")
            for a in accs:
                console.print(f"- {a['id']}: {a['phone']}")
            ids = input("Введите ID через запятую: ").strip()
            try:
                id_list = [int(x.strip()) for x in ids.split(",") if x.strip()]
            except ValueError:
                console.print("[red]Неверный формат ID[/red]")
                wait_key()
                continue
            link = input("Ссылка addlist: ").strip()
            r2 = requests.post(f"{API_BASE}/folders/addlist", json={"phone_ids": id_list, "link": link})
            console.print(r2.json() if r2.ok else f"[red]Ошибка: {r2.status_code} {r2.text}")
            wait_key()
        elif ch == "0":
            break


def menu_admin():
    while True:
        clear_screen()
        print_header()
        console.print("[bold magenta]Админ[/bold magenta]\n")
        console.print("1. Показать IP диапазоны")
        console.print("2. Добавить IP диапазон")
        console.print("3. Удалить IP диапазон")
        console.print("0. Назад\n")
        ch = input("Выберите действие: ").strip()
        if ch == "1":
            r = requests.get(f"{API_BASE}/admin/ip_ranges")
            data = r.json() if r.ok else []
            if not data:
                console.print("[yellow]Список пуст[/yellow]")
            else:
                for row in data:
                    console.print(f"- {row['id']}: {row['prefix']}")
            wait_key()
        elif ch == "2":
            prefix = input("Префикс (например 192.168.1.): ").strip()
            r = requests.post(f"{API_BASE}/admin/ip_ranges", json={"prefix": prefix})
            console.print(r.json() if r.ok else f"[red]Ошибка: {r.status_code} {r.text}")
            wait_key()
        elif ch == "3":
            ip_id = input("ID для удаления: ").strip()
            r = requests.delete(f"{API_BASE}/admin/ip_ranges/{ip_id}")
            console.print("Удалено" if r.status_code == 204 else f"[red]Ошибка: {r.status_code} {r.text}")
            wait_key()
        elif ch == "0":
            break


def main():
    while True:
        clear_screen()
        print_header()
        console.print("\n[bold cyan]1.[/bold cyan] Аккаунты")
        console.print("[bold cyan]2.[/bold cyan] Настройки")
        console.print("[bold cyan]3.[/bold cyan] Папки")
        console.print("[bold cyan]4.[/bold cyan] Админ")
        console.print("[bold cyan]0.[/bold cyan] Выход\n")
        ch = input("Выберите действие: ").strip()
        if ch == "1":
            menu_accounts()
        elif ch == "2":
            menu_config()
        elif ch == "3":
            menu_folders()
        elif ch == "4":
            menu_admin()
        elif ch == "0":
            break


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)

