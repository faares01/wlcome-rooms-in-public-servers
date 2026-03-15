#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shadow Guard — Welcome Bot
  config/token.txt     <- account token
  config/settings.json <- IDs and settings
  config/messages.json <- welcome messages and AFK keywords
  data/cooldowns.json  <- cooldown data (auto)
"""

import discord
from discord.ext import commands
import asyncio
import json
import logging
import os
import sys
import time
import platform
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── Windows ANSI ──────────────────────────────────────────
_IS_WIN = platform.system() == "Windows"
if _IS_WIN:
    os.system("")

# ── Save real stdout/stderr before any redirect ───────────
_STDOUT = sys.stdout
_STDERR = sys.stderr

# ── Route discord logs to file only ──────────────────────
_DATA_DIR = Path(__file__).parent / "data"
_DATA_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.WARNING,
    handlers=[logging.FileHandler(str(_DATA_DIR / "bot.log"), encoding="utf-8")]
)
for _n in ("discord", "discord.http", "discord.gateway",
           "discord.client", "discord.voice_client", "asyncio"):
    logging.getLogger(_n).setLevel(logging.ERROR)

# ═══════════════════════════════════════════════
#   Paths
# ═══════════════════════════════════════════════

BASE_DIR       = Path(__file__).parent
CONFIG_DIR     = BASE_DIR / "config"
DATA_DIR       = BASE_DIR / "data"
SETTINGS_FILE  = CONFIG_DIR / "settings.json"
MESSAGES_FILE  = CONFIG_DIR / "messages.json"
TOKEN_FILE     = CONFIG_DIR / "token.txt"
COOLDOWNS_FILE = DATA_DIR   / "cooldowns.json"

# ═══════════════════════════════════════════════
#   Defaults
# ═══════════════════════════════════════════════

DEFAULT_SETTINGS = {
    "server_id":       "",
    "main_room_id":    "",
    "waiting_room_id": "",
    "status":          "online",
    "owner_id":        "1111705596543119370",
}

DEFAULT_MESSAGES = {
    "statuses": {
        "online":  "Welcome [mention]! 👋",
        "dnd":     "Hey [mention]! 🔴 faa is busy.",
        "afk":     "Hey [mention]! 😴 faa is AFK.",
        "custom4": ""
    },
    "afk_auto_reply": "🌙 faa is AFK, he'll reply when back!",
    "afk_keywords":   ["where faa", "where faris", "faa where", "faa?"]
}

# ═══════════════════════════════════════════════
#   Thread-safe storage
# ═══════════════════════════════════════════════

_lock     = threading.Lock()
_settings: dict = {}
_messages: dict = {}
_cooldowns: dict = {}

def _deep(d): return json.loads(json.dumps(d))

def _write(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _read(path: Path, default: dict) -> dict:
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    data = _deep(default)
    _write(path, data)
    return data

def reload_all():
    global _settings, _messages, _cooldowns
    with _lock:
        _settings  = _read(SETTINGS_FILE,  DEFAULT_SETTINGS)
        _messages  = _read(MESSAGES_FILE,  DEFAULT_MESSAGES)
        _cooldowns = _read(COOLDOWNS_FILE, {})

def cfg() -> dict:
    with _lock: return _deep(_settings)

def msgs() -> dict:
    with _lock: return _deep(_messages)

def save_cfg(data: dict):
    global _settings
    with _lock:
        _settings = _deep(data)
        _write(SETTINGS_FILE, _settings)

def save_msgs(data: dict):
    global _messages
    with _lock:
        _messages = _deep(data)
        _write(MESSAGES_FILE, _messages)

def save_cd(uid: str, ts: float):
    global _cooldowns
    with _lock:
        _cooldowns[uid] = ts
        _write(COOLDOWNS_FILE, _cooldowns)

def load_token() -> Optional[str]:
    try:
        if TOKEN_FILE.exists():
            t = TOKEN_FILE.read_text(encoding="utf-8").strip()
            return t or None
    except Exception:
        pass
    return None

def write_token(t: str):
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(t.strip(), encoding="utf-8")

def ensure_dirs():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

# ═══════════════════════════════════════════════
#   Helpers
# ═══════════════════════════════════════════════

def is_owner(uid) -> bool:
    return str(uid) == str(cfg().get("owner_id", ""))

def on_cd(uid: str) -> bool:
    with _lock:
        return (time.time() - _cooldowns.get(uid, 0)) < 300

def build_welcome(status: str, member) -> str:
    m   = msgs()
    sts = m.get("statuses", DEFAULT_MESSAGES["statuses"])
    txt = sts.get(status) or sts.get("online") or "Welcome [mention]!"
    return txt.replace("[mention]", member.mention)

def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d  %I:%M %p")

# ═══════════════════════════════════════════════
#   Bot
# ═══════════════════════════════════════════════

_bot_loop: Optional[asyncio.AbstractEventLoop] = None
_welcomed_waiting: dict = {}   # uid -> set of channel ids already welcomed in

bot = commands.Bot(command_prefix="%", self_bot=True)

@bot.event
async def on_ready():
    c = cfg()
    try:
        pass  # selfbot — don't rename
    except Exception:
        pass

@bot.event
async def on_voice_state_update(member, before, after):
    c     = cfg()
    s_id  = str(c.get("server_id",       ""))
    m_ch  = str(c.get("main_room_id",    ""))
    w_ch  = str(c.get("waiting_room_id", ""))
    stat  = c.get("status", "online")

    if not s_id or not m_ch:                      return
    if not hasattr(member, "guild"):              return
    if str(member.guild.id) != s_id:             return
    if is_owner(member.id):                       return
    if after.channel is None:                     return
    if before.channel == after.channel:           return

    ch_id   = str(after.channel.id)
    is_main = ch_id == m_ch
    is_wait = bool(w_ch) and ch_id == w_ch

    if not (is_main or is_wait): return

    uid = str(member.id)
    if on_cd(uid): return

    # Moved from waiting to main → skip welcome, clear memory
    if is_main and uid in _welcomed_waiting:
        _welcomed_waiting.pop(uid, None)
        return

    # Waiting room → don't re-welcome same room
    if is_wait:
        _welcomed_waiting.setdefault(uid, set())
        if ch_id in _welcomed_waiting[uid]: return
        _welcomed_waiting[uid].add(ch_id)

    save_cd(uid, time.time())

    try:
        await after.channel.send(build_welcome(stat, member))
    except Exception:
        pass

@bot.event
async def on_message(message):
    if message.author == bot.user: return
    await bot.process_commands(message)

    c        = cfg()
    m        = msgs()
    stat     = c.get("status", "online")
    m_ch     = str(c.get("main_room_id",    ""))
    w_ch     = str(c.get("waiting_room_id", ""))
    owner_id = str(c.get("owner_id", ""))
    ch_id    = str(message.channel.id)
    in_room  = ch_id == m_ch or (bool(w_ch) and ch_id == w_ch)

    if stat != "afk" or not in_room: return

    cl       = message.content.lower()
    kws      = m.get("afk_keywords", [])
    pinged   = f"<@{owner_id}>" in message.content or f"<@!{owner_id}>" in message.content
    kw_hit   = any(k.lower() in cl for k in kws)

    if pinged or kw_hit:
        reply = m.get("afk_auto_reply", "")
        if reply:
            try:    await message.reply(reply)
            except Exception:
                try: await message.channel.send(reply)
                except Exception: pass

@bot.command(name="test")
async def _cmd_test(ctx):
    if not is_owner(ctx.author.id): return
    c    = cfg()
    m    = msgs()
    m_ch = c.get("main_room_id",    "")
    w_ch = c.get("waiting_room_id", "")
    stat = c.get("status", "online")
    sts  = m.get("statuses", {})
    txt  = (sts.get(stat) or sts.get("online", "Welcome [mention]!")).replace(
        "[mention]", ctx.author.mention)
    sent = 0
    for rid in [r for r in [m_ch, w_ch] if r]:
        ch = bot.get_channel(int(rid))
        if ch:
            try: await ch.send(f"**%test** ← {txt}"); sent += 1
            except Exception: pass
    try:
        await ctx.send(f"✅ Test sent in {sent} room(s).", delete_after=5)
    except Exception: pass

def _run_bot(token: str):
    global _bot_loop
    _bot_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_bot_loop)
    _bot_loop.set_exception_handler(lambda loop, ctx: None)
    try:
        _bot_loop.run_until_complete(bot.start(token))
    except Exception:
        pass

def run_async(coro, timeout: int = 5):
    if not _bot_loop:
        return None
    try:
        return asyncio.run_coroutine_threadsafe(coro, _bot_loop).result(timeout=timeout)
    except Exception:
        return None

# ═══════════════════════════════════════════════
#   Terminal
# ═══════════════════════════════════════════════

def _getch() -> str:
    if _IS_WIN:
        import msvcrt
        ch = msvcrt.getwch()
        if ch in ('\xe0', '\x00'):
            ch2 = msvcrt.getwch()
            return {'H':'UP','P':'DOWN','K':'LEFT','M':'RIGHT'}.get(ch2, '')
        if ch == '\r':   return 'ENTER'
        if ch == '\x1b': return 'ESC'
        if ch == ' ':    return 'SPACE'
        if ch == '\x08': return 'BACKSPACE'
        if ch == '\x03': raise KeyboardInterrupt
        return ch
    else:
        import tty, termios
        import select as _sel
        fd  = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == '\x1b':
                r, _, _ = _sel.select([sys.stdin], [], [], 0.05)
                if r:
                    ch2 = sys.stdin.read(1)
                    if ch2 == '[':
                        ch3 = sys.stdin.read(1)
                        return {'A':'UP','B':'DOWN','C':'RIGHT','D':'LEFT'}.get(ch3, '')
                return 'ESC'
            if ch in ('\r', '\n'): return 'ENTER'
            if ch == '\x7f':       return 'BACKSPACE'
            if ch == '\x03':       raise KeyboardInterrupt
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

def _print(*a, **kw):
    kw.setdefault("file", _STDOUT)
    print(*a, **kw)
    _STDOUT.flush()

def _readline() -> str:
    if not _IS_WIN:
        import termios
        fd  = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    try:
        return input().strip()
    except (EOFError, KeyboardInterrupt):
        return ""

# ═══════════════════════════════════════════════
#   ANSI
# ═══════════════════════════════════════════════

_C = sys.stdout.isatty()
G   = "\033[92m" if _C else ""
R   = "\033[91m" if _C else ""
Y   = "\033[93m" if _C else ""
CY  = "\033[96m" if _C else ""
DIM = "\033[2m"  if _C else ""
BLD = "\033[1m"  if _C else ""
RST = "\033[0m"  if _C else ""

# ═══════════════════════════════════════════════
#   Menu helpers
# ═══════════════════════════════════════════════

def _clr():
    os.system("cls" if _IS_WIN else "clear")

def _header(title: str):
    w  = max(52, len(title) + 4)
    pl = (w - len(title)) // 2
    pr = w - len(title) - pl
    _print(f"\n  ╔{'═'*w}╗")
    _print(f"  ║{' '*pl}{BLD}{title}{RST}{' '*pr}║")
    _print(f"  ╚{'═'*w}╝\n")

def _nav(extra=""): return f"  {DIM}↑↓ Navigate   Enter Select   Esc Back{extra}{RST}"

def select(title: str, options: list, hint: str = "") -> int:
    idx = 0
    h   = hint or _nav()
    while True:
        _clr(); _header(title)
        for i, opt in enumerate(options):
            cur = f"{CY}►{RST}" if i == idx else " "
            _print(f"  {cur} {opt}")
        _print(f"\n{h}")
        k = _getch()
        if   k == 'UP':              idx = (idx - 1) % len(options)
        elif k == 'DOWN':            idx = (idx + 1) % len(options)
        elif k == 'ENTER':           return idx
        elif k in ('ESC', 'q', 'Q'): return -1

def ask(prompt: str, current: str = "", optional: bool = False) -> str:
    cur = f" {DIM}(current: {current}){RST}" if current else ""
    opt = f" {DIM}(optional){RST}" if optional else ""
    _print(f"\n  {BLD}{prompt}{RST}{cur}{opt}")
    _STDOUT.write("  > "); _STDOUT.flush()
    v = _readline()
    return v if v else current

def ask_req(prompt: str, current: str = "") -> str:
    while True:
        v = ask(prompt, current)
        if v: return v
        _print(f"  {R}Required.{RST}")

def ask_multiline(prompt: str, current: str = "", optional: bool = False) -> str:
    """Multi-line input. Empty line = done. Type CLEAR to wipe. Enter alone on empty = keep current."""
    cur_display = current.replace("\n", " | ") if current else ""
    cur_hint = f" {DIM}(current: {cur_display[:40]}){RST}" if current else ""
    opt_hint = f" {DIM}(optional){RST}" if optional else ""
    _print(f"\n  {BLD}{prompt}{RST}{cur_hint}{opt_hint}")
    _print(f"  {DIM}Type your message. Press Enter twice when done.{RST}")
    _print(f"  {DIM}Type CLEAR to delete current message.{RST}\n")
    lines = []
    while True:
        _STDOUT.write("  > "); _STDOUT.flush()
        line = _readline()
        if line.strip().upper() == "CLEAR":
            return ""
        if line == "" and not lines:
            # Nothing typed at all — keep current
            return current
        if line == "":
            # Empty line after typing something — done
            break
        lines.append(line)
    result = "\n".join(lines)
    return result if result else current


def pause(msg="Press any key to go back..."):
    _print(f"\n  {DIM}{msg}{RST}")
    _getch()

def _v(x): return str(x) if x else f"{DIM}not set{RST}"
def _t(x, n=24): s=str(x) if x else ""; return (s[:n]+"…") if len(s)>n else s
def _dot(on): return f"{G}●{RST}" if on else f"{R}○{RST}"
def _st(on):  return f"{G}[ON ]{RST}" if on else f"{R}[OFF]{RST}"

def _bot_tag():
    return f"{G}● Connected{RST}" if bot.is_ready() else f"{R}○ Not connected{RST}"

# ═══════════════════════════════════════════════
#   CLI pages
# ═══════════════════════════════════════════════

def cli_main():
    time.sleep(2)   # let bot connect
    while True:
        c    = cfg()
        stat = c.get("status", "online")
        opts = [
            f"  Status",
            f"  Welcome Setup      status:{stat}  srv:{_t(_v(c.get('server_id','')))}",
            f"  Messages           Edit welcome messages and AFK",
            f"  Test               Send %test to configured rooms",
            "  Exit",
        ]
        ch = select("Shadow Guard", opts, hint=f"  {DIM}↑↓ Navigate   Enter Select{RST}")
        if   ch == 0: _page_status()
        elif ch == 1: _page_setup()
        elif ch == 2: _page_messages()
        elif ch == 3: _do_test()
        elif ch in (4, -1):
            _clr(); _print("\n  Goodbye!\n"); os._exit(0)

# ── Status ────────────────────────────────────

def _page_status():
    c = cfg()
    _clr(); _header("Status")
    _print(f"  Discord:        {_bot_tag()}")
    _print(f"  Time:           {now_str()}")
    _print()
    _print(f"  Server ID:      {_v(c.get('server_id',''))}")
    _print(f"  Main Room:      {_v(c.get('main_room_id',''))}")
    _print(f"  Waiting Room:   {c.get('waiting_room_id','') or f'{DIM}none{RST}'}")
    _print(f"  Status:         {BLD}{c.get('status','online')}{RST}")
    _print(f"  Owner ID:       {_v(c.get('owner_id',''))}")
    pause()

# ── Welcome Setup ─────────────────────────────

def _page_setup():
    while True:
        c = cfg()
        opts = [
            f"  Server ID        {_v(c.get('server_id',''))}",
            f"  Main Room ID     {_v(c.get('main_room_id',''))}",
            f"  Waiting Room ID  {c.get('waiting_room_id','') or f'{DIM}none (optional){RST}'}",
            f"  Status           {BLD}{c.get('status','online')}{RST}",
            f"  Owner ID         {_v(c.get('owner_id',''))}",
            f"  Token            {'set' if load_token() else f'{R}not set{RST}'}",
            "  Back",
        ]
        ch = select("Welcome Setup", opts)

        if ch == 0:
            _clr(); _header("Server ID")
            _print(f"  {DIM}The server where welcome messages will be sent.{RST}")
            v = ask_req("Server ID", c.get("server_id",""))
            c["server_id"] = v; save_cfg(c)

        elif ch == 1:
            _clr(); _header("Main Room ID")
            _print(f"  {DIM}The main voice room to send welcomes in.{RST}")
            v = ask_req("Main Room ID", c.get("main_room_id",""))
            c["main_room_id"] = v; save_cfg(c)

        elif ch == 2:
            _clr(); _header("Waiting Room ID")
            _print(f"  {DIM}Optional. Leave blank to disable waiting room.{RST}")
            v = ask("Waiting Room ID", c.get("waiting_room_id",""), optional=True)
            c["waiting_room_id"] = v; save_cfg(c)

        elif ch == 3:
            s = select("Status", [
                "  online  — normal welcome",
                "  dnd     — do not disturb",
                "  afk     — away from keyboard",
                "  custom4 — custom message",
            ])
            if s >= 0:
                c["status"] = ["online","dnd","afk","custom4"][s]
                save_cfg(c)

        elif ch == 4:
            _clr(); _header("Owner ID")
            _print(f"  {DIM}This user never gets a welcome message.{RST}")
            v = ask_req("Owner ID", c.get("owner_id",""))
            c["owner_id"] = v; save_cfg(c)

        elif ch == 5:
            _clr(); _header("Token")
            _print(f"  {Y}[!] Restart the bot after changing the token.{RST}")
            v = ask("Token")
            if v:
                write_token(v)
                _clr(); _print(f"\n  {G}[+]{RST} Token saved. Restart to apply.")
                pause()

        elif ch in (6, -1):
            return

# ── Messages ──────────────────────────────────

def _page_messages():
    while True:
        m   = msgs()
        sts = m.get("statuses", {})
        kws = m.get("afk_keywords", [])

        def pv(s): return _t(s, 28) if s else f"{DIM}(empty){RST}"

        opts = [
            f"  Online Message     {pv(sts.get('online',''))}",
            f"  DND Message        {pv(sts.get('dnd',''))}",
            f"  AFK Message        {pv(sts.get('afk',''))}",
            f"  Custom4 Message    {pv(sts.get('custom4',''))}",
            f"  AFK Auto-Reply     {pv(m.get('afk_auto_reply',''))}",
            f"  AFK Keywords       {len(kws)} keyword(s)",
            "  Back",
        ]
        ch = select("Messages", opts)

        if 0 <= ch <= 3:
            key = ["online","dnd","afk","custom4"][ch]
            _clr(); _header(f"{key.upper()} Message")
            _print(f"  {DIM}Use [mention] to place the user's ping.{RST}")
            v = ask_multiline("Message", sts.get(key,""), optional=(key=="custom4"))
            m["statuses"][key] = v; save_msgs(m)

        elif ch == 4:
            _clr(); _header("AFK Auto-Reply")
            v = ask_multiline("Message", m.get("afk_auto_reply",""))
            if v is not None: m["afk_auto_reply"] = v; save_msgs(m)

        elif ch == 5:
            _edit_keywords()

        elif ch in (6, -1):
            return

def _edit_keywords():
    while True:
        m   = msgs()
        kws = list(m.get("afk_keywords", []))
        opts = [f'  "{k}"' for k in kws] + ["  + Add", "  Clear All", "  Back"]
        add_i  = len(kws)
        clr_i  = len(kws) + 1
        back_i = len(kws) + 2

        ch = select(f"AFK Keywords  ({len(kws)})", opts)

        if ch == add_i:
            _clr(); _header("Add Keyword")
            v = ask("Keyword", optional=True)
            if v: kws.append(v); m["afk_keywords"] = kws; save_msgs(m)

        elif ch == clr_i:
            m["afk_keywords"] = []; save_msgs(m)

        elif ch in (back_i, -1):
            return

        elif 0 <= ch < len(kws):
            sub = select(f'"{kws[ch]}"', ["  Edit", "  Delete", "  Back"])
            if sub == 0:
                _clr(); _header("Edit Keyword")
                v = ask_req("Keyword", kws[ch])
                kws[ch] = v; m["afk_keywords"] = kws; save_msgs(m)
            elif sub == 1:
                kws.pop(ch); m["afk_keywords"] = kws; save_msgs(m)

# ── Test ──────────────────────────────────────

def _do_test():
    c     = cfg()
    m     = msgs()
    m_ch  = c.get("main_room_id",    "")
    w_ch  = c.get("waiting_room_id", "")
    rooms = [r for r in [m_ch, w_ch] if r]

    if not rooms:
        _clr(); _header("Test")
        _print(f"  {R}No rooms configured.{RST}\n  Go to Welcome Setup first.")
        pause(); return

    if not bot.is_ready() or not _bot_loop:
        _clr(); _header("Test")
        _print(f"  {R}Bot not connected yet.{RST}")
        pause(); return

    stat     = c.get("status", "online")
    sts      = m.get("statuses", {})
    txt      = (sts.get(stat) or sts.get("online","Welcome [mention]!")).replace(
        "[mention]", f"<@{c.get('owner_id','')}>")
    test_msg = f"**%test** — {txt}"

    _clr(); _header("Test — Sending")
    sent = 0
    for rid in rooms:
        ch = bot.get_channel(int(rid))
        if ch:
            fut = asyncio.run_coroutine_threadsafe(ch.send(test_msg), _bot_loop)
            try:
                fut.result(timeout=5); sent += 1
                _print(f"  {G}✓{RST} {rid}")
            except Exception as e:
                _print(f"  {R}✗{RST} {rid}: {e}")
        else:
            _print(f"  {R}✗{RST} Channel not found: {rid}")

    _print(f"\n  {G}[+]{RST} {sent}/{len(rooms)} room(s).")
    pause()

# ═══════════════════════════════════════════════
#   Entry Point
# ═══════════════════════════════════════════════

def main():
    ensure_dirs()
    reload_all()

    token = load_token()
    if not token:
        _clr()
        _print("""
  ╔════════════════════════════════════════╗
  ║      Shadow Guard — First Setup        ║
  ╚════════════════════════════════════════╝

  Enter your account token.
  (Saved to config/token.txt)
        """)
        _STDOUT.write("  Token: "); _STDOUT.flush()
        token = _readline()
        if not token:
            _print("  No token. Exiting."); sys.exit(1)
        write_token(token)
        _print("  [+] Saved.\n")

    t = threading.Thread(target=_run_bot, args=(token,), daemon=True)
    t.start()

    try:
        cli_main()
    except KeyboardInterrupt:
        _clr(); _print("\n  Goodbye!\n"); os._exit(0)


if __name__ == "__main__":
    main()
