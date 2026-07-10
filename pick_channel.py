#!/usr/bin/env python3
"""List the channels this account is in and set POST_CHANNEL in .env.

Use this after setup to (re)choose the destination channel — it reuses your
existing login, so no OTP is needed.

Run:  python pick_channel.py
"""
from __future__ import annotations

import asyncio

from telethon import TelegramClient

import config
from resolve import choose_channel


async def main() -> None:
    config.require("API_ID", "API_HASH")
    client = TelegramClient(config.SESSION, config.API_ID, config.API_HASH)
    await client.start()
    me = await client.get_me()
    print(f"Logged in as {me.first_name} (id {me.id}).")

    value = await choose_channel(client)
    config.save_post_channel(value)
    print(f"\nSaved POST_CHANNEL={value} to .env")
    print("Start the bot with:  python userbot.py")
    await client.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nCancelled.")
