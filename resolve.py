"""Resolve the destination channel.

A userbot can only resolve/post to a channel it has actually joined. If the
direct lookup fails we warm the dialog cache and match by id; if still not
found, we return None so the caller can print helpful guidance.
"""
from __future__ import annotations

from telethon import TelegramClient, utils


async def resolve_channel(client: TelegramClient, ident):
    """Return the channel entity, or None if the account can't access it."""
    # 1) direct (works for @username, invite link, or a cached id)
    try:
        return await client.get_entity(ident)
    except (ValueError, TypeError):
        pass

    # 2) scan dialogs (the channel must be one this account has joined)
    print("Channel not cached — scanning your chats...")
    async for dialog in client.iter_dialogs():
        ent = dialog.entity
        if dialog.id == ident:
            return ent
        try:
            if ent is not None and utils.get_peer_id(ent) == ident:
                return ent
        except Exception:
            pass

    return None


async def list_channels(client: TelegramClient) -> list[tuple[int, str]]:
    """(id, title) for every broadcast/supergroup this account is in."""
    out = []
    async for dialog in client.iter_dialogs():
        if dialog.is_channel:
            out.append((dialog.id, dialog.name or "(no title)"))
    return out
