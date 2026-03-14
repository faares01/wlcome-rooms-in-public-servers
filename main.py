#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════╗
║         حارس الظل لفارس — Shadow Guard Bot          ║
║         Discord Bot + CLI                            ║
╠══════════════════════════════════════════════════════╣
║  الملفات:                                            ║
║    config/token.txt        ← توكن البوت              ║
║    config/settings.json    ← الإعدادات والـ IDs       ║
║    config/messages.json    ← الرسائل والكلمات         ║
║    data/cooldowns.json     ← بيانات كولداون (تلقائي) ║
╚══════════════════════════════════════════════════════╝
"""

import discord
from discord.ext import commands
import asyncio
import json
import os
import sys
import time
import platform
from datetime import datetime
from pathlib import Path
from typing import Optional

# ═══════════════════════════════════════════════════════════
#   مسارات الملفات
# ═══════════════════════════════════════════════════════════

BASE_DIR      = Path(__file__).parent
CONFIG_DIR    = BASE_DIR / "config"
DATA_DIR      = BASE_DIR / "data"

SETTINGS_FILE  = CONFIG_DIR / "settings.json"
MESSAGES_FILE  = CONFIG_DIR / "messages.json"
TOKEN_FILE     = CONFIG_DIR / "token.txt"
COOLDOWNS_FILE = DATA_DIR   / "cooldowns.json"

# ═══════════════════════════════════════════════════════════
#   القيم الافتراضية
# ═══════════════════════════════════════════════════════════

DEFAULT_SETTINGS = {
    "bot_name":                "حارس الظل لفارس",
    "owner_id":                "1111705596543119370",
    "owner_names":             ["faa", "فارس", "faris"],
    "main_server_id":          "",
    "private_server_id":       "",
    "private_log_channel_id":  "",
    "blocked_voice_rooms":     [],
    "follow_target_id":        "1111705596543119370",
    "features": {
        "welcome":          False,
        "mention_monitor":  False,
        "surveillance":     False,
        "follow":           False
    },
    "welcome_config": {
        "server_id":        "",
        "main_room_id":     "",
        "waiting_room_id":  "",
        "status":           "online"
    },
    "surveillance_config": {
        "target_id":        "",
        "server_id":        "",
        "log_channel_id":   ""
    }
}

DEFAULT_MESSAGES = {
    "statuses": {
        "online":  "أهلاً وسهلاً [mention]! 👋 يسعدنا وجودك معنا!",
        "dnd":     "مرحباً [mention]! 🔴 فارس مشغول حالياً، لا تزعجوه.",
        "afk":     "أهلاً [mention]! 😴 فارس غائب مؤقتاً، سيعود قريباً!",
        "custom4": ""
    },
    "afk_auto_reply": "🌙 فارس غائب الآن، سيرد عليك حين يعود إن شاء الله!",
    "afk_keywords": [
        "وين فارس", "وينك فارس", "فارس وين", "اين فارس",
        "فارس فين", "where faris", "faris where", "فارس؟"
    ]
}

# ═══════════════════════════════════════════════════════════
#   دوال I/O
# ═══════════════════════════════════════════════════════════

def ensure_dirs():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

def _write_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_json(path: Path, default: dict) -> dict:
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    data = json.loads(json.dumps(default))   # نسخة عميقة
    _write_json(path, data)
    return data

def load_token() -> Optional[str]:
    try:
        if TOKEN_FILE.exists():
            t = TOKEN_FILE.read_text(encoding="utf-8").strip()
            return t or None
    except Exception:
        pass
    return None

def save_token(token: str):
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(token.strip(), encoding="utf-8")

# ═══════════════════════════════════════════════════════════
#   حالة التطبيق
# ═══════════════════════════════════════════════════════════

settings:         dict = {}
messages_cfg:     dict = {}
cooldowns:        dict = {}     # uid_str → timestamp
welcomed_waiting: dict = {}     # uid_str → set[ch_id_str]

def reload_all():
    global settings, messages_cfg, cooldowns
    settings     = load_json(SETTINGS_FILE,  DEFAULT_SETTINGS)
    messages_cfg = load_json(MESSAGES_FILE,  DEFAULT_MESSAGES)
    cooldowns    = load_json(COOLDOWNS_FILE, {})

def save_settings():    _write_json(SETTINGS_FILE,  settings)
def save_messages():    _write_json(MESSAGES_FILE,  messages_cfg)
def save_cooldowns():   _write_json(COOLDOWNS_FILE, cooldowns)

# ═══════════════════════════════════════════════════════════
#   مساعدات عامة
# ═══════════════════════════════════════════════════════════

def is_owner(uid) -> bool:
    return str(uid) == str(settings.get("owner_id", ""))

def on_cooldown(uid) -> bool:
    return (time.time() - cooldowns.get(str(uid), 0)) < 300   # 5 دقائق

def set_cd(uid):
    cooldowns[str(uid)] = time.time()
    save_cooldowns()

def welcome_msg(status: str, member: discord.Member) -> str:
    sts = messages_cfg.get("statuses", DEFAULT_MESSAGES["statuses"])
    msg = sts.get(status) or sts.get("online") or "أهلاً [mention]!"
    return msg.replace("[mention]", member.mention)

def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d  %I:%M %p")

# ═══════════════════════════════════════════════════════════
#   إنشاء البوت
# ═══════════════════════════════════════════════════════════

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="%", intents=intents, help_command=None)

# ═══════════════════════════════════════════════════════════
#   Events — الاتصال
# ═══════════════════════════════════════════════════════════

@bot.event
async def on_ready():
    reload_all()
    name = settings.get("bot_name", "حارس الظل لفارس")
    print(f"\n{'═'*56}")
    print(f"  🤖  {name}")
    print(f"  ✅  متصل:      {bot.user}  ({bot.user.id})")
    print(f"  📡  سيرفرات:   {len(bot.guilds)}")
    print(f"  🕐  الوقت:     {now_str()}")
    print(f"{'═'*56}")
    print("  اكتب  help  في CLI للأوامر المتاحة.\n")
    # محاولة تغيير اسم البوت
    try:
        if bot.user.name != name:
            await bot.user.edit(username=name)
    except Exception:
        pass

# ═══════════════════════════════════════════════════════════
#   ميزة 1 + 3 + 5 — Voice State
# ═══════════════════════════════════════════════════════════

@bot.event
async def on_voice_state_update(member: discord.Member,
                                before: discord.VoiceState,
                                after:  discord.VoiceState):
    reload_all()

    # ── ميزة 5: متابعة صوتية ─────────────────────────────
    if settings["features"].get("follow"):
        await _follow(member, before, after)

    # ── ميزة 3: مراقبة صوت ───────────────────────────────
    if settings["features"].get("surveillance"):
        await _surv_voice(member, before, after)

    # ── ميزة 1: ترحيب ────────────────────────────────────
    if not settings["features"].get("welcome"):
        return

    wc   = settings.get("welcome_config", {})
    s_id = str(wc.get("server_id",      ""))
    m_ch = str(wc.get("main_room_id",   ""))
    w_ch = str(wc.get("waiting_room_id",""))
    stat = wc.get("status", "online")

    if not s_id or str(member.guild.id) != s_id:
        return
    if is_owner(member.id):
        return
    if after.channel is None or before.channel == after.channel:
        return

    ch_id   = str(after.channel.id)
    is_main = ch_id == m_ch
    is_wait = bool(w_ch) and ch_id == w_ch

    if not (is_main or is_wait):
        return

    uid = str(member.id)

    if on_cooldown(uid):
        return

    # دخل الرئيسي بعد الانتظار → تخطَّ ومسح الذاكرة
    if is_main and uid in welcomed_waiting:
        welcomed_waiting.pop(uid, None)
        return

    # روم انتظار → لا تكرر للنفس الروم
    if is_wait:
        welcomed_waiting.setdefault(uid, set())
        if ch_id in welcomed_waiting[uid]:
            return
        welcomed_waiting[uid].add(ch_id)

    set_cd(uid)
    msg = welcome_msg(stat, member)
    try:
        await after.channel.send(msg)
    except Exception as e:
        print(f"  [!] خطأ ترحيب: {e}")

# ═══════════════════════════════════════════════════════════
#   ميزة 1 + 2 + 3 — Messages
# ═══════════════════════════════════════════════════════════

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    await bot.process_commands(message)
    reload_all()

    # ── ميزة 1: رد AFK التلقائي ───────────────────────────
    if settings["features"].get("welcome"):
        wc       = settings.get("welcome_config", {})
        stat     = wc.get("status", "online")
        m_ch     = str(wc.get("main_room_id",    ""))
        w_ch     = str(wc.get("waiting_room_id", ""))
        ch_id    = str(message.channel.id)
        owner_id = str(settings.get("owner_id", ""))
        in_room  = ch_id == m_ch or (bool(w_ch) and ch_id == w_ch)

        if stat == "afk" and in_room:
            cl  = message.content.lower()
            kws = messages_cfg.get("afk_keywords", DEFAULT_MESSAGES["afk_keywords"])
            owner_pinged = (f"<@{owner_id}>"  in message.content or
                            f"<@!{owner_id}>" in message.content)
            kw_hit = any(k.lower() in cl for k in kws)

            if owner_pinged or kw_hit:
                reply = messages_cfg.get("afk_auto_reply",
                                         DEFAULT_MESSAGES["afk_auto_reply"])
                try:
                    await message.reply(reply)
                except Exception:
                    try:
                        await message.channel.send(reply)
                    except Exception:
                        pass

    # ── ميزة 2: مراقبة المنشن ─────────────────────────────
    if settings["features"].get("mention_monitor") and message.guild:
        await _mention_monitor(message)

    # ── ميزة 3: مراقبة رسائل الشخص ───────────────────────
    if settings["features"].get("surveillance") and message.guild:
        await _surv_msg(message)


# ─── أمر %test في Discord (للمالك فقط) ───────────────────

@bot.command(name="test")
async def discord_test(ctx: commands.Context):
    """يرسل رسالة ترحيب تجريبية في الرومات المُعيَّنة"""
    if not is_owner(ctx.author.id):
        return   # تجاهل تام إذا ليس المالك

    reload_all()
    wc   = settings.get("welcome_config", {})
    m_ch = wc.get("main_room_id",    "")
    w_ch = wc.get("waiting_room_id", "")
    stat = wc.get("status", "online")
    sts  = messages_cfg.get("statuses", DEFAULT_MESSAGES["statuses"])
    msg  = (sts.get(stat) or sts.get("online", "مرحباً [mention]!")).replace(
        "[mention]", ctx.author.mention
    )
    rooms = [r for r in [m_ch, w_ch] if r]
    sent  = 0
    for rid in rooms:
        ch = bot.get_channel(int(rid))
        if ch:
            try:
                await ch.send(f"**%test** ← {msg}")
                sent += 1
            except Exception:
                pass
    try:
        await ctx.send(f"✅ أُرسلت رسالة الاختبار في {sent}/{len(rooms)} روم.",
                       delete_after=5)
    except Exception:
        pass

# ═══════════════════════════════════════════════════════════
#   ميزة 2: مراقبة المنشن
# ═══════════════════════════════════════════════════════════

async def _mention_monitor(message: discord.Message):
    owner_id  = str(settings.get("owner_id", ""))
    names     = settings.get("owner_names", [])
    mon_srv   = str(settings.get("main_server_id",          ""))
    log_ch_id = str(settings.get("private_log_channel_id",  ""))

    if not all([mon_srv, log_ch_id]):
        return
    if str(message.guild.id) != mon_srv:
        return
    if is_owner(message.author.id):
        return

    cl = message.content.lower()
    mentioned = (
        f"<@{owner_id}>"  in message.content or
        f"<@!{owner_id}>" in message.content or
        any(n.lower() in cl for n in names)
    )
    if not mentioned:
        return

    try:
        log_ch = bot.get_channel(int(log_ch_id))
        if not log_ch:
            return

        embed = discord.Embed(
            title="🔔 جاك منشن!",
            color=0xff6b35,
            timestamp=message.created_at
        )
        embed.add_field(name="👤 من",       value=message.author.mention,                     inline=True)
        embed.add_field(name="📍 في",       value=f"#{message.channel.name}",                  inline=True)
        embed.add_field(name="🏠 السيرفر",  value=message.guild.name,                          inline=True)
        embed.add_field(name="💬 الرسالة",  value=(message.content[:1000] or "—"),             inline=False)
        embed.add_field(name="🔗 رابط",     value=f"[اضغط هنا لفتح الرسالة]({message.jump_url})", inline=False)
        embed.add_field(name="🕐 الوقت",    value=now_str(),                                    inline=False)
        embed.set_footer(text=settings.get("bot_name", "حارس الظل"))

        await log_ch.send(embed=embed)
    except Exception as e:
        print(f"  [!] خطأ mention_monitor: {e}")

# ═══════════════════════════════════════════════════════════
#   ميزة 3: مراقبة شخص
# ═══════════════════════════════════════════════════════════

async def _surv_msg(message: discord.Message):
    sv  = settings.get("surveillance_config", {})
    tid = str(sv.get("target_id",      ""))
    sid = str(sv.get("server_id",      ""))
    lid = str(sv.get("log_channel_id", ""))

    if not all([tid, sid, lid]):
        return
    if str(message.author.id) != tid or str(message.guild.id) != sid:
        return

    try:
        log_ch = bot.get_channel(int(lid))
        if not log_ch:
            return

        embed = discord.Embed(
            title="👁️ مراقبة — رسالة جديدة",
            color=0x9b59b6,
            timestamp=message.created_at
        )
        embed.add_field(name="👤 المستخدم", value=f"{message.author} (`{message.author.id}`)",       inline=False)
        embed.add_field(name="📍 القناة",   value=f"#{message.channel.name} (`{message.channel.id}`)", inline=True)
        embed.add_field(name="🏠 السيرفر",  value=message.guild.name,                                  inline=True)
        embed.add_field(name="💬 الرسالة",  value=(message.content[:1024] or "—"),                    inline=False)
        if message.attachments:
            attach = "\n".join(a.url for a in message.attachments)
            embed.add_field(name="📎 مرفقات", value=attach[:1024], inline=False)
        embed.add_field(name="🔗 رابط",     value=f"[اضغط هنا]({message.jump_url})",                  inline=False)
        embed.add_field(name="🕐 الوقت",    value=now_str(),                                           inline=False)

        await log_ch.send(embed=embed)
    except Exception as e:
        print(f"  [!] خطأ surv_msg: {e}")


async def _surv_voice(member: discord.Member,
                      before: discord.VoiceState,
                      after:  discord.VoiceState):
    sv  = settings.get("surveillance_config", {})
    tid = str(sv.get("target_id",      ""))
    sid = str(sv.get("server_id",      ""))
    lid = str(sv.get("log_channel_id", ""))

    if not all([tid, sid, lid]):
        return
    if str(member.id) != tid or str(member.guild.id) != sid:
        return

    if   after.channel and not before.channel:
        action = f"🟢 دخل: **{after.channel.name}** (`{after.channel.id}`)"
    elif not after.channel and before.channel:
        action = f"🔴 خرج من: **{before.channel.name}**"
    elif after.channel and before.channel and after.channel != before.channel:
        action = f"🔀 انتقل: **{before.channel.name}** → **{after.channel.name}**"
    else:
        return

    try:
        log_ch = bot.get_channel(int(lid))
        if not log_ch:
            return
        embed = discord.Embed(title="👁️ مراقبة — حركة صوتية",
                              color=0xe74c3c, description=action)
        embed.add_field(name="👤 المستخدم", value=f"{member} (`{member.id}`)", inline=True)
        embed.add_field(name="🕐 الوقت",   value=now_str(),                    inline=True)
        await log_ch.send(embed=embed)
    except Exception as e:
        print(f"  [!] خطأ surv_voice: {e}")

# ═══════════════════════════════════════════════════════════
#   ميزة 5: متابعة صوتية
# ═══════════════════════════════════════════════════════════

async def _follow(member: discord.Member,
                  before: discord.VoiceState,
                  after:  discord.VoiceState):
    tid     = str(settings.get("follow_target_id", ""))
    blocked = [str(x) for x in settings.get("blocked_voice_rooms", [])]

    if not tid or str(member.id) != tid:
        return

    if after.channel is None:                      # غادر كل الرومات
        for vc in bot.voice_clients:
            if vc.guild == member.guild:
                try:
                    await vc.disconnect(force=True)
                except Exception:
                    pass
        return

    if str(after.channel.id) in blocked:           # روم محظور
        return

    try:
        vc = discord.utils.get(bot.voice_clients, guild=member.guild)
        if vc:
            await vc.move_to(after.channel)
        else:
            await after.channel.connect()
    except Exception as e:
        print(f"  [!] خطأ follow: {e}")

# ═══════════════════════════════════════════════════════════
#   واجهة CLI
# ═══════════════════════════════════════════════════════════

BANNER = """
  ╔══════════════════════════════════════════════════╗
  ║      حارس الظل لفارس — Shadow Guard CLI         ║
  ╚══════════════════════════════════════════════════╝"""

def clr():
    os.system("cls" if platform.system() == "Windows" else "clear")

def inp(prompt="") -> str:
    return input(prompt).strip()

def req(label: str, optional=False) -> str:
    while True:
        v = inp(f"  {label}: ")
        if v:
            return v
        if optional:
            return ""
        print("  ⚠  لا يمكن أن يكون فارغاً.")

def yn(prompt: str) -> bool:
    while True:
        r = inp(f"  {prompt} [y/n]: ").lower()
        if r in ("y", "yes", "ن", "نعم"):
            return True
        if r in ("n", "no", "لا"):
            return False

# ─── الحلقة الرئيسية للـ CLI ─────────────────────────────

async def cli_loop():
    await asyncio.sleep(1.5)    # انتظر اتصال البوت
    loop = asyncio.get_event_loop()

    while True:
        try:
            cmd = await loop.run_in_executor(
                None, lambda: input("\nShadow Guard ❯ ").strip()
            )
        except (EOFError, KeyboardInterrupt):
            print("\n  👋 وداعاً!")
            os._exit(0)

        if not cmd:
            continue

        parts = cmd.split()
        base  = parts[0].lower()

        if   base == "help":             _help()
        elif base == "status":           _status()
        elif base == "ids":              _ids()
        elif base == "token":            _cli_token()
        elif base == "name":             await _cli_name(parts)
        elif base == "reload":           reload_all(); print("  ✅ تم إعادة تحميل جميع الملفات.")
        elif base == "feature":          _cli_feature(parts)
        elif base == "welcome":          _cli_welcome()
        elif base == "setstatus":        _cli_setstatus(parts)
        elif base == "mention":          _cli_mention()
        elif base == "surveillance":     _cli_surveillance()
        elif base == "follow":           await _cli_follow()
        elif base == "messages":         _cli_messages()
        elif base == "test":             await _cli_test()
        elif base in ("exit","quit","خروج","q"):
            print("  👋 وداعاً!")
            os._exit(0)
        else:
            print(f"  ❌ أمر غير معروف: {cmd!r}  —  اكتب  help")

# ─── أوامر CLI ───────────────────────────────────────────

def _help():
    print("""
  ┌──────────────────────────────────────────────────────────┐
  │                    الأوامر المتاحة                        │
  ├─────────────────────────┬────────────────────────────────┤
  │  help                   │ عرض هذه القائمة                │
  │  status                 │ حالة البوت والميزات             │
  │  ids                    │ عرض جميع الـ IDs المحفوظة       │
  │  token                  │ تعيين/تغيير توكن البوت          │
  │  name <اسم جديد>        │ تغيير اسم البوت (فوري)         │
  │  reload                 │ إعادة تحميل جميع الملفات        │
  ├─────────────────────────┼────────────────────────────────┤
  │  feature welcome on/off │ تشغيل/إيقاف ترحيب روم         │
  │  feature mention on/off │ مراقبة المنشن                  │
  │  feature surveillance   │ مراقبة شخص                    │
  │  feature follow on/off  │ متابعة صوتية                  │
  ├─────────────────────────┼────────────────────────────────┤
  │  welcome                │ إعداد ميزة الترحيب             │
  │  setstatus <s>          │ تغيير الحالة (online/dnd/afk/4)│
  │  mention                │ إعداد مراقبة المنشن            │
  │  surveillance           │ إعداد مراقبة شخص              │
  │  follow                 │ إعداد المتابعة الصوتية         │
  │  messages               │ تعديل الرسائل والكلمات         │
  │  test                   │ إرسال رسالة اختبار             │
  │  exit                   │ إيقاف البوت                    │
  └─────────────────────────┴────────────────────────────────┘""")


def _status():
    reload_all()
    f  = settings.get("features", {})
    wc = settings.get("welcome_config", {})
    nm = settings.get("bot_name", "—")
    dc = f"{bot.user}  ({bot.user.id})" if bot.is_ready() else "❌ غير متصل"

    def st(key): return "✅ مفعّل" if f.get(key) else "❌ معطّل"

    print(f"""
  ┌─── حالة البوت ─────────────────────────────────────────
  │  الاسم:            {nm}
  │  Discord:          {dc}
  │  السيرفرات:        {len(bot.guilds) if bot.is_ready() else "—"}
  ├─── الميزات ────────────────────────────────────────────
  │  ترحيب روم:       {st('welcome')}  [الحالة: {wc.get('status','—')}]
  │  مراقبة منشن:     {st('mention_monitor')}
  │  مراقبة شخص:      {st('surveillance')}
  │  متابعة صوتية:    {st('follow')}
  └────────────────────────────────────────────────────────""")


def _ids():
    reload_all()
    wc = settings.get("welcome_config",      {})
    sv = settings.get("surveillance_config", {})
    bl = settings.get("blocked_voice_rooms", [])
    print(f"""
  ┌─── IDs المحفوظة ─────────────────────────────────────────
  │  [عام]
  │  owner_id:                  {settings.get('owner_id','—')}
  │  owner_names:               {', '.join(settings.get('owner_names',[]))}
  │  main_server_id:            {settings.get('main_server_id','—') or '(فارغ)'}
  │  private_server_id:         {settings.get('private_server_id','—') or '(فارغ)'}
  │  private_log_channel_id:    {settings.get('private_log_channel_id','—') or '(فارغ)'}
  │  follow_target_id:          {settings.get('follow_target_id','—')}
  │  blocked_voice_rooms:       {bl if bl else '(لا يوجد)'}
  ├─── [ترحيب روم] ─────────────────────────────────────────
  │  server_id:                 {wc.get('server_id','—') or '(فارغ)'}
  │  main_room_id:              {wc.get('main_room_id','—') or '(فارغ)'}
  │  waiting_room_id:           {wc.get('waiting_room_id','—') or '(لا يوجد)'}
  ├─── [مراقبة شخص] ────────────────────────────────────────
  │  target_id:                 {sv.get('target_id','—') or '(فارغ)'}
  │  server_id:                 {sv.get('server_id','—') or '(فارغ)'}
  │  log_channel_id:            {sv.get('log_channel_id','—') or '(فارغ)'}
  └──────────────────────────────────────────────────────────""")


def _cli_token():
    print("\n  ⚠  أدخل توكن البوت (سيُحفظ في config/token.txt):")
    token = inp("  Token: ")
    if token:
        save_token(token)
        print("  ✅ تم حفظ التوكن. أعد تشغيل البوت لتطبيقه.")
    else:
        print("  ❌ لم يُدخَل توكن.")


async def _cli_name(parts):
    if len(parts) < 2:
        print("  الاستخدام: name <الاسم الجديد>")
        return
    new_name = " ".join(parts[1:])
    settings["bot_name"] = new_name
    save_settings()
    if bot.is_ready():
        try:
            await bot.user.edit(username=new_name)
            print(f"  ✅ تم تغيير الاسم إلى: {new_name}")
        except discord.HTTPException as e:
            print(f"  ⚠  Discord يحدّ تغيير الاسم (مرة كل ساعة): {e}")
    else:
        print(f"  ✅ تم حفظ الاسم: {new_name}  (سيُطبَّق عند الاتصال)")


def _cli_feature(parts):
    map_ = {
        "welcome":      "welcome",
        "mention":      "mention_monitor",
        "surveillance": "surveillance",
        "follow":       "follow"
    }
    if len(parts) < 3:
        print("  الاستخدام: feature <welcome|mention|surveillance|follow> <on|off>")
        return
    feat = parts[1].lower()
    val  = parts[2].lower() in ("on", "1", "true", "نعم", "y")
    key  = map_.get(feat)
    if not key:
        print(f"  ❌ ميزة غير معروفة: {feat}")
        return
    settings.setdefault("features", {})[key] = val
    save_settings()
    print(f"  {'✅ مفعّلة' if val else '❌ معطّلة'}: {feat}")


def _cli_welcome():
    print("\n  ── إعداد ترحيب روم ──────────────────────────────")
    print("  ⚠  تأكد أن البوت موجود في السيرفر ولديه صلاحية إرسال رسائل.")
    srv  = req("ID السيرفر")
    room = req("ID الروم الرئيسي")
    wait = inp("  ID روم الانتظار (اختياري — Enter للتخطي): ")
    print("  الحالات: online / dnd / afk / custom4")
    stat = inp("  الحالة الافتراضية [online]: ") or "online"
    settings.setdefault("welcome_config", {}).update({
        "server_id":       srv,
        "main_room_id":    room,
        "waiting_room_id": wait,
        "status":          stat
    })
    save_settings()
    print("  ✅ تم حفظ إعداد الترحيب.")


def _cli_setstatus(parts):
    valid = {"online", "dnd", "afk", "custom4"}
    if len(parts) < 2:
        print("  الاستخدام: setstatus <online|dnd|afk|custom4>")
        print("  📌 يمكنك تغيير الحالة في أي وقت — حتى لو الميزة تعمل الآن.")
        return
    s = parts[1].lower()
    if s not in valid:
        print(f"  ❌ غير صالح. المتاح: {', '.join(valid)}")
        return
    settings.setdefault("welcome_config", {})["status"] = s
    save_settings()
    print(f"  ✅ الحالة الآن: {s}")


def _cli_mention():
    print("\n  ── إعداد مراقبة المنشن ─────────────────────────")
    print("  ⚠  تأكد أن البوت موجود في كلا السيرفرين!")
    ms = req("ID السيرفر الرئيسي (المراقَب)")
    ps = req("ID السيرفر الخاص للبوت")
    lc = req("ID قناة الإشعارات في السيرفر الخاص")
    settings["main_server_id"]           = ms
    settings["private_server_id"]        = ps
    settings["private_log_channel_id"]   = lc
    save_settings()
    print("  ✅ تم حفظ إعداد مراقبة المنشن.")


def _cli_surveillance():
    print("\n  ── إعداد مراقبة شخص ──────────────────────────")
    tid = req("ID الشخص المراقَب")
    sid = req("ID السيرفر المراقَب")
    lid = req("ID قناة إرسال التحديثات")
    settings.setdefault("surveillance_config", {}).update({
        "target_id":      tid,
        "server_id":      sid,
        "log_channel_id": lid
    })
    save_settings()
    print("  ✅ تم حفظ إعداد المراقبة.")


async def _cli_follow():
    print("\n  ── إعداد المتابعة الصوتية ──────────────────────")
    tid = req("ID الشخص المتابَع")
    settings["follow_target_id"] = tid

    bl = settings.get("blocked_voice_rooms", [])
    print(f"  الرومات المحظورة الحالية: {bl if bl else '(لا يوجد)'}")

    if yn("تعديل الرومات المحظورة؟"):
        new_b = []
        print("  أدخل IDs الرومات المحظورة (Enter فارغ للانتهاء):")
        while True:
            b = inp("  ID روم محظور (أو Enter للإنهاء): ")
            if not b:
                break
            new_b.append(b)
        settings["blocked_voice_rooms"] = new_b

    save_settings()
    print("  ✅ تم حفظ إعداد المتابعة.")

    # إذا الميزة مفعّلة → انضم فوراً للهدف إن كان في روم
    if settings["features"].get("follow") and bot.is_ready():
        target_id = int(tid)
        blocked   = [str(x) for x in settings.get("blocked_voice_rooms", [])]
        for guild in bot.guilds:
            m = guild.get_member(target_id)
            if m and m.voice and m.voice.channel:
                if str(m.voice.channel.id) not in blocked:
                    try:
                        vc = discord.utils.get(bot.voice_clients, guild=guild)
                        if vc:
                            await vc.move_to(m.voice.channel)
                        else:
                            await m.voice.channel.connect()
                        print(f"  🎙️ انضم البوت إلى: {m.voice.channel.name}")
                    except Exception as e:
                        print(f"  [!] فشل الانضمام: {e}")
                break


def _cli_messages():
    print("""
  ── تعديل الرسائل ──────────────────────────────────
  1  رسائل الترحيب (حسب كل حالة)
  2  رسالة رد AFK التلقائي
  3  كلمات AFK المفتاحية
  4  أسماء المالك (لمراقبة المنشن)
  0  رجوع""")
    ch = inp("  اختيارك: ")

    if ch == "1":
        print("\n  استخدم [mention] لتحديد مكان منشن الشخص في الرسالة.")
        labels = [
            ("online",  "اونلاين"),
            ("dnd",     "عدم الازعاج (DND)"),
            ("afk",     "AFK"),
            ("custom4", "مخصص 4")
        ]
        msgs = messages_cfg.setdefault("statuses", {})
        for key, label in labels:
            cur = msgs.get(key, "")
            print(f"\n  [{label}]  الحالية: {cur or '(فارغة)'}")
            new = inp(f"  الجديدة (Enter للإبقاء): ")
            if new:
                msgs[key] = new
        save_messages()
        print("  ✅ تم حفظ رسائل الترحيب.")

    elif ch == "2":
        cur = messages_cfg.get("afk_auto_reply", "")
        print(f"  الحالية: {cur}")
        new = inp("  الجديدة (Enter للإبقاء): ")
        if new:
            messages_cfg["afk_auto_reply"] = new
            save_messages()
            print("  ✅ تم الحفظ.")

    elif ch == "3":
        kws = messages_cfg.get("afk_keywords", [])
        print("  الكلمات الحالية:")
        for i, k in enumerate(kws, 1):
            print(f"    {i}. {k}")
        print("  أدخل الكلمات الجديدة (Enter فارغ للانتهاء):")
        new_kws = []
        while True:
            k = inp("  كلمة: ")
            if not k:
                break
            new_kws.append(k)
        if new_kws:
            messages_cfg["afk_keywords"] = new_kws
            save_messages()
            print("  ✅ تم حفظ الكلمات.")

    elif ch == "4":
        names = settings.get("owner_names", [])
        print(f"  الأسماء الحالية: {', '.join(names)}")
        print("  أدخل الأسماء الجديدة (Enter فارغ للانتهاء):")
        new_names = []
        while True:
            n = inp("  اسم: ")
            if not n:
                break
            new_names.append(n)
        if new_names:
            settings["owner_names"] = new_names
            save_settings()
            print("  ✅ تم حفظ الأسماء.")


async def _cli_test():
    reload_all()
    wc   = settings.get("welcome_config", {})
    m_ch = wc.get("main_room_id",    "")
    w_ch = wc.get("waiting_room_id", "")
    stat = wc.get("status", "online")

    rooms = [r for r in [m_ch, w_ch] if r]
    if not rooms:
        print("  ⚠  لم يُعيَّن أي روم. أعد إعداد الترحيب أولاً.")
        return

    print("  الرومات التي سيُرسَل فيها:")
    for r in rooms:
        print(f"    • {r}")
    if not yn("إرسال رسالة %test الآن؟"):
        return

    if not bot.is_ready():
        print("  ❌ البوت غير متصل بعد.")
        return

    sts     = messages_cfg.get("statuses", DEFAULT_MESSAGES["statuses"])
    msg_tpl = sts.get(stat) or sts.get("online", "مرحباً [mention]!")
    msg     = msg_tpl.replace("[mention]", f"<@{settings.get('owner_id','')}>")
    test_msg = f"**%test** — {msg}"

    sent = 0
    for rid in rooms:
        ch = bot.get_channel(int(rid))
        if ch:
            try:
                await ch.send(test_msg)
                sent += 1
            except Exception as e:
                print(f"  ❌ فشل في {rid}: {e}")
        else:
            print(f"  ⚠  لم يُعثَر على الروم: {rid}")
    print(f"  ✅ أُرسلت في {sent}/{len(rooms)} روم.")

# ═══════════════════════════════════════════════════════════
#   نقطة الدخول
# ═══════════════════════════════════════════════════════════

async def main():
    ensure_dirs()
    reload_all()

    token = load_token()
    if not token:
        clr()
        print(BANNER)
        print("\n  ⚠  لا يوجد توكن مُحفوظ.")
        print("  أدخل توكن البوت (سيُحفظ في config/token.txt):")
        token = input("  Token: ").strip()
        if not token:
            print("  ❌ لا يمكن التشغيل بدون توكن.")
            sys.exit(1)
        save_token(token)
        print("  ✅ تم حفظ التوكن.\n")

    async with bot:
        asyncio.ensure_future(cli_loop())
        await bot.start(token)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n  👋 وداعاً!")
    except discord.LoginFailure:
        print("\n  ❌ توكن غير صالح! استخدم أمر  token  في CLI لتغييره.")
        sys.exit(1)
    except Exception as e:
        print(f"\n  ❌ خطأ غير متوقع: {e}")
        sys.exit(1)
