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


async def list_channels(client: TelegramClient) -> list[dict]:
    """Every broadcast channel / supergroup this account is in, with post hint."""
    out = []
    async for dialog in client.iter_dialogs():
        if not dialog.is_channel:
            continue
        e = dialog.entity
        broadcast = bool(getattr(e, "broadcast", False))
        creator = bool(getattr(e, "creator", False))
        ar = getattr(e, "admin_rights", None)
        if broadcast:
            can_post = creator or (ar is not None and getattr(ar, "post_messages", False))
        else:
            can_post = True  # normal members can post in groups
        out.append({
            "id": dialog.id,
            "title": dialog.name or "(no title)",
            "broadcast": broadcast,
            "can_post": can_post,
        })
    return out


async def choose_channel(client: TelegramClient) -> str:
    """Interactive terminal picker. Returns the chosen POST_CHANNEL value."""
    print("\nLoading your channels...")
    chans = await list_channels(client)
    if chans:
        print("\nChannels this account is in:")
        for i, c in enumerate(chans, 1):
            kind = "channel" if c["broadcast"] else "group"
            post = "can post" if c["can_post"] else "NO post rights"
            print(f"  {i:>2}. {c['title']}   [{kind}, {post}]   id={c['id']}")
        print("      (or paste a @username / id / invite link)")
    else:
        print("\nThis account isn't in any channels yet.")

    while True:
        raw = input("\nPick a number, or paste @username / id / link: ").strip()
        if not raw:
            continue
        if raw.isdigit() and chans:
            idx = int(raw)
            if 1 <= idx <= len(chans):
                chosen = chans[idx - 1]
                if not chosen["can_post"]:
                    print("  Warning: this account has no post rights there. "
                          "Make it an admin, or pick another.")
                return str(chosen["id"])
            print("  out of range")
            continue
        return raw
