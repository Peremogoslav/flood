# main.py
import asyncio
import os
import time
from rich.console import Console
from rich.panel import Panel
from rich import box
from rich.table import Table

from db import init_db, get_conn, close_conn
from ui import clear_screen, print_header
from utils import check_access
from telegram_client import add_folder_by_link_to_accounts, try_authorize_new_account
from spam import spam_by_folder_interactive, choose_accounts_interactive
from config import load_config, save_config
from constants import SESSIONS_DIR, ADMIN_PASSWORD
from rich.console import Console
import pwinput

console = Console()

os.makedirs(SESSIONS_DIR, exist_ok=True)
init_db()

def list_accounts():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT phone, session_file FROM sessions")
    return [(r["phone"], r["session_file"]) for r in cursor.fetchall()]

async def add_account_interactive():
    while True:
        phone = input("Введите номер телефона (+79161234567) или 0 для возврата: ").strip()
        if phone == "0":
            console.print("[yellow][INFO][/yellow] Возврат в главное меню...")
            return

        if not phone or not phone.startswith("+") or not phone[1:].isdigit() or not (11 <= len(phone) <= 16):
            console.print("[red][FAILED][/red] Неверный формат номера!")
            continue
        session_file = f"{SESSIONS_DIR}/{phone}.session"

        # Проверим есть ли уже
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM sessions WHERE phone = ?", (phone,))
        if cursor.fetchone():
            console.print(f"[yellow][INFO][/yellow] Аккаунт {phone} уже был добавлен ранее.")
            time.sleep(2)
            return

        # Попытка авторизации (отправка кода/ввод кода)
        from telegram_client import TelegramClient  # lazy import for Telethon object (if needed)
        # Используем функцию-обертку для авторизации
        try:
            ok = await try_authorize_new_account(session_file, phone, console)
            if not ok:
                return
        except Exception as e:
            console.print(f"[red][FAILED][/red] Ошибка при авторизации: {e}")
            return

        # Сохраняем в БД
        try:
            cursor.execute("INSERT INTO sessions (phone, session_file) VALUES (?, ?)", (phone, session_file))
            conn.commit()
            console.print(f"[green][SUCCESS][/green] Аккаунт {phone} добавлен!\n")
            time.sleep(1)
        except Exception as e:
            console.print(f"[red][FAILED][/red] Ошибка базы данных: {e}")
            if os.path.exists(session_file):
                try:
                    os.remove(session_file)
                except Exception:
                    pass
        return

async def delete_accounts_interactive():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT phone, session_file FROM sessions")
    accounts = cursor.fetchall()
    if not accounts:
        console.print("[red][FAILED][/red] Нет аккаунтов для удаления!")
        input("\nНажмите Enter для возврата в меню...")
        return

    while True:
        console.print("\n[bold green]Ваши аккаунты:[/bold green]")
        for i, r in enumerate(accounts, 1):
            console.print(f"[cyan]{i}[/cyan]. {r['phone']}")
        console.print("[cyan]0[/cyan]. Назад в меню")

        choice_input = input("Выберите аккаунт(ы) для удаления через запятую (например 1,2) или 0 для выхода: ").strip()
        if choice_input == "0":
            return

        choices = []
        for x in choice_input.split(","):
            x = x.strip()
            if x.isdigit():
                idx = int(x) - 1
                if 0 <= idx < len(accounts):
                    choices.append(idx)

        if not choices:
            console.print("[red][FAILED][/red] Неверный выбор!")
            continue

        for idx in choices:
            phone, session_file = accounts[idx]["phone"], accounts[idx]["session_file"]
            try:
                cursor.execute("DELETE FROM sessions WHERE phone=?", (phone,))
                conn.commit()
                if os.path.exists(session_file):
                    os.remove(session_file)
                console.print(f"[green][SUCCESS][/green] Сессия {phone} удалена")
            except Exception as e:
                console.print(f"[yellow][WARNING][/yellow] Не удалось удалить сессию {phone}: {e}")

        cursor.execute("SELECT phone, session_file FROM sessions")
        accounts = cursor.fetchall()
        if not accounts:
            console.print("[green][INFO][/green] Все аккаунты удалены!")
            input("\nНажмите Enter для возврата в меню...")
            return

async def add_folder_flow():
    accounts = list_accounts()
    if not accounts:
        console.print("[red][FAILED][/red] Нет добавленных аккаунтов!")
        input("\nНажмите Enter для возврата в меню...")
        return
    # Выбор аккаунтов
    selected = await choose_accounts_interactive(accounts)
    if not selected:
        console.print("[yellow][INFO][/yellow] Возврат в главное меню без выбора аккаунтов")
        await asyncio.sleep(1)
        return
    link = input("Введите ссылку на папку (addlist) или 0 для отмены: ").strip()
    if link == "0":
        console.print("[yellow][INFO][/yellow] Отмена.")
        await asyncio.sleep(1)
        return
    await add_folder_by_link_to_accounts(selected, link)
    console.print("[green][SUCCESS][/green] Операция завершена!")
    input("\nНажмите Enter для возврата в меню...")

async def admin_panel():
    from db import get_conn
    conn = get_conn()
    cursor = conn.cursor()
    entered_password = pwinput.pwinput(prompt="Введите пароль администратора: ", mask="*")
    if entered_password != ADMIN_PASSWORD:
        console.print("[red][FAILED][/red] Неверный пароль!")
        await asyncio.sleep(2)
        return
    while True:
        clear_screen()
        print_header()
        console.print(Panel.fit("[bold yellow]АДМИН-ПАНЕЛЬ[/bold yellow]", box=box.DOUBLE, padding=(1, 2)))
        console.print("\n[bold cyan]1.[/bold cyan] Показать разрешенные IP диапазоны")
        console.print("[bold cyan]2.[/bold cyan] Добавить IP диапазон")
        console.print("[bold cyan]3.[/bold cyan] Удалить IP диапазон")
        console.print("[bold cyan]4.[/bold cyan] SQL-консоль")
        console.print("[bold cyan]0.[/bold cyan] Назад в главное меню\n")
        choice = input("Выберите действие: ").strip()
        if choice == '1':
            cursor.execute("SELECT id, prefix FROM ip_ranges ORDER BY id")
            ranges = cursor.fetchall()
            if not ranges:
                console.print("[yellow][INFO][/yellow] Список IP диапазонов пуст.")
            else:
                console.print("\n[bold green]Разрешенные IP диапазоны:[/bold green]")
                for r in ranges:
                    console.print(f"[cyan]{r['id']}[/cyan]. {r['prefix']}")
            input("\nНажмите Enter для продолжения...")
        elif choice == '2':
            prefix_to_add = input("Введите новый IP префикс (например, 192.168.1.): ").strip()
            if not prefix_to_add:
                console.print("[red][FAILED][/red] Префикс не может быть пустым.")
            else:
                try:
                    cursor.execute("INSERT INTO ip_ranges (prefix) VALUES (?)", (prefix_to_add,))
                    conn.commit()
                    console.print(f"[green][SUCCESS][/green] Префикс '{prefix_to_add}' успешно добавлен.")
                except Exception as e:
                    console.print(f"[red][FAILED][/red] Произошла ошибка: {e}")
            await asyncio.sleep(2)
        elif choice == '3':
            cursor.execute("SELECT id, prefix FROM ip_ranges ORDER BY id")
            ranges = cursor.fetchall()
            if not ranges:
                console.print("[yellow][INFO][/yellow] Нет диапазонов для удаления.")
                await asyncio.sleep(2)
                continue
            console.print("\n[bold green]Выберите ID диапазона для удаления:[/bold green]")
            for r in ranges:
                console.print(f"[cyan]{r['id']}[/cyan]. {r['prefix']}")
            id_to_delete = input("Введите ID для удаления (или 0 для отмены): ").strip()
            if id_to_delete.isdigit():
                id_val = int(id_to_delete)
                if id_val == 0:
                    continue
                cursor.execute("DELETE FROM ip_ranges WHERE id = ?", (id_val,))
                if cursor.rowcount > 0:
                    conn.commit()
                    console.print(f"[green][SUCCESS][/green] Диапазон с ID {id_val} удален.")
                else:
                    console.print(f"[red][FAILED][/red] Диапазон с ID {id_val} не найден.")
            else:
                console.print("[red][FAILED][/red] Некорректный ID.")
            await asyncio.sleep(2)
        elif choice == "4":
            # простая SQL-консоль
            while True:
                query = input("SQL> ").strip()
                if query.lower() in ("exit", "quit"):
                    break
                if not query:
                    continue
                try:
                    cursor.execute(query)
                    conn.commit()
                    if query.lower().startswith("select"):
                        rows = cursor.fetchall()
                        if rows:
                            table = Table(title="Результаты запроса")
                            for idx, col in enumerate([d[0] for d in cursor.description]):
                                table.add_column(col, justify="center")
                            for row in rows:
                                table.add_row(*[str(x) for x in row])
                            console.print(table)
                        else:
                            console.print("[yellow][INFO][/yellow] Результаты пусты.")
                    else:
                        console.print(f"[green][SUCCESS][/green] Запрос выполнен успешно!")
                except Exception as e:
                    console.print(f"[red][FAILED][/red] Ошибка выполнения запроса: {e}")
        elif choice == '0':
            break
        else:
            console.print("[red][FAILED][/red] Неверный выбор!")
            await asyncio.sleep(1)

async def main():
    clear_screen()
    if not check_access():
        input("\nНажмите Enter для выхода...")
        return

    while True:
        clear_screen()
        print_header()
        console.print("\n[bold cyan]1.[/bold cyan] Добавить аккаунт Telegram")
        console.print("[bold cyan]2.[/bold cyan] Начать рассылку по папкам")
        console.print("[bold cyan]3.[/bold cyan] Удалить аккаунт/сессию")
        console.print("[bold cyan]4.[/bold cyan] Настройки спама")
        console.print("[bold cyan]5.[/bold cyan] Добавить папку с чатами")
        console.print("[bold cyan]6.[/bold cyan] Админ-панель")
        console.print("[bold cyan]0.[/bold cyan] Выйти\n")
        console.print("=" * 30)
        choice = input("Выберите действие: ").strip()
        if choice == "1":
            await add_account_interactive()
        elif choice == "2":
            await spam_by_folder_interactive()
        elif choice == "3":
            await delete_accounts_interactive()
        elif choice == "4":
            # настройки спама (упрощённые)
            cfg = load_config()
            while True:
                clear_screen()
                print_header()
                console.print("[bold magenta]Настройки спама[/bold magenta]\n")
                console.print(f"1. Мин. задержка между чатами: [cyan]{cfg['min_delay']}[/cyan] сек")
                console.print(f"2. Макс. задержка между чатами: [cyan]{cfg['max_delay']}[/cyan] сек")
                console.print(f"3. Рандомный порядок чатов: [cyan]{'Да' if cfg['randomize_chats'] else 'Нет'}[/cyan]")
                console.print(f"4. Использовать фото: [cyan]{'Да' if cfg.get('use_images', False) else 'Нет'}[/cyan]")
                console.print("\n0. Назад в меню")
                ch = input("\nВыберите пункт: ").strip()
                if ch == "1":
                    while True:
                        val = input(f"Введите новое минимальное значение (сек, число >=1 и <= {cfg['max_delay']}): ").strip()
                        if val.isdigit() and 1 <= int(val) <= cfg['max_delay']:
                            cfg["min_delay"] = int(val)
                            break
                        console.print(f"[red][FAILED][/red] Введите число от 1 до {cfg['max_delay']}!")
                elif ch == "2":
                    while True:
                        val = input(f"Введите новое максимальное значение (сек, число >= {cfg['min_delay']}): ").strip()
                        if val.isdigit() and int(val) >= cfg['min_delay']:
                            cfg["max_delay"] = int(val)
                            break
                        console.print(f"[red][FAILED][/red] Введите число >= {cfg['min_delay']}!")
                elif ch == "3":
                    cfg["randomize_chats"] = not cfg["randomize_chats"]
                elif ch == "4":
                    cfg["use_images"] = not cfg.get("use_images", False)
                elif ch == "0":
                    break
                else:
                    console.print("[red][FAILED][/red] Неверный выбор!")
                save_config(cfg)
                console.print("[green][SUCCESS][/green] Настройки сохранены.")
                await asyncio.sleep(1)
        elif choice == "5":
            await add_folder_flow()
        elif choice == "6":
            await admin_panel()
        elif choice == "0":
            break
        else:
            console.print("[red][FAILED][/red] Неверный выбор!")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        close_conn()
