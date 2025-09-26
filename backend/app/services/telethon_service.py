import os
from typing import Dict, List, Tuple
import asyncio
from telethon import TelegramClient, utils
from telethon.sessions import StringSession
from sqlalchemy.orm import Session as SASession
from ..models import SessionAccount
from telethon.tl.functions.messages import GetDialogFiltersRequest
from telethon.tl.types import User, Chat, Channel, DialogFilter, DialogFilterDefault
from ..settings import settings


def session_path(session_file: str | None, phone: str | None = None) -> str:
    os.makedirs(settings.sessions_dir, exist_ok=True)
    if session_file:
        return session_file
    if phone:
        return os.path.join(settings.sessions_dir, f"{phone}.session")
    raise ValueError("Either session_file or phone must be provided")


_SESSION_LOCKS: Dict[str, asyncio.Lock] = {}


def session_lock_for(path: str) -> asyncio.Lock:
    # normalize path to avoid duplicates
    key = os.path.abspath(path)
    lock = _SESSION_LOCKS.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _SESSION_LOCKS[key] = lock
    return lock


async def list_folders(session_file: str | None = None, session_string: str | None = None) -> Dict[str, List[str]]:
    if session_string:
        client = TelegramClient(StringSession(session_string), settings.api_id, settings.api_hash)
        lock = None
        await client.connect()
    else:
        client = TelegramClient(session_file, settings.api_id, settings.api_hash)
        lock = session_lock_for(session_file or "")
        async with lock:
            await client.connect()
    try:
        if not await client.is_user_authorized():
            return {}
        all_dialogs = [d async for d in client.iter_dialogs()]
        dialog_map = {utils.get_peer_id(d.entity): d.entity for d in all_dialogs}
        folders_with_titles: Dict[str, List[str]] = {}
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
                titles: List[str] = []
                added_peer_ids = set()
                if hasattr(f, 'include_peers'):
                    for peer in f.include_peers:
                        peer_id = utils.get_peer_id(peer)
                        if peer_id in dialog_map and peer_id not in added_peer_ids:
                            titles.append(getattr(dialog_map[peer_id], 'title', getattr(dialog_map[peer_id], 'username', str(peer_id))))
                            added_peer_ids.add(peer_id)
                for dialog in all_dialogs:
                    entity = dialog.entity
                    peer_id = utils.get_peer_id(entity)
                    if peer_id in added_peer_ids:
                        continue
                    if isinstance(f, DialogFilter):
                        if f.bots and isinstance(entity, User) and getattr(entity, 'bot', False):
                            titles.append(getattr(entity, 'title', getattr(entity, 'username', str(peer_id))))
                            added_peer_ids.add(peer_id)
                        if f.broadcasts and isinstance(entity, Channel) and not getattr(entity, 'megagroup', False):
                            titles.append(getattr(entity, 'title', getattr(entity, 'username', str(peer_id))))
                            added_peer_ids.add(peer_id)
                        if f.groups and (isinstance(entity, Chat) or (isinstance(entity, Channel) and getattr(entity, 'megagroup', False))):
                            titles.append(getattr(entity, 'title', getattr(entity, 'username', str(peer_id))))
                            added_peer_ids.add(peer_id)
                        if isinstance(entity, User):
                            if f.contacts and getattr(entity, 'contact', False):
                                titles.append(getattr(entity, 'first_name', str(peer_id)))
                                added_peer_ids.add(peer_id)
                            if f.non_contacts and not getattr(entity, 'contact', False):
                                titles.append(getattr(entity, 'first_name', str(peer_id)))
                                added_peer_ids.add(peer_id)
                folders_with_titles[folder_title] = titles
        return folders_with_titles
    finally:
        if client.is_connected():
            if lock:
                async with lock:
                    await client.disconnect()
            else:
                await client.disconnect()


async def get_folder_peers(session_file: str | None, folder_name: str, session_string: str | None = None):
    if session_string:
        client = TelegramClient(StringSession(session_string), settings.api_id, settings.api_hash)
        lock = None
        await client.connect()
    else:
        client = TelegramClient(session_file, settings.api_id, settings.api_hash)
        lock = session_lock_for(session_file or "")
        async with lock:
            await client.connect()
    try:
        if not await client.is_user_authorized():
            return []
        all_dialogs = [d async for d in client.iter_dialogs()]
        dialog_map = {utils.get_peer_id(d.entity): d.entity for d in all_dialogs}
        try:
            filters_result = await client(GetDialogFiltersRequest())
        except Exception:
            filters_result = None
        if not (filters_result and hasattr(filters_result, 'filters')):
            return []
        for f in filters_result.filters:
            if isinstance(f, DialogFilterDefault):
                continue
            current_title = f.title.text if hasattr(f.title, 'text') else str(f.title)
            if current_title != folder_name:
                continue
            peers = []
            added_peer_ids = set()
            if hasattr(f, 'include_peers'):
                for peer in f.include_peers:
                    peer_id = utils.get_peer_id(peer)
                    if peer_id in dialog_map and peer_id not in added_peer_ids:
                        peers.append(dialog_map[peer_id])
                        added_peer_ids.add(peer_id)
            for dialog in all_dialogs:
                entity = dialog.entity
                pid = utils.get_peer_id(entity)
                if pid in added_peer_ids:
                    continue
                if isinstance(f, DialogFilter):
                    if f.bots and isinstance(entity, User) and getattr(entity, 'bot', False):
                        peers.append(entity); added_peer_ids.add(pid)
                    if f.broadcasts and isinstance(entity, Channel) and not getattr(entity, 'megagroup', False):
                        peers.append(entity); added_peer_ids.add(pid)
                    if f.groups and (isinstance(entity, Chat) or (isinstance(entity, Channel) and getattr(entity, 'megagroup', False))):
                        peers.append(entity); added_peer_ids.add(pid)
                    if isinstance(entity, User):
                        if f.contacts and getattr(entity, 'contact', False):
                            peers.append(entity); added_peer_ids.add(pid)
                        if f.non_contacts and not getattr(entity, 'contact', False):
                            peers.append(entity); added_peer_ids.add(pid)
            return peers
        return []
    finally:
        if client.is_connected():
            if lock:
                async with lock:
                    await client.disconnect()
            else:
                await client.disconnect()

