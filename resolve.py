"""Resolve the destination channel, even a private one referenced by numeric id.

Telethon can't look up a private channel by bare id unless it's cached, so if
the direct lookup fails we warm the account's dialog cache and retry.
"""
from __future__ import annotations

from telethon import TelegramClient


async def resolve_channel(client: TelegramClient, ident):
    try:
        return await client.get_entity(ident)
    except (ValueError, TypeError):
        pass

    print("Channel not cached — loading dialogs to find it...")
    async for dialog in client.iter_dialogs():
        if dialog.id == ident or getattr(dialog.entity, "id", None) == ident:
            return dialog.entity

    return await client.get_entity(ident)
