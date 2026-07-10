# ZIP -> Channel Userbot (Telethon)

Send a **.zip** to this userbot's DM (or Saved Messages). It:

1. Assigns it a sequential id: **#1, #2, #3 ...**
2. Downloads and extracts it (files up to ~**2 GB**).
3. Posts the contents to your channel:
   - **Images** -> grouped into a **native Telegram album** (Telegram's own grid
     layout, up to 9 per album), captioned **`Album - #N`**
   - **Videos** -> sent **one by one**, each captioned **`Video - #N`**

Captions are **bold**. The id `#N` is the same for everything from one zip.

## Setup

```bash
pip install -r requirements.txt
python setup.py
```

`setup.py` asks for `API_ID` / `API_HASH` (from https://my.telegram.org), the
destination channel, and logs in your account (phone -> OTP code -> 2FA
password if set). It writes `.env` and creates the session.

> The logged-in account must be able to **post** in the target channel.

## Run

```bash
python userbot.py
```

Leave it running, then send a `.zip` to the account's **DM** or **Saved
Messages**. You'll get a `Queued as #N` reply, then live progress while it
downloads and posts.

## Speed

`cryptg` is installed via requirements — it makes MTProto crypto (the bottleneck
for big files) much faster, so 2 GB downloads/uploads run at full speed with no
extra setup. Jobs are queued and processed one at a time to stay smooth and
avoid flood limits.

## Files

| File          | Role                                                        |
|---------------|-------------------------------------------------------------|
| `setup.py`    | Interactive setup: creds + channel + OTP login, writes .env |
| `config.py`   | Loads `.env`, paths, album/pacing settings                  |
| `userbot.py`  | Main: watches DM for zips, downloads, posts albums/videos   |
| `media.py`    | Finds images/videos in the extracted folder (natural sort)  |
| `counter.py`  | Persistent `#N` counter                                     |
| `resolve.py`  | Resolves the channel (even a private one by numeric id)     |

## Tuning (`.env`)

| Var          | Default | Meaning                                     |
|--------------|---------|---------------------------------------------|
| `ALBUM_SIZE` | 9       | images per Telegram album (max 10)          |
| `SEND_DELAY` | 2       | seconds between posts (flood safety)        |
| `OWNERS`     | —       | extra user ids allowed to send zips         |

## Notes

- Images post as a **real Telegram album** (compressed photos in Telegram's
  grid), not a stitched image — matches the native look.
- Only the logged-in account (Saved Messages) and any ids in `OWNERS` can
  trigger processing — random DMs are ignored.
- Supported images: jpg/png/webp/bmp/gif/tiff/heic. Videos:
  mp4/mkv/avi/mov/webm/m4v and more.
- `__MACOSX`, `.DS_Store`, `Thumbs.db` are ignored.
- `.env` and `*.session` are gitignored — never commit them.
