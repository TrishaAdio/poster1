"""ZIP -> channel userbot.

Send a .zip to this account's DM (or Saved Messages). It is assigned #1, #2, ...
then downloaded, extracted, and posted to POST_CHANNEL:
  - images  -> native Telegram album (grouped grid, up to 9), caption Album - #N
  - videos  -> one by one, captioned  Video - #N   (bold)

Handles files up to ~2 GB (userbot login). Install cryptg for speed.

Run:  python userbot.py    (Ctrl+C to stop)
"""
from __future__ import annotations

import asyncio
import shutil
import time
import zipfile
from pathlib import Path

from telethon import TelegramClient, events

import config
import counter
import media

# Created in main() so the module stays importable without credentials.
client: TelegramClient | None = None

_queue: "asyncio.Queue[tuple]" = asyncio.Queue()
_state = {"self_id": 0, "channel": None}


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


def _is_zip(msg) -> bool:
    if not msg.document:
        return False
    name = (msg.file.name or "").lower() if msg.file else ""
    if name.endswith(".zip"):
        return True
    return (msg.document.mime_type or "") in (
        "application/zip", "application/x-zip-compressed", "multipart/x-zip",
    )


def _allowed(sender_id: int) -> bool:
    return sender_id == _state["self_id"] or sender_id in config.OWNERS


def _progress(status_msg, label: str):
    """Throttled progress callback (edits at most every 5% / 4s)."""
    st = {"pct": -5, "t": 0.0}

    async def cb(current, total):
        now = time.time()
        pct = int(current * 100 / total) if total else 0
        if pct >= st["pct"] + 5 or now - st["t"] >= 4:
            st["pct"], st["t"] = pct, now
            try:
                await status_msg.edit(
                    f"{label}: {pct}%  ({_human(current)} / {_human(total)})"
                )
            except Exception:
                pass

    return cb


def _safe_extract(zip_path: Path, dest: Path) -> None:
    """Extract, ignoring absolute/parent-traversal ('zip slip') members."""
    dest = dest.resolve()
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            target = (dest / member.filename).resolve()
            if str(target) == str(dest) or str(target).startswith(str(dest) + "/"):
                zf.extract(member, dest)


# --------------------------------------------------------------------------
# core processing
# --------------------------------------------------------------------------
async def process_zip(msg, zid: int) -> None:
    work = config.WORK_DIR / f"zip_{zid}_{int(time.time())}"
    work.mkdir(parents=True, exist_ok=True)
    zip_path = work / "archive.zip"
    status = await msg.reply(f"#{zid}: downloading...")

    try:
        await client.download_media(
            msg, file=str(zip_path), progress_callback=_progress(status, f"#{zid} download")
        )

        await status.edit(f"#{zid}: extracting...")
        extract_dir = work / "unz"
        extract_dir.mkdir()
        await asyncio.to_thread(_safe_extract, zip_path, extract_dir)

        images, videos = await asyncio.to_thread(media.scan, extract_dir)
        if not images and not videos:
            await status.edit(f"#{zid}: no images or videos found.")
            return
        await status.edit(
            f"#{zid}: {len(images)} image(s), {len(videos)} video(s). Posting..."
        )

        channel = _state["channel"]
        albums = 0

        # --- images -> native Telegram albums (Album - #N) ------------------
        # Passing a list of files to send_file groups them into one album, which
        # Telegram lays out in its own grid. Caption goes on the first item.
        for batch in media.chunk(images, config.ALBUM_SIZE):
            files = [str(p) for p in batch]
            await client.send_file(
                channel, files,
                caption=f"<b>Album - #{zid}</b>", parse_mode="html",
                progress_callback=_progress(status, f"#{zid} album {albums + 1}"),
            )
            albums += 1
            await asyncio.sleep(config.SEND_DELAY)

        # --- videos -> one by one (Video - #N) ------------------------------
        sent_videos = 0
        for v in videos:
            await client.send_file(
                channel, str(v),
                caption=f"<b>Video - #{zid}</b>", parse_mode="html",
                supports_streaming=True,
                progress_callback=_progress(status, f"#{zid} video {sent_videos + 1}/{len(videos)}"),
            )
            sent_videos += 1
            await asyncio.sleep(config.SEND_DELAY)

        await status.edit(
            f"#{zid}: done. {albums} album(s), {sent_videos} video(s) posted."
        )
    finally:
        shutil.rmtree(work, ignore_errors=True)


async def _worker() -> None:
    while True:
        msg, zid = await _queue.get()
        try:
            await process_zip(msg, zid)
        except Exception as e:  # noqa: BLE001
            try:
                await msg.reply(f"#{zid}: failed - {type(e).__name__}: {e}")
            except Exception:
                pass
            print(f"#{zid} error: {e!r}")
        finally:
            _queue.task_done()


# --------------------------------------------------------------------------
# handler
# --------------------------------------------------------------------------
async def on_message(event):
    if not event.is_private or not _is_zip(event.message):
        return
    if not _allowed(event.sender_id):
        return
    zid = counter.next_id()
    await event.reply(f"Queued as #{zid} (in queue: {_queue.qsize() + 1}).")
    await _queue.put((event.message, zid))


async def main() -> None:
    global client
    config.require("API_ID", "API_HASH", "POST_CHANNEL_RAW")

    client = TelegramClient(config.SESSION, config.API_ID, config.API_HASH)
    client.add_event_handler(on_message, events.NewMessage)
    await client.start()  # prompts phone + OTP on first run

    me = await client.get_me()
    _state["self_id"] = me.id

    from resolve import list_channels, resolve_channel

    channel = await resolve_channel(client, config.post_channel())
    if channel is None:
        print(f"\nCould not access POST_CHANNEL={config.POST_CHANNEL_RAW!r}.")
        print(f"This account ({me.first_name}, id {me.id}) must be a MEMBER of "
              "the channel, and an ADMIN with post rights to post there.\n")
        chans = await list_channels(client)
        if chans:
            print("Channels this account is currently in:")
            for cid, title in chans:
                print(f"  {cid}   {title}")
            print("\nSet POST_CHANNEL in .env to one of the ids above (or its "
                  "@username / invite link), make sure this account can post, "
                  "then run again.")
        else:
            print("This account isn't in any channels yet. Join/get added to your "
                  "target channel (with post rights), then run again.")
        await client.disconnect()
        return

    _state["channel"] = channel
    asyncio.create_task(_worker())
    print(f"Running as {me.first_name} (id {me.id}).")
    print(f"Posting to: {getattr(channel, 'title', channel)}")
    print("Send a .zip to this account's DM / Saved Messages. Ctrl+C to stop.")
    await client.run_until_disconnected()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
