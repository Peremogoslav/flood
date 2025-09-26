import asyncio
import os
import sys
from datetime import datetime
import pwinput
import requests
from rich.console import Console
from rich.panel import Panel
from rich import box


API_BASE = os.getenv("API_BASE", "http://localhost:8000")
LOG_FILE = os.getenv("CLI_LOG_FILE", "log.file")
session = requests.Session()
ACCESS_TOKEN = None
ACCESS_PASSWORD = None
IS_ADMIN = False
console = Console()


def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


def print_header():
    console.print(Panel.fit("[bold cyan]TELEGRAM MANAGER CLI (API)[/bold cyan]", box=box.DOUBLE, padding=(1, 2)))


def wait_key():
    input("\nНажмите Enter для продолжения...")


def log_line(message: str):
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{ts} | {message}\n")
    except Exception:
        pass


def fetch_accounts():
    r = api_get("/accounts/")
    if not r.ok:
        console.print(f"[red]Ошибка: {r.status_code} {r.text}")
        log_line(f"accounts_fetch_failed status={r.status_code}")
        return []
    data = r.json() or []
    return data


def show_accounts_enumerated(accs: list[dict]):
    if not accs:
        console.print("[yellow]Нет аккаунтов[/yellow]")
        return
    for idx, a in enumerate(accs, 1):
        console.print(f"- {idx}: {a['phone']}")


def prompt_account_indices(max_n: int) -> list[int]:
    raw = input("Введите номера через запятую: ").strip()
    try:
        nums = [int(x.strip()) for x in raw.split(",") if x.strip()]
    except ValueError:
        console.print("[red]Неверный формат[/red]")
        return []
    valid = []
    for n in nums:
        if 1 <= n <= max_n:
            valid.append(n)
    if not valid:
        console.print("[yellow]Ничего не выбрано[/yellow]")
    return valid


def prompt_yes_no(message: str, default: bool | None = True) -> bool:
    suffix = "[Y/n]" if default is True else ("[y/N]" if default is False else "[y/n]")
    while True:
        ans = input(f"{message} {suffix}: ").strip().lower()
        if ans == "" and default is not None:
            return default
        if ans in ("y", "yes", "да", "д", "1", "true"):
            return True
        if ans in ("n", "no", "нет", "н", "0", "false"):
            return False
        console.print("[yellow]Пожалуйста, введите y/н или n/нет[/yellow]")


def prompt_phone() -> str | None:
    while True:
        phone = input("Введите номер телефона (+79161234567) или 0 для возврата: ").strip()
        if phone == "0":
            return None
        if phone.startswith("+") and phone[1:].replace(" ", "").isdigit() and 11 <= len(phone.replace(" ", "")) <= 16:
            return phone
        console.print("[red]Неверный формат номера. Пример: +79001234567[/red]")


def auth_headers():
    global ACCESS_TOKEN
    return {"Authorization": f"Bearer {ACCESS_TOKEN}"} if ACCESS_TOKEN else {}


def extra_headers():
    return {"X-Access-Password": ACCESS_PASSWORD} if ACCESS_PASSWORD else {}


def merged_headers(h: dict | None = None) -> dict:
    base = {}
    base.update(auth_headers())
    base.update(extra_headers())
    if h:
        base.update(h)
    return base


def _maybe_prompt_access_password(resp: requests.Response) -> bool:
    global ACCESS_PASSWORD
    if resp is not None and resp.status_code == 403:
        try:
            data = resp.json()
            if isinstance(data, dict) and "Access denied" in str(data.get("detail", "")):
                pwd = pwinput.pwinput(prompt="Пароль доступа: ", mask="*")
                if pwd:
                    ACCESS_PASSWORD = pwd
                    return True
        except Exception:
            pass
    return False


def api_get(path: str, **kwargs):
    url = f"{API_BASE}{path}"
    kwargs["headers"] = merged_headers(kwargs.get("headers"))
    resp = session.get(url, **kwargs)
    if _maybe_prompt_access_password(resp):
        kwargs["headers"] = merged_headers(kwargs.get("headers"))
        resp = session.get(url, **kwargs)
    return resp


def api_post(path: str, **kwargs):
    url = f"{API_BASE}{path}"
    kwargs["headers"] = merged_headers(kwargs.get("headers"))
    resp = session.post(url, **kwargs)
    if _maybe_prompt_access_password(resp):
        kwargs["headers"] = merged_headers(kwargs.get("headers"))
        resp = session.post(url, **kwargs)
    return resp


def api_put(path: str, **kwargs):
    url = f"{API_BASE}{path}"
    kwargs["headers"] = merged_headers(kwargs.get("headers"))
    resp = session.put(url, **kwargs)
    if _maybe_prompt_access_password(resp):
        kwargs["headers"] = merged_headers(kwargs.get("headers"))
        resp = session.put(url, **kwargs)
    return resp


def api_delete(path: str, **kwargs):
    url = f"{API_BASE}{path}"
    kwargs["headers"] = merged_headers(kwargs.get("headers"))
    resp = session.delete(url, **kwargs)
    if _maybe_prompt_access_password(resp):
        kwargs["headers"] = merged_headers(kwargs.get("headers"))
        resp = session.delete(url, **kwargs)
    return resp


def menu_auth():
    global ACCESS_TOKEN, IS_ADMIN
    while True:
        clear_screen()
        print_header()
        console.print("[bold magenta]Авторизация[/bold magenta]\n")
        console.print("1. Регистрация (username + пароль)")
        console.print("2. Вход (username + пароль)")
        console.print("0. Назад\n")
        ch = input("Выберите действие: ").strip()
        if ch == "1":
            username = input("Username: ").strip()
            password = pwinput.pwinput(prompt="Пароль: ", mask="*")
            r = api_post("/users/register", json={"username": username, "password": password})
            if r.ok:
                data = r.json()
                ACCESS_TOKEN = data.get("access_token")
                try:
                    IS_ADMIN = bool(data.get("is_admin", False))
                except Exception:
                    IS_ADMIN = False
                console.print("[green]Регистрация успешна. Токен получен.[/green]")
                log_line(f"register_success username={username}")
                return
            else:
                if r.status_code == 409:
                    console.print("[red]Пользователь уже существует[/red]")
                    log_line(f"register_conflict username={username}")
                elif r.status_code == 422:
                    console.print("[red]Некорректные данные: username ≥ 3 символов, пароль ≥ 6 символов[/red]")
                    log_line(f"register_invalid username={username}")
                else:
                    console.print("[red]Ошибка регистрации[/red]")
                    log_line(f"register_error username={username} status={r.status_code}")
                wait_key()
                continue
        elif ch == "2":
            username = input("Username: ").strip()
            password = pwinput.pwinput(prompt="Пароль: ", mask="*")
            r = api_post("/users/login", json={"username": username, "password": password})
            if r.ok:
                data = r.json()
                ACCESS_TOKEN = data.get("access_token")
                try:
                    IS_ADMIN = bool(data.get("is_admin", False))
                except Exception:
                    IS_ADMIN = False
                console.print("[green]Вход выполнен. Токен обновлён.[/green]")
                log_line(f"login_success username={username}")
                return
            else:
                console.print("[red]Неверные учетные данные[/red]")
                log_line(f"login_invalid username={username}")
                wait_key()
                continue
        elif ch == "0":
            break


def add_account_flow():
    phone = prompt_phone()
    if not phone:
        return
    r = api_post("/auth/start", json={"phone": phone})
    if not r.ok:
        console.print(f"[red]Ошибка: {r.status_code} {r.text}")
        log_line(f"add_account_start_failed phone={phone} status={r.status_code}")
        wait_key()
        return
    code = input("Введите код из Telegram (или 0 для отмены): ").strip()
    if code == "0":
        return
    pwd = pwinput.pwinput(prompt="Введите пароль 2FA (если включён, иначе Enter): ", mask="*")
    payload = {"phone": phone, "code": code or None, "password": (pwd or None)}
    r2 = api_post("/auth/verify", json=payload)
    console.print(r2.json() if r2.ok else f"[red]Ошибка: {r2.status_code} {r2.text}")
    if r2.ok:
        log_line(f"add_account_success phone={phone}")
    else:
        log_line(f"add_account_failed phone={phone} status={r2.status_code}")
    wait_key()


def delete_account_flow():
    r = api_get("/accounts/")
    data = r.json() if r.ok else []
    if not data:
        console.print("[yellow]Нет аккаунтов для удаления[/yellow]")
        wait_key()
        return
    console.print("Ваши аккаунты:")
    for a in data:
        console.print(f"- {a['id']}: {a['phone']}")
    ids = input("Введите ID для удаления (через запятую, или 0 для отмены): ").strip()
    if ids.strip() == "0":
        return
    try:
        targets = [int(x.strip()) for x in ids.split(",") if x.strip()]
    except ValueError:
        console.print("[red]Неверный формат ID[/red]")
        wait_key()
        return
    if not targets:
        console.print("[yellow]Ничего не выбрано[/yellow]")
        wait_key()
        return
    if not prompt_yes_no("Подтвердите удаление выбранных аккаунтов", default=False):
        console.print("Отменено")
        wait_key()
        return
    for tid in targets:
        resp = session.delete(f"{API_BASE}/accounts/{tid}", headers=auth_headers())
        if resp.status_code == 204:
            console.print(f"Удалено: {tid}")
        else:
            console.print(f"[red]Ошибка при удалении {tid}: {resp.status_code} {resp.text}")
    wait_key()


def add_folder_to_accounts_flow():
    accs = fetch_accounts()
    if not accs:
        console.print("[yellow]Нет аккаунтов[/yellow]")
        wait_key()
        return
    console.print("Доступные аккаунты:")
    show_accounts_enumerated(accs)
    idxs = prompt_account_indices(len(accs))
    if not idxs:
        wait_key()
        return
    id_list = [accs[i - 1]["id"] for i in idxs]
    link = input("Ссылка addlist: ").strip()
    r2 = api_post("/folders/addlist", json={"phone_ids": id_list, "link": link})
    console.print(r2.json() if r2.ok else f"[red]Ошибка: {r2.status_code} {r2.text}")
    wait_key()


def choose_accounts_and_folder():
    accs = fetch_accounts()
    if not accs:
        console.print("[yellow]Нет аккаунтов. Сначала добавьте аккаунт в пункте 1 главного меню.[/yellow]")
        wait_key()
        return [], None
    console.print("Ваши аккаунты:")
    show_accounts_enumerated(accs)
    idxs = prompt_account_indices(len(accs))
    if not idxs:
        wait_key()
        return [], None
    selected_ids = [accs[i - 1]["id"] for i in idxs]
    params = "&".join([f"account_ids={i}" for i in selected_ids])
    r2 = api_get(f"/folders/by_accounts?{params}")
    if not r2.ok:
        console.print(f"[red]Ошибка: {r2.status_code} {r2.text}")
        wait_key()
        return [], None
    data = r2.json()  # {accId: {folderName: [titles]}}
    folder_names = set()
    for _, fmap in data.items():
        folder_names.update(list(fmap.keys()))
    if not folder_names:
        console.print("[yellow]У выбранных аккаунтов нет папок[/yellow]")
        wait_key()
        return [], None
    folder_list = sorted(folder_names)
    console.print("Доступные папки:")
    for i, name in enumerate(folder_list, 1):
        console.print(f"{i}. {name}")
    ch = input("Выберите папку по номеру (или 0 для отмены): ").strip()
    if not ch.isdigit() or not (1 <= int(ch) <= len(folder_list)):
        if ch == "0":
            return [], None
        console.print("[red]Неверный выбор папки[/red]")
        wait_key()
        return [], None
    return selected_ids, folder_list[int(ch) - 1]


def start_spam_flow():
    acc_ids, folder_name = choose_accounts_and_folder()
    if not acc_ids or not folder_name:
        return
    msgs = []
    try:
        if os.path.exists("messages.txt"):
            with open("messages.txt", "r", encoding="utf-8") as f:
                content = f.read().strip()
                msgs = [m.strip() for m in content.split("|") if m.strip()]
        else:
            messages = input("Сообщения через | : ").strip()
            msgs = [m.strip() for m in messages.split("|") if m.strip()]
    except Exception as e:
        console.print(f"[red]Ошибка чтения messages.txt: {e}[/red]")
        wait_key()
        return
    if not msgs:
        console.print("[red]Нет сообщений для отправки[/red]")
        wait_key()
        return
    # read config from API; if available, don't prompt
    min_delay = 5
    max_delay = 10
    randomize = True
    try:
        rc = api_get("/config/")
        if rc.ok:
            cfg = rc.json()
            min_delay = int(cfg.get("min_delay", min_delay))
            max_delay = int(cfg.get("max_delay", max_delay))
            randomize = bool(cfg.get("randomize_chats", randomize))
    except Exception:
        pass
    payload = {"account_ids": acc_ids, "folder_name": folder_name, "messages": msgs, "min_delay": min_delay, "max_delay": max_delay, "randomize_chats": randomize}
    r = api_post("/spam/start", json=payload)
    if r.ok:
        data = r.json()
        job_id = data.get("job_id")
        console.print(f"[green]Запущено[/green]. job_id: {job_id}")
        # live log tail
        since = 0
        while True:
            s = api_get(f"/spam/logs/{job_id}", params={"since": since})
            if not s.ok:
                console.print(f"[red]Ошибка статуса: {s.status_code} {s.text}")
                break
            body = s.json()
            for entry in body.get("logs", []):
                level = entry.get("level")
                peer = entry.get("peer", "?")
                account = entry.get("account", "?")
                if level == "sent":
                    console.print(f"[green][SENT][/green] {account} → {peer}")
                elif level == "skip":
                    console.print(f"[yellow][SKIP][/yellow] {account} → {peer}: {entry.get('detail','')}")
                else:
                    console.print(f"[blue]{entry.get('msg','')}")
            since = body.get("next", since)
            status = body.get("status")
            if status in ("completed", "error"):
                console.print(f"[bold]Статус: {status}[/bold]")
                break
            # exit live tail if user wants
            try:
                import time
                time.sleep(1)
            except KeyboardInterrupt:
                break
    else:
        console.print(f"[red]Ошибка: {r.status_code} {r.text}")
    wait_key()
def menu_accounts():
    while True:
        clear_screen()
        print_header()
        console.print("[bold magenta]Аккаунты[/bold magenta]\n")
        console.print("1. Показать аккаунты")
        console.print("2. Добавить аккаунт (номер → код → 2FA)")
        console.print("3. Удалить аккаунт")
        console.print("0. Назад\n")
        ch = input("Выберите действие: ").strip()
        if ch == "1":
            r = api_get("/accounts/")
            if r.ok:
                data = r.json()
                if not data:
                    console.print("[yellow]Нет аккаунтов[/yellow]")
                else:
                    for a in data:
                        console.print(f"- {a['id']}: {a['phone']}")
                log_line("accounts_list")
            else:
                console.print(f"[red]Ошибка: {r.status_code} {r.text}")
                log_line(f"accounts_list_failed status={r.status_code}")
            wait_key()
        elif ch == "2":
            phone = input("Телефон (+7...): ").strip()
            r = session.post(f"{API_BASE}/auth/start", json={"phone": phone}, headers=auth_headers())
            if not r.ok:
                console.print(f"[red]Ошибка: {r.status_code} {r.text}")
                wait_key()
                continue
            code = input("Код из Telegram: ").strip()
            password = pwinput.pwinput(prompt="Пароль 2FA (если запрашивается, иначе Enter): ", mask="*")
            payload = {"phone": phone, "code": code or None, "password": password or None}
            r2 = session.post(f"{API_BASE}/auth/verify", json=payload, headers=auth_headers())
            console.print(r2.json() if r2.ok else f"[red]Ошибка: {r2.status_code} {r2.text}")
            wait_key()
        elif ch == "3":
            acc_id = input("ID аккаунта для удаления: ").strip()
            r = session.delete(f"{API_BASE}/accounts/{acc_id}", headers=auth_headers())
            console.print("Удалено" if r.status_code == 204 else f"[red]Ошибка: {r.status_code} {r.text}")
            wait_key()
        elif ch == "0":
            break


def menu_config():
    while True:
        clear_screen()
        print_header()
        console.print("[bold magenta]Настройки[/bold magenta]\n")
        r = session.get(f"{API_BASE}/config/", headers=auth_headers())
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
            r2 = session.put(f"{API_BASE}/config/", json=payload, headers=auth_headers())
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
        console.print("2. Показать папки выбранных аккаунтов")
        console.print("3. Начать рассылку по папке")
        console.print("0. Назад\n")
        ch = input("Выберите действие: ").strip()
        if ch == "1":
            r = session.get(f"{API_BASE}/accounts/", headers=auth_headers())
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
            r2 = api_post("/folders/addlist", json={"phone_ids": id_list, "link": link})
            console.print(r2.json() if r2.ok else f"[red]Ошибка: {r2.status_code} {r2.text}")
            wait_key()
        elif ch == "2":
            r = api_get("/accounts/")
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
            params = "&".join([f"account_ids={i}" for i in id_list])
            r2 = api_get(f"/folders/by_accounts?{params}")
            console.print(r2.json() if r2.ok else f"[red]Ошибка: {r2.status_code} {r2.text}")
            wait_key()
        elif ch == "3":
            r = api_get("/accounts/")
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
            folder_name = input("Название папки: ").strip()
            messages = input("Сообщения через | : ").strip()
            msgs = [m.strip() for m in messages.split("|") if m.strip()]
            try:
                min_delay = int(input("min_delay: ").strip() or "5")
                max_delay = int(input("max_delay: ").strip() or "10")
            except ValueError:
                console.print("[red]Неверные задержки[/red]")
                wait_key()
                continue
            randomize = input("Перемешивать чаты? (y/n): ").strip().lower() in ("y", "да", "1", "true")
            payload = {"account_ids": id_list, "folder_name": folder_name, "messages": msgs, "min_delay": min_delay, "max_delay": max_delay, "randomize_chats": randomize}
            r2 = api_post("/spam/start", json=payload)
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
            r = session.get(f"{API_BASE}/admin/ip_ranges", headers=auth_headers())
            data = r.json() if r.ok else []
            if not data:
                console.print("[yellow]Список пуст[/yellow]")
            else:
                for row in data:
                    console.print(f"- {row['id']}: {row['prefix']}")
            wait_key()
        elif ch == "2":
            prefix = input("Префикс (например 192.168.1.): ").strip()
            r = session.post(f"{API_BASE}/admin/ip_ranges", json={"prefix": prefix}, headers=auth_headers())
            console.print(r.json() if r.ok else f"[red]Ошибка: {r.status_code} {r.text}")
            wait_key()
        elif ch == "3":
            ip_id = input("ID для удаления: ").strip()
            r = session.delete(f"{API_BASE}/admin/ip_ranges/{ip_id}", headers=auth_headers())
            console.print("Удалено" if r.status_code == 204 else f"[red]Ошибка: {r.status_code} {r.text}")
            wait_key()
        elif ch == "0":
            break


def main():
    # one-time access check at startup
    # try a cheap call to /health with access password prompt
    try:
        resp = api_get("/health")
        if resp.status_code == 403 and not ACCESS_PASSWORD:
            # prompt handled inside api_get, but if still forbidden, stop
            console.print("[red]Доступ запрещён. Обратитесь к администратору для добавления IP либо пароля доступа[/red]")
            return
    except Exception:
        pass
    while True:
        clear_screen()
        print_header()
        if not ACCESS_TOKEN:
            console.print("\n[bold cyan]1.[/bold cyan] Авторизация (регистрация/вход)")
            console.print("[bold cyan]0.[/bold cyan] Выход\n")
            ch = input("Выберите действие: ").strip()
            if ch == "1":
                menu_auth()
            elif ch == "0":
                break
            continue
        console.print("\n[bold cyan]1.[/bold cyan] Добавить аккаунт Telegram")
        console.print("[bold cyan]2.[/bold cyan] Начать рассылку по папкам")
        console.print("[bold cyan]3.[/bold cyan] Удалить аккаунт/сессию")
        console.print("[bold cyan]4.[/bold cyan] Настройки спама")
        console.print("[bold cyan]5.[/bold cyan] Добавить папку с чатами")
        if IS_ADMIN:
            console.print("[bold cyan]6.[/bold cyan] Админ-панель")
        console.print("[bold cyan]0.[/bold cyan] Выйти\n")
        ch = input("Выберите действие: ").strip()
        if ch == "1":
            add_account_flow()
        elif ch == "2":
            start_spam_flow()
        elif ch == "3":
            delete_account_flow()
        elif ch == "4":
            menu_config()
        elif ch == "5":
            add_folder_to_accounts_flow()
        elif ch == "6":
            if IS_ADMIN:
                menu_admin()
            else:
                console.print("[red]Доступно только администратору[/red]")
                wait_key()
        elif ch == "0":
            break


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)

