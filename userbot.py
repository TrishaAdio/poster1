"""ZIP -> channel userbot.

Send a .zip to this account's DM (or Saved Messages). It is assigned #1, #2, ...
then downloaded, extracted, and posted to POST_CHANNEL:
  - images  -> native Telegram album (grouped grid, up to 9), caption Album - #N
  - videos  -> one by one, captioned  Video - #N   (bold)
             (videos over MAX_VIDEO_MB are skipped; a real thumbnail is
              generated via ffmpeg so none show up as a black square)

Progress for zips sent from Saved Messages is printed to the TERMINAL (no
message edits), to avoid flooding Saved Messages.

Handles files up to ~2 GB (userbot login). Install cryptg for speed and ffmpeg
for video thumbnails.

Run:  python userbot.py    (Ctrl+C to stop)
"""
from __future__ import annotations

import asyncio
import shutil
import time
import zipfile
from pathlib import Path

from telethon import TelegramClient, events
from telethon.tl.types import DocumentAttributeVideo

import config
import counter
import media
import video

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


class Reporter:
    """Status output. In Saved Messages -> print to terminal (no edits, no
    flood). In another DM -> edit a single status message."""

    def __init__(self, zid: int, status_msg=None):
        self.zid = zid
        self.status = status_msg  # None => terminal only

    async def set(self, text: str) -> None:
        line = f"#{self.zid}: {text}"
        if self.status is None:
            print(line, flush=True)
        else:
            try:
                await self.status.edit(line)
            except Exception:
                pass

    def progress(self, label: str):
        """Throttled progress callback (at most every 5% / 4s)."""
        st = {"pct": -5, "t": 0.0}

        async def cb(current, total):
            now = time.time()
            pct = int(current * 100 / total) if total else 0
            if pct >= st["pct"] + 5 or now - st["t"] >= 4:
                st["pct"], st["t"] = pct, now
                await self.set(f"{label}: {pct}%  ({_human(current)} / {_human(total)})")

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

    # Saved Messages -> terminal progress (no message edits, no flood).
    is_saved = msg.chat_id == _state["self_id"]
    status_msg = None if is_saved else await msg.reply(f"#{zid}: downloading...")
    rep = Reporter(zid, status_msg)

    try:
        await rep.set("downloading...")
        await client.download_media(
            msg, file=str(zip_path), progress_callback=rep.progress("download")
        )

        await rep.set("extracting...")
        extract_dir = work / "unz"
        extract_dir.mkdir()
        await asyncio.to_thread(_safe_extract, zip_path, extract_dir)

        images, videos = await asyncio.to_thread(media.scan, extract_dir)
        if not images and not videos:
            await rep.set("no images or videos found.")
            return
        await rep.set(f"{len(images)} image(s), {len(videos)} video(s). Posting...")

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
                progress_callback=rep.progress(f"album {albums + 1}"),
            )
            albums += 1
            await asyncio.sleep(config.SEND_DELAY)

        # --- videos -> one by one (Video - #N) ------------------------------
        # Skip videos over the size limit; generate a real thumbnail so none
        # appear as a black square.
        sent_videos = 0
        skipped = 0
        for v in videos:
            size = v.stat().st_size
            if size > config.MAX_VIDEO_BYTES:
                skipped += 1
                await rep.set(
                    f"skipped {v.name} ({_human(size)} > {config.MAX_VIDEO_MB:.0f}MB)"
                )
                continue

            thumb_path = work / f"thumb_{sent_videos}.jpg"
            meta = await asyncio.to_thread(video.probe, str(v))
            has_thumb = await asyncio.to_thread(video.make_thumbnail, str(v), str(thumb_path))

            attributes = None
            if meta and (meta["w"] or meta["duration"]):
                attributes = [DocumentAttributeVideo(
                    duration=meta["duration"], w=meta["w"] or 0, h=meta["h"] or 0,
                    supports_streaming=True,
                )]

            await client.send_file(
                channel, str(v),
                caption=f"<b>Video - #{zid}</b>", parse_mode="html",
                supports_streaming=True,
                thumb=str(thumb_path) if has_thumb else None,
                attributes=attributes,
                progress_callback=rep.progress(f"video {sent_videos + 1}/{len(videos)}"),
            )
            sent_videos += 1
            await asyncio.sleep(config.SEND_DELAY)

        summary = f"done. {albums} album(s), {sent_videos} video(s) posted"
        if skipped:
            summary += f", {skipped} video(s) skipped (> {config.MAX_VIDEO_MB:.0f}MB)"
        await rep.set(summary + ".")
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
    qpos = _queue.qsize() + 1
    if event.chat_id == _state["self_id"]:
        print(f"Queued zip as #{zid} (in queue: {qpos}).", flush=True)
    else:
        await event.reply(f"Queued as #{zid} (in queue: {qpos}).")
    await _queue.put((event.message, zid))


async def main() -> None:
    global client
    config.require("API_ID", "API_HASH")  # channel is chosen interactively if needed

    client = TelegramClient(config.SESSION, config.API_ID, config.API_HASH)
    client.add_event_handler(on_message, events.NewMessage)
    await client.start()  # prompts phone + OTP on first run

    me = await client.get_me()
    _state["self_id"] = me.id

    from resolve import choose_channel, resolve_channel

    # Try the configured channel; if it's missing or unusable, just let the
    # user pick one from a list right here — no fiddling with .env needed.
    channel = None
    if config.POST_CHANNEL_RAW.strip():
        channel = await resolve_channel(client, config.post_channel())
        if channel is None:
            print(f"\nCould not use POST_CHANNEL={config.POST_CHANNEL_RAW!r} "
                  f"(this account isn't in it). Pick one below.")

    while channel is None:
        value = await choose_channel(client)
        channel = await resolve_channel(client, config.coerce_channel(value))
        if channel is None:
            print("  Couldn't access that one — try another (or paste an "
                  "invite link so the account joins).")
            continue
        config.save_post_channel(value)  # remember it for next time
        print("Saved this channel to .env.")

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
