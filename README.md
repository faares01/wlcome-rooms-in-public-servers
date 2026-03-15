# wlcome-rooms-in-public-servers 🛡️

A Discord selfbot that sends automatic welcome messages when someone joins a voice channel.

---

## Features

**Voice Welcome**
Sends a welcome message in the voice channel's text chat when a user joins.

- 4 status modes — each with its own custom message:
  - `online` — standard welcome
  - `dnd` — do not disturb message
  - `afk` — away message
  - `custom4` — fully custom
- Optional **waiting room** support — welcomes users in the waiting room without repeating when they move to the main room
- **5-minute cooldown** per user — prevents spam
- Owner is **never** welcomed
- **AFK auto-reply** — if someone mentions you or types a keyword while status is `afk`, the bot replies automatically

---

## Files

```
shadow_guard/
├── main.py                 ← bot + CLI in one file
├── requirements.txt
├── config/
│   ├── token.txt           ← your account token (never share this)
│   ├── settings.json       ← server/room IDs and status
│   └── messages.json       ← welcome messages and AFK keywords
└── data/
    ├── cooldowns.json      ← auto-managed
    └── bot.log             ← discord logs
```

---

## Setup

```bash
pip install -r requirements.txt
python main.py
```

On first run it will ask for your token. After that use the arrow-key CLI to configure everything.

---

## CLI Navigation

| Key | Action |
|-----|--------|
| `↑` `↓` | Navigate |
| `Enter` | Select |
| `Esc` | Go back |

**Menus:**
- **Welcome Setup** — set server ID, room IDs, status, owner ID, token
- **Messages** — edit each status message and AFK keywords
- **Test** — sends a `%test` message to your configured rooms
- **Status** — shows current config at a glance

---

## Discord Command

| Command | Description |
|---------|-------------|
| `%test` | Sends a test welcome to configured rooms (owner only) |

---

## Requirements

- Python 3.10+
- [`discord.py-self`](https://pypi.org/project/discord.py-self/)

---

> ⚠️ **This is a selfbot.** Using selfbots is against Discord's Terms of Service. Use at your own risk.
