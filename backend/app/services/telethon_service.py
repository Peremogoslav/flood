import os
from typing import Dict, List
import asyncio
from telethon import TelegramClient, utils
from telethon.sessions import StringSession
from telethon.tl.functions.messages import GetDialogFiltersRequest
from telethon.tl.types import User, Chat, Channel, DialogFilter, DialogFilterDefault
from ..settings import settings


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
                try:
                    folder_title = f.title.text  # some builds expose .text
                except Exception:
                    folder_title = str(getattr(f, 'title', ''))
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
        # Fallback: if user has no folders configured, expose a synthetic folder with all dialogs
        if not folders_with_titles:
            titles = []
            for dialog in all_dialogs:
                entity = dialog.entity
                titles.append(getattr(entity, 'title', getattr(entity, 'username', str(getattr(entity, 'id', 'unknown')))))
            if titles:
                folders_with_titles["Все чаты"] = titles
        return folders_with_titles
    finally:
        if client.is_connected():
            async with lock:
                await client.disconnect()


async def get_folder_peers(session_file: str | None, folder_name: str, session_string: str | None = None):
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
            # Fallback: return all dialogs if no folders configured
            return [d.entity for d in all_dialogs]
        for f in filters_result.filters:
            if isinstance(f, DialogFilterDefault):
                continue
            try:
                current_title = f.title.text
            except Exception:
                current_title = str(getattr(f, 'title', ''))
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
            async with lock:
                await client.disconnect()

