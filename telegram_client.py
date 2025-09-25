# telegram_client.py
import os
import traceback
from telethon import TelegramClient, utils
from telethon.errors import PhoneNumberInvalidError, SessionPasswordNeededError, PhoneCodeInvalidError
from telethon.tl.functions.chatlists import CheckChatlistInviteRequest, JoinChatlistInviteRequest
from telethon.tl.functions.messages import GetDialogFiltersRequest
from telethon.tl.types import User, Chat, Channel, DialogFilter, DialogFilterDefault
from rich.console import Console
from constants import API_ID, API_HASH, SESSIONS_DIR
from db import delete_session
console = Console()

os.makedirs(SESSIONS_DIR, exist_ok=True)

async def init_client(session_file: str):
    """
    Инициализирует клиент и возвращает (client, folders_with_chats) или (None, {})
    """
    client = None
    try:
        client = TelegramClient(session_file, API_ID, API_HASH)
        await client.connect()

        if not await client.is_user_authorized():
            console.print(f"[yellow][WARNING][/yellow] Сессия {session_file} потеряла авторизацию.")
            try:
                # Удаляем файл
                if os.path.exists(session_file):
                    os.remove(session_file)

                # Чистим запись в БД
                if delete_session(session_file):
                    console.print(f"[green][SUCCESS][/green] Запись о {session_file} удалена из БД.")
                else:
                    console.print(f"[red][FAILED][/red] Не удалось удалить запись о {session_file} из БД.")
            except OSError:
                console.print(f"[red][FAILED][/red] Не удалось удалить {session_file}")
            await client.disconnect()
            return None, {}

        all_dialogs = [d async for d in client.iter_dialogs()]
        dialog_map = {utils.get_peer_id(d.entity): d.entity for d in all_dialogs}
        folders_with_chats = {}

        filters_result = None
        try:
            filters_result = await client(GetDialogFiltersRequest())
        except Exception:
            filters_result = None

        if filters_result and hasattr(filters_result, "filters"):
            for f in filters_result.filters:
                if isinstance(f, DialogFilterDefault):
                    continue

                folder_title = f.title.text if hasattr(f.title, 'text') else str(f.title)
                chats_in_folder = []
                added_peer_ids = set()

                if hasattr(f, 'include_peers'):
                    for peer in f.include_peers:
                        peer_id = utils.get_peer_id(peer)
                        if peer_id in dialog_map and peer_id not in added_peer_ids:
                            chats_in_folder.append(dialog_map[peer_id])
                            added_peer_ids.add(peer_id)

                for dialog in all_dialogs:
                    entity = dialog.entity
                    peer_id = utils.get_peer_id(entity)
                    if peer_id in added_peer_ids:
                        continue

                    if isinstance(f, DialogFilter):
                        if f.bots and isinstance(entity, User) and getattr(entity, 'bot', False):
                            chats_in_folder.append(entity)
                            added_peer_ids.add(peer_id)
                        if f.broadcasts and isinstance(entity, Channel) and not getattr(entity, 'megagroup', False):
                            chats_in_folder.append(entity)
                            added_peer_ids.add(peer_id)
                        if f.groups and (isinstance(entity, Chat) or (
                                isinstance(entity, Channel) and getattr(entity, 'megagroup', False))):
                            chats_in_folder.append(entity)
                            added_peer_ids.add(peer_id)
                        if isinstance(entity, User):
                            if f.contacts and getattr(entity, 'contact', False):
                                chats_in_folder.append(entity)
                                added_peer_ids.add(peer_id)
                            if f.non_contacts and not getattr(entity, 'contact', False):
                                chats_in_folder.append(entity)
                                added_peer_ids.add(peer_id)

                folders_with_chats[folder_title] = chats_in_folder

        return client, folders_with_chats

    except Exception as e:
        if "SQLite" in str(e) or "database disk image is malformed" in str(e):
            console.print(f"[yellow][WARNING][/yellow] Файл сессии {session_file} поврежден, удаляю...")
            try:
                if os.path.exists(session_file):
                    os.remove(session_file)
            except OSError:
                console.print(f"[red][FAILED][/red] Не удалось удалить {session_file}")
            return None, {}
        console.print(f"[red][FAILED][/red] Ошибка при инициализации клиента ({os.path.basename(session_file)}): {e}")
        traceback.print_exc()
        if client and client.is_connected():
            await client.disconnect()
        return None, {}

async def add_folder_by_link_to_accounts(selected_accounts, link):
    """
    selected_accounts: list of tuples (phone, session_file)
    link: ссылка содержащая addlist/slug
    """
    if "addlist" not in link:
        console.print("[red][FAILED][/red] Это не ссылка addlist!")
        return

    slug = link.split("addlist/")[-1]

    for phone, session_file in selected_accounts:
        client = TelegramClient(session_file, API_ID, API_HASH)
        await client.connect()

        if not await client.is_user_authorized():
            console.print(f"[yellow][WARNING][/yellow] Аккаунт {phone} не авторизован!")
            await client.disconnect()
            continue

        try:
            result_check = await client(CheckChatlistInviteRequest(slug=slug))
            await client(JoinChatlistInviteRequest(slug=slug, peers=result_check.peers))
            console.print(f"[green][SUCCESS][/green] Папка подключена для {phone}")
        except Exception as e:
            console.print(f"[red][FAILED][/red] Не удалось подключить папку для {phone}: {e}")
        finally:
            await client.disconnect()

async def try_authorize_new_account(session_file: str, phone: str, console):
    """
    Простой поток авторизации (посыл кода, ввод кода/2fa) — вызывается из add_account.
    Возвращает True если авторизовали.
    """
    client = TelegramClient(session_file, API_ID, API_HASH)
    await client.connect()
    try:
        await client.send_code_request(phone)
    except PhoneNumberInvalidError:
        console.print(f"[red][FAILED][/red] Номер {phone} не найден в Telegram или имеет неверный формат.")
        await client.disconnect()
        return False

    code_ok = False
    for _ in range(3):
        code = input("Введите код из Telegram или 0 для возврата: ").strip()
        if code == "0":
            await client.disconnect()
            return False
        try:
            await client.sign_in(phone, code)
            code_ok = True
            break
        except PhoneCodeInvalidError:
            console.print("[red][FAILED][/red] Неверный код, попробуйте ещё раз.")
        except SessionPasswordNeededError:
            while True:
                pwd = pwinput.pwinput(prompt="Введите пароль 2FA или 0 для возврата: ", mask="*").strip()
                if pwd == "0":
                    await client.disconnect()
                    return False
                try:
                    await client.sign_in(password=pwd)
                    code_ok = True
                    break
                except Exception as e:
                    console.print(f"[red][FAILED][/red] Ошибка 2FA: {e}")
            if code_ok:
                break

    if not code_ok:
        await client.disconnect()
        return False

    await client.disconnect()
    return True
