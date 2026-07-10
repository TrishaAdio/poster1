"""Resolve (and if needed, join) the destination channel.

A userbot can only resolve/post to a channel it has joined. If POST_CHANNEL is
an invite link or public @username, we can join it automatically. If it's a
bare numeric id the account isn't in, we can't join it (no invite hash) — the
account must be added to that channel first.
"""
from __future__ import annotations

import re

from telethon import TelegramClient, utils
from telethon.errors import UserAlreadyParticipantError
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import (
    CheckChatInviteRequest,
    ImportChatInviteRequest,
)


def _invite_hash(text: str):
    """Extract the invite hash from a t.me/+HASH or t.me/joinchat/HASH link."""
    m = re.search(r"(?:t\.me/|telegram\.me/)(?:joinchat/|\+)([\w-]+)", text)
    return m.group(1) if m else None


def _username(text: str):
    """Extract a public @username (or t.me/name) if present."""
    t = text.strip()
    if t.startswith("@"):
        return t[1:]
    m = re.search(r"(?:t\.me/|telegram\.me/)([A-Za-z]\w{3,})/?$", t)
    return m.group(1) if m else None


async def _try_join(client: TelegramClient, ident):
    """Best-effort join when ident is an invite link or public username."""
    if not isinstance(ident, str):
        return None

    h = _invite_hash(ident)
    if h:
        try:
            upd = await client(ImportChatInviteRequest(h))
            print("Joined the channel via invite link.")
            return upd.chats[0]
        except UserAlreadyParticipantError:
            try:
                inv = await client(CheckChatInviteRequest(h))
                return getattr(inv, "chat", None)
            except Exception:
                return None
        except Exception as e:
            print(f"Could not join via invite link: {type(e).__name__}")
            return None

    uname = _username(ident)
    if uname:
        try:
            ent = await client.get_entity(uname)
            try:
                await client(JoinChannelRequest(ent))
                print(f"Joined @{uname}.")
            except Exception:
                pass  # already a member, or a channel that needs no join
            return ent
        except Exception:
            return None
    return None


async def resolve_channel(client: TelegramClient, ident):
    """Return the channel entity, or None if the account can't access it."""
    # 1) direct (cached id, or resolvable @username)
    try:
        return await client.get_entity(ident)
    except (ValueError, TypeError):
        pass

    # 2) if it's a link/username, try to join it
    joined = await _try_join(client, ident)
    if joined is not None:
        return joined

    # 3) scan the account's existing chats
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
            can_post = True
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
    else:
        print("\nThis account isn't in any channels yet.")
    print("  (or paste a @username or an invite link — the account will join it)")

    while True:
        raw = input("\nPick a number, or paste @username / invite link / id: ").strip()
        if not raw:
            continue
        if raw.isdigit() and chans:
            idx = int(raw)
            if 1 <= idx <= len(chans):
                chosen = chans[idx - 1]
                if not chosen["can_post"]:
                    print("  Note: this account has no post rights there yet — "
                          "make it an admin with 'Post messages'.")
                return str(chosen["id"])
            print("  out of range")
            continue
        return raw
