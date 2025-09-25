# spam.py
import os
import random
import asyncio
from telethon.errors import (
    FloodWaitError,
    ChatWriteForbiddenError,
    UserPrivacyRestrictedError,
    PeerIdInvalidError,
    ChannelPrivateError,
    ChatAdminRequiredError,
    MessageTooLongError,
    MessageIdInvalidError,
    RPCError,
    SlowModeWaitError
)
from rich.console import Console
from rich.panel import Panel
from rich import box
from rich.table import Table

from config import load_config, save_config
from db import get_conn
from telegram_client import init_client, add_folder_by_link_to_accounts
from ui import print_manual
from constants import SKIP_FOLDER_NAME

console = Console()

async def choose_accounts_interactive(accounts):
    console.print("\n[bold green]Ваши аккаунты:[/bold green]")
    for i, (phone, _) in enumerate(accounts, 1):
        console.print(f"[cyan]{i}[/cyan]. {phone}")
    console.print("[cyan]0[/cyan]. Назад")

    while True:
        choice_input = input("Выберите аккаунт(ы) через запятую (например 1,2) или 0 для отмены: ").strip()
        if choice_input == "0":
            return []
        choices = []
        for x in choice_input.split(","):
            x = x.strip()
            if x.isdigit():
                idx = int(x) - 1
                if 0 <= idx < len(accounts):
                    choices.append(idx)
        if choices:
            return [accounts[i] for i in choices]
        console.print("[red][FAILED][/red] Неверный выбор!")

async def choose_folder(folder_maps):
    all_folders = sorted({fname for fmap in folder_maps for fname in fmap.keys()})
    if not all_folders:
        console.print("[red][FAILED][/red] У выбранных аккаунтов нет папок!")
        return None
    console.print("\n[bold green]Доступные папки:[/bold green]")
    for i, name in enumerate(all_folders, 1):
        console.print(f"[cyan]{i}[/cyan]. {name}")
    while True:
        choice = input("Выберите папку по номеру: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(all_folders):
            return all_folders[int(choice) - 1]
        console.print("[red][FAILED][/red] Неверный выбор!")

async def spam_by_folder_interactive():
    print_manual()
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT phone, session_file FROM sessions")
    accounts = cursor.fetchall()
    if not accounts:
        console.print("[red][FAILED][/red] Нет добавленных аккаунтов!")
        input("\nНажмите Enter для возврата в меню...")
        return

    selected_accounts = await choose_accounts_interactive([(r["phone"], r["session_file"]) for r in accounts])
    if not selected_accounts:
        return

    tasks = [init_client(sfile) for _, sfile in selected_accounts]
    results = await asyncio.gather(*tasks)
    filtered = [(c, f) for c, f in results if c]
    if not filtered:
        console.print("[red][FAILED][/red] Не удалось инициализировать ни одного клиента.")
        return

    clients, folder_maps = zip(*filtered)
    folder_name = await choose_folder(folder_maps)
    if not folder_name:
        for c in clients:
            if c and c.is_connected():
                await c.disconnect()
        return

    while True:
        try:
            num_msgs = await asyncio.to_thread(lambda: int(input("Сколько кругов рассылки сделать: ").strip()))
            if num_msgs > 0:
                break
            console.print("[red][FAILED][/red] Число должно быть больше 0!")
        except ValueError:
            console.print("[red][FAILED][/red] Введите корректное число!")

    if os.path.exists("messages.txt"):
        with open("messages.txt", "r", encoding="utf-8") as f:
            content = f.read().strip()
            messages = [m.strip() for m in content.split("|") if m.strip()]
    else:
        msgs_input = input("Введите сообщения через | : ").strip()
        messages = [m.strip() for m in msgs_input.split("|") if m.strip()]

    if not messages:
        console.print("[red][FAILED][/red] Нет сообщений для отправки!")
        return

    cfg = load_config()

    async def spam_with_client(client, phone, fmap):
        peers = fmap.get(folder_name, [])
        if cfg["randomize_chats"]:
            random.shuffle(peers)

        console.print(f"\n[blue][INFO][/blue] Запуск рассылки с {phone} ({len(peers)} чатов)")

        for _ in range(num_msgs):
            for peer in peers:
                peer_title = getattr(peer, 'title', getattr(peer, 'username', f"ID {peer.id}"))
                msg = random.choice(messages)
                try:
                    if cfg.get("use_images", False) and os.path.exists("media"):
                        media_files = [
                            os.path.join("media", f)
                            for f in os.listdir("media")
                            if f.lower().endswith((".jpg", ".jpeg", ".png", ".mp4", ".mov", ".mkv"))
                        ]
                        if media_files:
                            media = random.choice(media_files)
                            try:
                                await client.send_file(peer, media, caption=msg)
                                console.print(f"[green][SENT][/green] {phone}: сообщение с медиа в '{peer_title}'")
                            except RPCError:
                                await client.send_message(peer, msg, link_preview=False)
                                console.print(f"[yellow][INFO][/yellow] {phone}: медиа запрещено, отправлен текст в '{peer_title}'")
                        else:
                            await client.send_message(peer, msg, link_preview=False)
                            console.print(f"[green][SENT][/green] {phone}: текстовое сообщение в '{peer_title}'")
                    else:
                        await client.send_message(peer, msg, link_preview=False)
                        console.print(f"[green][SENT][/green] {phone}: текстовое сообщение в '{peer_title}'")
                except (FloodWaitError, ChatWriteForbiddenError, UserPrivacyRestrictedError,
                        PeerIdInvalidError, ChannelPrivateError, ChatAdminRequiredError,
                        MessageTooLongError, MessageIdInvalidError, SlowModeWaitError, RPCError) as e:
                    console.print(f"[yellow][SKIPPED][/yellow] {phone}: не можем написать в '{peer_title}' ({type(e).__name__})")
                    fmap.setdefault(SKIP_FOLDER_NAME, []).append(peer)
                except Exception:
                    console.print(f"[red][FAILED][/red] {phone}: критическая ошибка при отправке в '{peer_title}'")
                await asyncio.sleep(random.randint(cfg["min_delay"], cfg["max_delay"]))

    spam_tasks = [spam_with_client(clients[i], selected_accounts[i][0], folder_maps[i])
                  for i in range(len(clients))]
    await asyncio.gather(*spam_tasks)

    for c in clients:
        if c and c.is_connected():
            await c.disconnect()

    console.print(Panel("[bold green][INFO][/bold green] Рассылка завершена!", box=box.DOUBLE))
    await asyncio.to_thread(input)
