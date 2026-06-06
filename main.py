#!/usr/bin/env python3
"""
Escrower Bot — Genuine Edition v5
- Form triggered in GROUP → private group auto-created for buyer+seller+bot
- Bot is admin of private group, userbot leaves after setup
- ALL deal flow (agree/cancel/pay/dispute) happens inside private group
- Seller name fixed, Terms rendered properly
- Buyer can only agree as buyer, Seller only as seller
"""

import os, io, re, sqlite3, logging, asyncio, random, hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from PIL import Image, ImageDraw, ImageFont
import aiohttp
from aiohttp import web

try:
    from telethon import TelegramClient
    from telethon.tl.functions.channels import (
        CreateChannelRequest, InviteToChannelRequest,
        DeleteChannelRequest, EditAdminRequest,
    )
    from telethon.tl.functions.messages import ExportChatInviteRequest
    from telethon.tl.types import ChatAdminRights
    from telethon.errors import (
        UserNotMutualContactError, UserPrivacyRestrictedError, FloodWaitError,
    )
    TELETHON_OK = True
except ImportError:
    TELETHON_OK = False

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    InputFile, ChatPermissions, BotCommand,
)
from telegram.ext import (
    ApplicationBuilder, ContextTypes, CommandHandler,
    MessageHandler, CallbackQueryHandler, filters,
)
# Plugin system — loads everything from plugins/ folder
from plugin_loader import load_all as _load_plugins

# ══════════════════════════════════════════
#  CONFIG  —  loaded from config/settings.py
#  To change ANYTHING: edit config/settings.py
#  Never modify main.py for config changes
# ══════════════════════════════════════════
from config.settings import (
    BOT_TOKEN, ADMIN_IDS, LOG_CHANNEL, UPI_ID, QR_PATH,
    ADMIN_PASSWORD, DB_PATH, RENDER_URL, PORT, BOT_NAME,
    ESCROW_FEE_PCT, TG_API_ID, TG_API_HASH, TELETHON_SESSION,
    USERBOT_ENABLED as _UB_CFG, GROUP_AUTO_DELETE_DELAY,
    DEAL_ID_MIN, DEAL_ID_MAX, PING_INTERVAL,
    TX_PATTERNS, AMOUNT_PATTERNS, THEMES,
    FEATURE_OCR, MIN_DEAL_AMOUNT, MAX_DEAL_AMOUNT,
)
USERBOT_ENABLED = TELETHON_OK and _UB_CFG

logging.basicConfig(format="%(asctime)s | %(levelname)-8s | %(message)s", level=logging.INFO)
log = logging.getLogger("Escrower")

userbot: Any = None
BOT_ID: int       = 0   # filled in main()
BOT_USERNAME: str = ""   # filled in main()

# ══════════════════════════════════════════
#  DATABASE
# ══════════════════════════════════════════
# ══════════════════════════════════════════
#  DATABASE — Turso (cloud) + SQLite fallback
#  Turso = free cloud SQLite, survives restarts
#  Set TURSO_URL + TURSO_TOKEN in Render env vars
#  If not set, falls back to local SQLite (data lost on restart)
# ══════════════════════════════════════════

TURSO_URL   = os.getenv("TURSO_URL",   "")   # libsql://your-db.turso.io
TURSO_TOKEN = os.getenv("TURSO_TOKEN", "")   # your turso auth token

_DB_CONN = None   # the single live connection

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    uid INTEGER PRIMARY KEY,
    username TEXT, full_name TEXT,
    joined TEXT, last_seen TEXT,
    deal_count INTEGER DEFAULT 0,
    rating REAL DEFAULT 5.0,
    referred_by INTEGER,
    referral_code TEXT UNIQUE,
    invite_count INTEGER DEFAULT 0,
    fee_discount REAL DEFAULT 0.0,
    is_banned INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS escrows (
    id INTEGER PRIMARY KEY,
    origin_chat INTEGER,
    private_gid INTEGER,
    private_raw_id INTEGER,
    invite_link TEXT,
    seller_id INTEGER, seller_name TEXT,
    buyer_id INTEGER,  buyer_name TEXT,
    item TEXT, amount TEXT, mode TEXT DEFAULT 'UPI',
    valid_till TEXT, terms TEXT,
    status TEXT DEFAULT 'PENDING',
    seller_agreed INTEGER DEFAULT 0,
    buyer_agreed INTEGER DEFAULT 0,
    created_at TEXT, agreed_at TEXT,
    paid_at TEXT, money_held_at TEXT,
    deal_done_at TEXT, seller_upi TEXT,
    payout_proof TEXT, closed_at TEXT, cancelled_at TEXT,
    tx_id TEXT, tx_amount TEXT,
    dispute_at TEXT, dispute_by INTEGER,
    admin_added INTEGER DEFAULT 0,
    fee_pct REAL DEFAULT 2.5,
    posted_msg_id INTEGER,
    private_msg_id INTEGER
);
CREATE TABLE IF NOT EXISTS warnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER, user_id INTEGER,
    warned_by INTEGER, reason TEXT, ts TEXT
);
CREATE TABLE IF NOT EXISTS disputes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    escrow_id INTEGER, raised_by INTEGER,
    reason TEXT, status TEXT DEFAULT 'OPEN',
    resolved_by INTEGER, resolution TEXT, ts TEXT
);
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT, event TEXT, detail TEXT
);
"""


def init_db():
    global _DB_CONN
    if TURSO_URL and TURSO_TOKEN:
        try:
            import libsql_experimental as libsql
            conn = libsql.connect(
                database=TURSO_URL,
                auth_token=TURSO_TOKEN,
            )
            conn.executescript(SCHEMA)
            conn.commit()
            _DB_CONN = conn
            log.info("✅ Connected to Turso cloud database: %s", TURSO_URL)
            return conn
        except ImportError:
            log.error("❌ libsql_experimental not installed. Run: pip install libsql-experimental")
        except Exception as e:
            log.error("❌ Turso connection failed: %s — falling back to SQLite", e)

    # Fallback: local SQLite
    path = DB_PATH
    log.warning("⚠️  Using LOCAL SQLite (%s). Set TURSO_URL+TURSO_TOKEN for persistence!", path)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript(SCHEMA)
    conn.commit()
    _DB_CONN = conn
    return conn


def _conn():
    """Return live DB connection, reconnecting if needed."""
    global _DB_CONN
    if _DB_CONN is None:
        init_db()
    return _DB_CONN


DB = init_db()


def dbc(sql, p=()):
    c = _conn().cursor(); c.execute(sql, p); _conn().commit(); return c

def row(sql, p=()):
    c = _conn().cursor(); c.execute(sql, p); r = c.fetchone()
    if not r: return None
    return dict(zip([d[0] for d in c.description], r))

def rows(sql, p=()):
    c = _conn().cursor(); c.execute(sql, p)
    cols = [d[0] for d in c.description]
    return [dict(zip(cols, r)) for r in c.fetchall()]

def upsert_user(u):
    now  = datetime.utcnow().isoformat()
    code = hashlib.md5(f"{u.id}{u.full_name}".encode()).hexdigest()[:10].upper()
    if row("SELECT uid FROM users WHERE uid=?", (u.id,)):
        dbc("UPDATE users SET username=?,full_name=?,last_seen=? WHERE uid=?",
            (u.username, u.full_name, now, u.id))
    else:
        dbc("INSERT INTO users(uid,username,full_name,joined,last_seen,referral_code) VALUES(?,?,?,?,?,?)",
            (u.id, u.username, u.full_name, now, now, code))

def get_user(uid):    return row("SELECT * FROM users WHERE uid=?", (uid,))
def get_escrow(eid):  return row("SELECT * FROM escrows WHERE id=?", (eid,))
def dblog(ev, det=""): dbc("INSERT INTO logs(ts,event,detail) VALUES(?,?,?)",
                           (datetime.utcnow().isoformat(), ev, det))

QR_BYTES = None
if os.path.exists(QR_PATH):
    with open(QR_PATH, "rb") as f: QR_BYTES = f.read()

AUTHED      = set()
PENDING     = {}   # uid → partial escrow data while filling form
RATE_Q      = {}   # uid → {eid, rated_id}
SELLER_UPI  = {}   # uid → eid (waiting for seller to send UPI ID)
PAYOUT_WAIT = {}   # eid → True (waiting for admin payout screenshot)

# ══════════════════════════════════════════
#  VISUALS
# ══════════════════════════════════════════
# THEMES loaded from config/settings.py

def _font(size, bold=False):
    names = (["DejaVuSans-Bold.ttf","arialbd.ttf","LiberationSans-Bold.ttf"]
             if bold else
             ["DejaVuSans.ttf","arial.ttf","LiberationSans-Regular.ttf"])
    for n in names:
        try: return ImageFont.truetype(n, size)
        except: pass
    return ImageFont.load_default()

def _rrect(draw, xy, r, fill):
    x0,y0,x1,y1 = xy
    draw.rectangle([x0+r,y0,x1-r,y1],fill=fill)
    draw.rectangle([x0,y0+r,x1,y1-r],fill=fill)
    for cx,cy in [(x0+r,y0+r),(x1-r,y0+r),(x0+r,y1-r),(x1-r,y1-r)]:
        draw.ellipse([cx-r,cy-r,cx+r,cy+r],fill=fill)

def make_welcome_img(name: str) -> bytes:
    W,H=1000,400; t=random.choice(THEMES)
    im=Image.new("RGB",(W,H),t["bg"]); d=ImageDraw.Draw(im)
    for x in range(0,W,55): d.line([(x,0),(x,H)],fill=(*t["b"],15))
    for y in range(0,H,55): d.line([(0,y),(W,y)],fill=(*t["b"],15))
    d.rectangle([0,0,W,5],fill=t["a"]); d.rectangle([0,H-5,W,H],fill=t["a"])
    f1=_font(48,True); f2=_font(26,True); f3=_font(19); f4=_font(15)
    d.text((50,30),"🔐  "+BOT_NAME,font=f2,fill=t["a"])
    d.text((50,80),f"Welcome, {name[:22]}!",font=f1,fill=(255,255,255))
    d.rectangle([50,148,340,151],fill=t["a"])
    d.text((50,162),"End-to-End Encrypted Private Deals",font=f3,fill=(200,220,255))
    d.text((50,196),"Private • Secure • Verified",font=f3,fill=(160,190,230))
    d.text((50,240),"Every deal gets its own private group — buyer & seller only.",font=f4,fill=(130,160,200))
    d.text((50,264),"Group is auto-deleted after the deal closes.",font=f4,fill=(130,160,200))
    d.text((50,320),"Type /form in a group to start a deal",font=f4,fill=(100,130,170))
    buf=io.BytesIO(); im.save(buf,"PNG"); buf.seek(0); return buf.read()

def make_deal_img(eid, seller, buyer, amount, status, mode) -> bytes:
    W,H=1000,420; t=THEMES[eid%len(THEMES)]
    im=Image.new("RGB",(W,H),t["bg"]); d=ImageDraw.Draw(im)
    for x in range(0,W,55): d.line([(x,0),(x,H)],fill=(*t["b"],12))
    d.rectangle([0,0,W,6],fill=t["a"])
    fb=_font(20,True); f1=_font(28,True); f2=_font(19); f3=_font(15)
    SC={"PENDING":(255,200,0),"AGREED":(100,255,150),"QR_SENT":(80,200,255),
        "PAID":(255,160,80),"CLOSED":(80,255,160),"CANCELLED":(255,80,80),"DISPUTE":(255,120,0)}
    sc=SC.get(status,(200,200,200))
    d.text((40,18),f"🔐  Deal #{eid}  —  {BOT_NAME}",font=fb,fill=t["a"])
    sw=int(d.textlength(f"● {status}",font=fb))+20
    _rrect(d,(W-sw-50,13,W-30,43),8,(*sc,40)); d.text((W-sw-40,16),f"● {status}",font=fb,fill=sc)
    d.rectangle([40,55,W-40,58],fill=(*t["a"],60))
    d.text((40,68),"💼  SELLER",font=f3,fill=(*t["a"],160))
    d.text((40,88),str(seller)[:35],font=f1,fill=(255,255,255))
    d.text((W//2+20,68),"🛒  BUYER",font=f3,fill=(*t["a"],160))
    d.text((W//2+20,88),str(buyer)[:35],font=f1,fill=(255,255,255))
    d.rectangle([40,140,W-40,142],fill=(*t["a"],40))
    cw=(W-80)//3
    for i,(l,v) in enumerate([("💰 AMOUNT",amount),("💳 MODE",mode),(f"🔖 DEAL ID",f"#{eid}")]):
        x=40+i*cw; d.text((x,152),l,font=f3,fill=(*t["a"],150)); d.text((x,170),str(v)[:22],font=f2,fill=(255,255,255))
    d.rectangle([40,210,W-40,212],fill=(*t["a"],30))
    d.text((40,222),"🔒 End-to-end encrypted  •  Private group  •  Auto-deleted on close",font=f3,fill=(120,150,190))
    d.text((40,248),"⚠️ Escrow fee is non-refundable even if deal is cancelled.",font=f3,fill=(255,160,80))
    d.rectangle([0,H-6,W,H],fill=t["a"])
    buf=io.BytesIO(); im.save(buf,"PNG"); buf.seek(0); return buf.read()

# ══════════════════════════════════════════
#  USERBOT — Telethon
# ══════════════════════════════════════════
async def ub_create_group(eid, seller_id, buyer_id, bot_username):
    """
    Create private supergroup.
    Order:
      1. Create group (userbot is owner)
      2. Add bot by @username → make it admin
      3. Add seller
      4. Add buyer (if possible)
      5. Generate invite link
      6. Userbot leaves — only bot + seller + buyer remain
    """
    global userbot
    if not userbot: return {"ok": False, "error": "Userbot not running"}

    title = f"🔐 Escrow #{eid} | Private Deal"
    try:
        res = await userbot(CreateChannelRequest(
            title=title,
            about=f"Private escrow deal #{eid}. Auto-deleted on close.",
            megagroup=True,
        ))
        ch = res.chats[0]; raw_id = ch.id
        bot_gid = int(f"-100{raw_id}")
        log.info("Created group '%s' raw=%s bot_gid=%s", title, raw_id, bot_gid)
    except Exception as e:
        return {"ok": False, "error": str(e)}

    errs = []

    # ── STEP 1: Add bot by @username and make it admin ──
    # Bots can be resolved by username even without being a contact
    bot_added = False
    try:
        bot_ent = await userbot.get_entity(bot_username)
        await userbot(InviteToChannelRequest(ch, [bot_ent]))
        await asyncio.sleep(1)  # small delay before promoting
        await userbot(EditAdminRequest(
            channel=ch,
            user_id=bot_ent,
            admin_rights=ChatAdminRights(
                change_info=True,
                post_messages=True,
                edit_messages=True,
                delete_messages=True,
                ban_users=True,
                invite_users=True,
                pin_messages=True,
                add_admins=False,
                manage_call=False,
            ),
            rank="Escrow Bot"
        ))
        bot_added = True
        log.info("✅ Bot @%s added as admin to group %s", bot_username, raw_id)
    except Exception as e:
        errs.append(f"bot_admin: {e}")
        log.error("❌ Could not add bot as admin: %s", e)

    # ── STEP 2: Add seller and buyer ─────────────────────
    for uid, role in [(seller_id, "seller"), (buyer_id, "buyer")]:
        if not uid: continue
        try:
            ent = await userbot.get_entity(uid)
            await userbot(InviteToChannelRequest(ch, [ent]))
            log.info("✅ Invited %s uid=%s", role, uid)
        except (UserNotMutualContactError, UserPrivacyRestrictedError):
            errs.append(f"{role}({uid}): privacy restricted — share link manually")
            log.warning("Privacy restricted: %s %s", role, uid)
        except FloodWaitError as e:
            log.warning("FloodWait %ss for %s", e.seconds, role)
            await asyncio.sleep(e.seconds)
            try:
                ent = await userbot.get_entity(uid)
                await userbot(InviteToChannelRequest(ch, [ent]))
            except Exception as e2:
                errs.append(f"{role}: {e2}")
        except Exception as e:
            errs.append(f"{role}: {e}")
            log.warning("Could not invite %s %s: %s", role, uid, e)

    # ── STEP 3: Generate invite link ─────────────────────
    inv_link = None
    try:
        inv = await userbot(ExportChatInviteRequest(ch))
        inv_link = inv.link
        log.info("Invite link: %s", inv_link)
    except Exception as e:
        log.warning("Invite link failed: %s", e)

    # ── STEP 4: Userbot leaves ────────────────────────────
    # Only do this if bot was successfully added, otherwise no one manages the group
    if bot_added:
        try:
            await asyncio.sleep(2)  # ensure bot is fully settled as admin
            await userbot.delete_dialog(ch)
            log.info("✅ Userbot left group %s — bot is now in charge", raw_id)
        except Exception as e:
            log.warning("Userbot leave failed: %s", e)
    else:
        log.error("❌ Bot not added as admin — userbot staying in group as fallback")
        errs.append("bot_not_added: userbot remained as fallback admin")

    return {
        "ok":       True,
        "raw_id":   raw_id,
        "gid":      bot_gid,
        "link":     inv_link,
        "errors":   errs,
        "bot_added": bot_added,
    }


async def ub_delete_group(raw_id):
    global userbot
    if not userbot or not raw_id: return
    try:
        ch = await userbot.get_entity(raw_id)
        await userbot(DeleteChannelRequest(ch))
        log.info("Deleted group raw_id=%s", raw_id)
    except Exception as e: log.warning("Delete group %s: %s", raw_id, e)


async def ub_add_user(raw_id, uid):
    global userbot
    if not userbot: return False
    try:
        ch  = await userbot.get_entity(raw_id)
        ent = await userbot.get_entity(uid)
        await userbot(InviteToChannelRequest(ch, [ent]))
        return True
    except Exception as e:
        log.warning("Add user %s to %s: %s", uid, raw_id, e); return False

# ══════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════
async def is_admin(update: Update, ctx) -> bool:
    uid = update.effective_user.id
    if uid in ADMIN_IDS or uid in AUTHED: return True
    try:
        m = await update.effective_chat.get_member(uid)
        return m.status in ("administrator", "creator")
    except: return False

async def safe_log(ctx, text):
    if LOG_CHANNEL:
        try: await ctx.bot.send_message(LOG_CHANNEL, text[:4000])
        except: pass

def _se(s):
    return {"PENDING":"🕐","AGREED":"🤝","QR_SENT":"💳","PAID":"💰",
            "CLOSED":"✅","CANCELLED":"❌","DISPUTE":"⚠️"}.get(s,"•")

def _fee_str(e):
    try:
        amt = float(re.sub(r"[^\d.]", "", str(e.get("amount","0") or "0")))
        fee = round(amt * float(e.get("fee_pct", ESCROW_FEE_PCT)) / 100, 2)
        return f"₹{fee}"
    except: return "—"

def _escrow_caption(e, show_agree=True):
    sa = "✅ Agreed" if e.get("seller_agreed") else "⏳ Waiting"
    ba = "✅ Agreed" if e.get("buyer_agreed")  else "⏳ Waiting"
    st = _se(e.get("status","")) + " " + (e.get("status") or "")
    terms = (e.get("terms") or "Standard escrow terms apply.")[:300]
    lines = [
        f"🔐 <b>Escrow Deal #{e['id']}</b>",
        "",
        f"💼 <b>Seller</b>    :  {e.get('seller_name') or '—'}",
        f"🛒 <b>Buyer</b>     :  {e.get('buyer_name') or '—'}",
        "",
        f"📦 <b>Item</b>      :  {e.get('item') or '—'}",
        f"💰 <b>Amount</b>    :  {e.get('amount') or '—'}",
        f"💳 <b>Mode</b>      :  {e.get('mode') or 'UPI'}",
        f"📅 <b>Valid Till</b> :  {e.get('valid_till') or '—'}",
        f"🏷️ <b>Escrow Fee</b> :  {_fee_str(e)}  ({e.get('fee_pct', ESCROW_FEE_PCT)}%)",
        "",
        f"📊 <b>Status</b>    :  {st}",
    ]
    if show_agree:
        lines += ["",
                  f"👤 Seller : {sa}",
                  f"🛒 Buyer  : {ba}"]
    lines += ["",
              f"📜 <b>Terms</b>  :  {terms}",
              "",
              "🔒 <i>End-to-end encrypted  •  Private group  •  Auto-deleted on close</i>",
              "⚠️ <i>Escrow fee is non-refundable even if cancelled.</i>"]
    return "\n".join(lines)

def _deal_kb(eid, e):
    """Buttons shown in origin group BEFORE private group is created."""
    sa = e.get("seller_agreed"); ba = e.get("buyer_agreed")
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{'✅' if sa else '🤝'} I'm Seller — AGREE",  callback_data=f"ag|s|{eid}"),
         InlineKeyboardButton(f"{'✅' if ba else '🤝'} I'm Buyer — AGREE",   callback_data=f"ag|b|{eid}")],
        [InlineKeyboardButton("❌ Seller CANCEL", callback_data=f"ca|s|{eid}"),
         InlineKeyboardButton("❌ Buyer CANCEL",  callback_data=f"ca|b|{eid}")],
        [InlineKeyboardButton("🔄 Refresh",       callback_data=f"ref|{eid}"),
         InlineKeyboardButton("ℹ️ Deal Info",     callback_data=f"inf|{eid}")],
    ])

def _private_kb(eid, admin_added=False):
    """Buttons shown INSIDE the private deal group."""
    add_btn = (InlineKeyboardButton("✅ Admin Added as Mediator", callback_data="noop")
               if admin_added else
               InlineKeyboardButton("👮 Add Admin as Mediator",   callback_data=f"addadmin|{eid}"))
    return InlineKeyboardMarkup([
        [add_btn],
        [InlineKeyboardButton("⚠️ Raise Dispute",   callback_data=f"dispute|{eid}"),
         InlineKeyboardButton("✅ Mark as Paid",     callback_data=f"markpaid|{eid}")],
        [InlineKeyboardButton("📞 Contact Admin",   callback_data=f"contactadmin|{eid}"),
         InlineKeyboardButton("❓ Help",             callback_data=f"dealhelp|{eid}")],
        [InlineKeyboardButton("📜 Deal Terms",       callback_data=f"dealterms|{eid}"),
         InlineKeyboardButton("🔖 Deal Info",        callback_data=f"inf|{eid}")],
    ])

# ══════════════════════════════════════════
#  /start  —  DM welcome
# ══════════════════════════════════════════
async def cmd_start(update: Update, ctx):
    u = update.effective_user; upsert_user(u)
    # referral
    if ctx.args:
        code = ctx.args[0].replace("ref_","")
        ref = row("SELECT uid FROM users WHERE referral_code=?", (code,))
        if ref and ref["uid"] != u.id:
            existing = row("SELECT referred_by FROM users WHERE uid=?", (u.id,))
            if existing and not existing.get("referred_by"):
                dbc("UPDATE users SET referred_by=? WHERE uid=?", (ref["uid"], u.id))
                dbc("UPDATE users SET invite_count=invite_count+1, fee_discount=MIN(fee_discount+0.5,50) WHERE uid=?",
                    (ref["uid"],))
                try: await ctx.bot.send_message(ref["uid"],
                    f"🎉 <b>Referral!</b> {u.full_name} joined via your link! +0.5% discount earned.",
                    parse_mode="HTML")
                except: pass

    img = make_welcome_img(u.first_name)
    bio = io.BytesIO(img); bio.name="welcome.png"
    p   = get_user(u.id); code = p.get("referral_code","") if p else ""
    kb  = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Start Escrow Deal", callback_data="start_escrow"),
         InlineKeyboardButton("👤 My Profile",       callback_data="my_profile")],
        [InlineKeyboardButton("📊 My Deals",         callback_data="my_deals"),
         InlineKeyboardButton("📜 My History",       callback_data="my_history")],
        [InlineKeyboardButton("❓ Help & Commands",  callback_data="show_help"),
         InlineKeyboardButton("📞 Contact Admin",    callback_data="contact_admin")],
        [InlineKeyboardButton("📑 Terms",            callback_data="show_terms"),
         InlineKeyboardButton("📑 Terms",            callback_data="show_terms")],
        [InlineKeyboardButton("🔐 How It Works",     callback_data="how_it_works"),
         InlineKeyboardButton("🔗 My Referral Link", callback_data="my_referral")],
    ])
    await update.message.reply_photo(
        photo=InputFile(bio),
        caption=(
            f"🔐 <b>{BOT_NAME}</b>\n\n"
            f"Hello <b>{u.first_name}</b>! 👋\n\n"
            "I create <b>private encrypted groups</b> for every escrow deal.\n\n"
            "✦ Private group — buyer &amp; seller only\n"
            "✦ Bot is admin of the group\n"
            "✦ Group auto-deleted when deal closes\n"
            "✦ Admin mediator available on demand\n"
            "✦ Dispute resolution system\n\n"
            "<b>To start a deal:</b> Go to any group and type <code>/form</code>\n\n"
            "<i>Every deal is private. No one else can see your conversation.</i>"
        ),
        parse_mode="HTML", reply_markup=kb,
    )

# ══════════════════════════════════════════
#  FORM — triggered in GROUP
# ══════════════════════════════════════════
FORM_TEMPLATE = """📋 <b>New Escrow Deal Form</b>

Fill in the details below, then send it back as one message:

<code>SELLER   : {name}
BUYER    : @username_of_buyer
ITEM     : describe your item or service
AMOUNT   : ₹0
MODE     : UPI / Bank Transfer
VALID    : YYYY-MM-DD
TERMS    : your deal conditions here</code>

<i>✏️ Copy the block above, fill it in, and send it here.</i>"""

async def cmd_form(update: Update, ctx):
    u    = update.effective_user
    chat = update.effective_chat
    upsert_user(u)
    # Works in BOTH DM and groups
    # In DM: seller fills form → bot creates private group → buyer+seller invited
    # In group: same flow, private group still created
    seller_name = u.full_name or u.username or str(u.id)
    PENDING[u.id] = {
        "seller_id":   u.id,
        "seller_name": seller_name,
        "origin_chat": chat.id,   # used for fallback only
        "from_dm":     chat.type == "private",
    }
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel_form")]])
    await update.message.reply_text(
        FORM_TEMPLATE.format(name=seller_name),
        parse_mode="HTML", reply_markup=kb,
    )

async def cmd_escrow(update: Update, ctx): await cmd_form(update, ctx)

# ══════════════════════════════════════════
#  TEXT HANDLER
# ══════════════════════════════════════════
async def text_handler(update: Update, ctx):
    msg = update.message; u = update.effective_user
    if not msg or not u: return
    upsert_user(u)
    text = (msg.text or "").strip(); low = text.lower()

    if low in ("form","#form","#escrow","escrow"):
        return await cmd_form(update, ctx)

    if u.id in PENDING:
        return await _process_form(update, ctx, text)

    # Seller sending their UPI ID after buyer confirmed deal done
    if u.id in SELLER_UPI:
        eid = SELLER_UPI.pop(u.id)
        e   = get_escrow(eid)
        upi = text.strip()
        dbc("UPDATE escrows SET seller_upi=? WHERE id=?", (upi, eid))
        pgid = (e.get("private_gid") or e.get("origin_chat")) if e else None
        if pgid:
            try:
                await ctx.bot.send_message(pgid,
                    f"💳 <b>Seller UPI ID Received</b>\n\n"
                    f"  🏦 UPI : <code>{upi}</code>\n\n"
                    f"Admin is processing the payout of <b>{e.get('amount','—')}</b>.\n"
                    f"Please wait a moment...",
                    parse_mode="HTML")
            except: pass
        for aid in ADMIN_IDS:
            try:
                await ctx.bot.send_message(aid,
                    f"💸 <b>PAYOUT REQUIRED — Deal #{eid}</b>\n\n"
                    f"  💰 Amount      : <b>{e.get('amount','—')}</b>\n"
                    f"  🏦 Seller UPI  : <code>{upi}</code>\n"
                    f"  💼 Seller      : {e.get('seller_name','—')}\n\n"
                    f"1️⃣ Transfer <b>{e.get('amount','—')}</b> to <code>{upi}</code>\n"
                    f"2️⃣ Upload the payment screenshot here as proof\n"
                    f"3️⃣ Then send: <code>/payout {eid}</code>\n\n"
                    f"This will close the deal and delete the group in 5 minutes.",
                    parse_mode="HTML")
            except: pass
        await msg.reply_text(
            f"✅ <b>UPI ID received!</b>\n\n"
            f"Admin has been notified and will transfer <b>{e.get('amount','—')}</b> "
            f"to <code>{upi}</code> shortly.\n\n"
            f"You will be notified once the payment is sent.",
            parse_mode="HTML")
        await safe_log(ctx, f"💳 Seller UPI for #{eid}: {upi} | seller: {u.full_name}")
        return

    if u.id in RATE_Q:
        rq = RATE_Q.pop(u.id)
        try:
            score = int(text.strip()); assert 1 <= score <= 5
            dbc("UPDATE users SET rating=((rating*deal_count+?)/(deal_count+1)) WHERE uid=?",
                (score, rq["rated_id"]))
            await msg.reply_text(f"⭐ You gave <b>{score}/5</b>. Thank you!", parse_mode="HTML")
        except:
            await msg.reply_text("❌ Send a number 1-5."); RATE_Q[u.id] = rq

# ══════════════════════════════════════════
#  FORM PARSING
# ══════════════════════════════════════════
async def _process_form(update: Update, ctx, text: str):
    u = update.effective_user; p = PENDING.pop(u.id)

    def get(pattern, default="—"):
        m = re.search(pattern, text, re.I | re.MULTILINE)
        return m.group(1).strip() if m else default

    buyer_raw  = get(r"BUYER\s*:\s*(.+)")
    item       = get(r"ITEM\s*:\s*(.+)")
    amount_raw = get(r"AMOUNT\s*:\s*(.+)")
    mode       = get(r"MODE\s*:\s*(.+)", "UPI")
    valid      = get(r"VALID\s*:\s*(.+)", "—")
    terms      = get(r"TERMS\s*:\s*(.+)", "Standard escrow terms apply.")

    buyer_username = (buyer_raw.lstrip("@").strip()
                      if buyer_raw not in ("—","@username_of_buyer","username_of_buyer","") else None)
    amount      = amount_raw if amount_raw not in ("—","₹0","0") else "₹0"
    seller_name = u.full_name or u.username or str(u.id)

    profile  = get_user(u.id)
    discount = profile.get("fee_discount", 0) if profile else 0
    fee_pct  = max(0, ESCROW_FEE_PCT - discount)

    now = datetime.utcnow().isoformat()
    # Generate unique random 6-digit deal ID
    import random as _random
    while True:
        eid = _random.randint(100000, 999999)
        if not row("SELECT id FROM escrows WHERE id=?", (eid,)):
            break
    c = _conn().cursor()
    c.execute(
        "INSERT INTO escrows "
        "(id,origin_chat,seller_id,seller_name,buyer_name,item,amount,mode,valid_till,terms,fee_pct,created_at,posted_msg_id) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0)",
        (eid, u.id, u.id, seller_name, buyer_username,
         item, amount, mode, valid, terms, fee_pct, now))
    _conn().commit()

    dblog("ESCROW_CREATED", f"#{eid} by {seller_name}")
    await safe_log(ctx, f"🆕 Escrow #{eid}\nSeller: {seller_name}\nBuyer: {buyer_username}\nAmount: {amount}")

    # Acknowledge immediately
    await update.message.reply_text(
        f"✅ <b>Deal #{eid} received!</b>\n\n"
        f"⏳ Creating your private deal group now…",
        parse_mode="HTML"
    )

    # Create private group immediately — no waiting for agree buttons
    asyncio.create_task(_create_private_group_immediate(ctx, eid, u.id, buyer_username))

# ══════════════════════════════════════════
#  IMMEDIATE PRIVATE GROUP CREATION
#  Called right after form is filled — no agree buttons in DM
# ══════════════════════════════════════════
async def _create_private_group_immediate(ctx, eid: int, seller_uid: int, buyer_username: str | None):
    """
    Create private group right away.
    - Add seller (always possible, they started the bot)
    - Try to add buyer by username if userbot can resolve them
    - Post deal card + agree buttons INSIDE the private group
    - Send invite link to seller via DM
    - DM the buyer with invite link if we can find their ID
    """
    global BOT_ID, BOT_USERNAME
    e = get_escrow(eid)
    if not e: return

    seller_name  = e.get("seller_name", "Seller")
    buyer_name   = e.get("buyer_name") or buyer_username or "Buyer"
    amount       = e.get("amount", "—")

    # ── Try to resolve buyer Telegram ID via Telethon ──
    buyer_uid = None
    if USERBOT_ENABLED and buyer_username:
        try:
            ent = await userbot.get_entity(buyer_username)
            buyer_uid = ent.id
            dbc("UPDATE escrows SET buyer_id=? WHERE id=?", (buyer_uid, eid))
            log.info("Resolved buyer @%s → id=%s", buyer_username, buyer_uid)
        except Exception as ex:
            log.warning("Could not resolve buyer @%s: %s", buyer_username, ex)

    # ── Create the private supergroup ─────────────────
    private_gid = None; invite_link = None; raw_id = None

    if USERBOT_ENABLED and BOT_USERNAME:
        info = await ub_create_group(eid, seller_uid, buyer_uid, BOT_USERNAME)
        if info.get("ok"):
            raw_id      = info["raw_id"]
            private_gid = info["gid"]
            invite_link = info.get("link")
            dbc("UPDATE escrows SET private_gid=?,private_raw_id=?,invite_link=?,status='QR_SENT' WHERE id=?",
                (private_gid, raw_id, invite_link, eid))
            e = get_escrow(eid)

            # ── Post deal card + agree buttons inside group ──
            img = make_deal_img(eid, seller_name, buyer_name, amount, "PENDING", e.get("mode","UPI"))
            bio = io.BytesIO(img); bio.name = "deal.png"

            deal_text = _escrow_caption(e, show_agree=True)
            kb        = _deal_kb(eid, e)

            try:
                pmsg = await ctx.bot.send_photo(
                    private_gid, photo=InputFile(bio),
                    caption=deal_text, parse_mode="HTML", reply_markup=kb)
                dbc("UPDATE escrows SET posted_msg_id=?,private_msg_id=? WHERE id=?",
                    (pmsg.message_id, pmsg.message_id, eid))
                try: await ctx.bot.pin_chat_message(private_gid, pmsg.message_id)
                except: pass
            except Exception as ex:
                log.warning("Could not post deal card in private group: %s", ex)

            # ── Instructions pinned below deal card ──────────
            instructions = (
                f"📋 <b>How to proceed — Deal #{eid}</b>\n\n"
                f"  1️⃣  <b>Seller</b> ({seller_name}): press <b>\"I\'m Seller — AGREE\"</b>\n"
                f"  2️⃣  <b>Buyer</b> ({buyer_name}): press <b>\"I\'m Buyer — AGREE\"</b>\n"
                f"  3️⃣  Once both agree, buyer pays via UPI shown below\n"
                f"  4️⃣  Buyer uploads payment screenshot here\n"
                f"  5️⃣  Admin closes with /confirm {eid}\n\n"
                f"💰 Amount  : <b>{amount}</b>\n"
                f"🏦 UPI     : <code>{UPI_ID}</code>\n\n"
                f"📜 Terms: {(e.get('terms') or 'Standard escrow terms.')[:200]}\n\n"
                "🔒 <i>This group is private and encrypted. Auto-deleted on close.</i>\n"
                "⚠️ <i>Escrow fee is non-refundable even if cancelled.</i>"
            )
            try:
                await ctx.bot.send_message(private_gid, instructions,
                    parse_mode="HTML", reply_markup=_private_kb(eid))
            except Exception as ex:
                log.warning("Instructions msg failed: %s", ex)

            # Send QR
            await _send_qr(ctx, private_gid, eid, amount)

            # ── Notify seller in DM ───────────────────────────
            warn_txt = ""
            if info.get("errors"):
                warn_txt = (
                    "\n\n⚠️ <i>Buyer couldn't be auto-added (privacy settings). "
                    "Share the link below with them manually.</i>"
                )
            seller_msg = (
                f"🔐 <b>Private Deal Group Created — #{eid}</b>\n\n"
                f"Your deal group is ready!\n\n"
                f"🔗 <b>Join link:</b> {invite_link}\n\n"
                f"Share this link with your buyer <b>@{buyer_username or buyer_name}</b>\n"
                "Both of you join → press AGREE → deal begins."
                + warn_txt
            )
            try: await ctx.bot.send_message(seller_uid, seller_msg, parse_mode="HTML")
            except Exception as ex: log.warning("Seller DM failed: %s", ex)

            # ── Notify buyer in DM if we resolved their ID ───
            if buyer_uid:
                buyer_msg = (
                    f"🔐 <b>You\'ve been added to an Escrow Deal!</b>\n\n"
                    f"  🔖 Deal ID : <b>#{eid}</b>\n"
                    f"  💼 Seller  : {seller_name}\n"
                    f"  📦 Item    : {e.get('item','—')}\n"
                    f"  💰 Amount  : <b>{amount}</b>\n\n"
                    f"You have been added to the private deal group.\n"
                    f"Open it and press <b>\"I\'m Buyer — AGREE\"</b> if you agree.\n\n"
                    f"🔗 {invite_link}"
                )
                try: await ctx.bot.send_message(buyer_uid, buyer_msg, parse_mode="HTML")
                except Exception as ex: log.warning("Buyer DM failed: %s", ex)

            await safe_log(ctx,
                f"🔐 Private group created\n"
                f"Deal #{eid} | Seller: {seller_name} | Buyer: {buyer_name}\n"
                f"GID: {private_gid} | Link: {invite_link}")
            return

    # ── FALLBACK: userbot not available ──────────────────
    log.warning("Userbot not available — sending deal card in DM with invite instructions")
    e = get_escrow(eid)
    img = make_deal_img(eid, seller_name, buyer_name, amount, "PENDING", e.get("mode","UPI"))
    bio = io.BytesIO(img); bio.name = "deal.png"

    try:
        await ctx.bot.send_photo(
            seller_uid, photo=InputFile(bio),
            caption=_escrow_caption(e, show_agree=True),
            parse_mode="HTML", reply_markup=_deal_kb(eid, e))
    except Exception as ex:
        log.warning("Fallback deal card failed: %s", ex)

    await ctx.bot.send_message(seller_uid,
        f"⚠️ <b>Private group creation not available</b>\n\n"
        f"To enable auto group creation, set up <b>TELETHON_SESSION</b> in your environment.\n\n"
        f"For now, deal #{eid} will proceed here in DM.\n"
        f"Share the deal card above with your buyer and ask them to press <b>I\'m Buyer — AGREE</b>.\n\n"
        f"💰 Amount : {amount}\n🏦 UPI : <code>{UPI_ID}</code>",
        parse_mode="HTML")


# ══════════════════════════════════════════
#  CALLBACK HANDLER
# ══════════════════════════════════════════
async def callback_handler(update: Update, ctx):
    q = update.callback_query; await q.answer()
    d = q.data; u = q.from_user; upsert_user(u)

    # ── Navigation ────────────────────────────────────
    if d == "start_escrow":
        seller_name = u.full_name or u.username or str(u.id)
        PENDING[u.id] = {
            "seller_id":   u.id,
            "seller_name": seller_name,
            "origin_chat": q.message.chat_id,
            "from_dm":     q.message.chat.type == "private",
        }
        kb2 = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel_form")]])
        await q.message.reply_text(
            FORM_TEMPLATE.format(name=seller_name),
            parse_mode="HTML", reply_markup=kb2)
        return
    if d == "cancel_form":
        PENDING.pop(u.id, None); await q.edit_message_text("❌ Cancelled."); return
    if d == "my_profile":   return await _cb_profile(q, ctx, u)
    if d == "my_deals":     return await _cb_mydeals(q, ctx, u)
    if d == "my_history":   return await _cb_myhistory(q, ctx, u)
    if d == "show_help":    return await q.message.reply_text(HELP_TEXT, parse_mode="HTML")
    if d == "contact_admin":
        await q.message.reply_text("📞 Admin notified. They will reach you shortly.", parse_mode="HTML")
        await safe_log(ctx, f"📞 Contact: {u.full_name} ({u.id})"); return
    if d == "show_terms":   return await q.message.reply_text(TERMS_TEXT, parse_mode="HTML")
    if d == "how_it_works": return await q.message.reply_text(HOWTO_TEXT, parse_mode="HTML")
    if d == "my_referral":  return await _cb_referral(q, ctx, u)
    if d == "noop":         return

    # ── Deal callbacks ────────────────────────────────
    parts = d.split("|"); act = parts[0]
    if act in ("ag","ca","ref","inf","dispute","markpaid","addadmin","contactadmin","dealhelp","dealterms","dealdone"):
        try: eid = int(parts[-1])
        except: return
        e = get_escrow(eid)
        if not e: await q.answer("Escrow not found.", show_alert=True); return
        return await _handle_deal_cb(q, ctx, act, parts, eid, e, u)

    # Rate quick buttons
    if act in ("_r1","_r2","_r3","_r4","_r5"):
        try:
            score    = int(act[2:])
            eid      = int(parts[1])
            rated_id = int(parts[2])
            dbc("UPDATE users SET rating=((rating*deal_count+?)/(deal_count+1)), deal_count=deal_count+1 WHERE uid=?",
                (score, rated_id))
            await q.edit_message_text(f"⭐ You gave <b>{score}/5</b>. Thank you!", parse_mode="HTML")
        except: pass
        return

async def _handle_deal_cb(q, ctx, act, parts, eid, e, u):
    is_seller = u.id == e.get("seller_id")
    is_buyer  = u.id == e.get("buyer_id")
    is_adm    = u.id in ADMIN_IDS or u.id in AUTHED

    if act == "dealdone":
        # Buyer confirms deal is done — ask seller for UPI ID
        global SELLER_UPI
        if not (is_buyer or is_adm):
            await q.answer("⚠️ Only the buyer can release payment.", show_alert=True); return
        seller_id = e.get("seller_id")
        if not seller_id:
            await q.answer("Seller not found.", show_alert=True); return
        dbc("UPDATE escrows SET deal_done_at=? WHERE id=?", (datetime.utcnow().isoformat(), eid))
        SELLER_UPI[seller_id] = eid
        pgid = e.get("private_gid") or e.get("origin_chat")
        # Notify group
        await q.message.reply_text(
            f"✅ <b>Buyer confirmed deal is done!</b>\n\n"
            f"💸 Releasing payment to seller...\n\n"
            f"<b>@{e.get('seller_name')}</b> — Please send your <b>UPI ID</b> here "
            f"so admin can transfer the money to you.",
            parse_mode="HTML")
        # DM seller too
        try:
            await ctx.bot.send_message(seller_id,
                f"🎉 <b>Buyer confirmed — Deal Done!</b>\n\n"
                f"💸 Admin will now release <b>{e.get('amount')}</b> to you.\n\n"
                f"Please send your <b>UPI ID</b> in the private deal group "
                f"(or reply here) so admin can transfer the money.",
                parse_mode="HTML")
        except: pass
        await safe_log(ctx, f"💸 Deal #{eid} — buyer released payment. Waiting for seller UPI.")
        return

    if act == "inf":
        await q.message.reply_text(_escrow_caption(e, show_agree=True), parse_mode="HTML"); return

    if act == "dealterms":
        t = (e.get("terms") or "Standard escrow terms apply.")
        await q.message.reply_text(
            f"📜 <b>Deal #{eid} Terms</b>\n\n{t}\n\n"
            f"⚠️ <i>Escrow fee ({e.get('fee_pct',ESCROW_FEE_PCT)}%) is non-refundable.</i>",
            parse_mode="HTML"); return

    if act == "dealhelp":
        await q.message.reply_text(
            f"❓ <b>Help — Deal #{eid}</b>\n\n"
            "👮 <b>Add Admin as Mediator</b> — brings admin into this group\n"
            "⚠️ <b>Raise Dispute</b> — opens formal dispute\n"
            "✅ <b>Mark as Paid</b> — buyer confirms payment sent\n"
            "📞 <b>Contact Admin</b> — notifies admin\n\n"
            "Use /dispute or /contact for direct admin help.",
            parse_mode="HTML"); return

    if act == "contactadmin":
        await q.message.reply_text(
            f"📞 <b>Admin Notified — Deal #{eid}</b>\n\nAdmin will join shortly.",
            parse_mode="HTML")
        await safe_log(ctx, f"📞 Contact for #{eid}\nFrom: {u.full_name} ({u.id})\nChat: {q.message.chat_id}")
        return

    if act == "addadmin":
        if e.get("admin_added"):
            await q.answer("Admin already added.", show_alert=True); return
        raw_id = e.get("private_raw_id")
        added  = []
        if raw_id and USERBOT_ENABLED:
            for aid in ADMIN_IDS:
                ok = await ub_add_user(raw_id, aid)
                if ok: added.append(aid)
        dbc("UPDATE escrows SET admin_added=1 WHERE id=?", (eid,))
        # DM all admins
        for aid in ADMIN_IDS:
            try:
                await ctx.bot.send_message(aid,
                    f"👮 <b>Mediator Request — Escrow #{eid}</b>\n\n"
                    f"Seller: {e.get('seller_name')}\nBuyer: {e.get('buyer_name') or '?'}\n"
                    f"Amount: {e.get('amount')}\n\n"
                    f"{'🔗 ' + e.get('invite_link','') if e.get('invite_link') else 'Join the private group.'}",
                    parse_mode="HTML")
            except: pass
        msg = "✅ Admin added as mediator!" if added else "✅ Admin notified! Joining shortly."
        await q.message.reply_text(f"👮 <b>{msg}</b>", parse_mode="HTML")
        try: await q.message.edit_reply_markup(_private_kb(eid, admin_added=True))
        except: pass
        await safe_log(ctx, f"👮 Mediator requested #{eid} by {u.full_name}")
        return

    if act == "dispute":
        dbc("UPDATE escrows SET status='DISPUTE',dispute_at=?,dispute_by=? WHERE id=?",
            (datetime.utcnow().isoformat(), u.id, eid))
        await q.message.reply_text(
            f"⚠️ <b>Dispute Raised — Deal #{eid}</b>\n\n"
            "Admin has been notified. Please describe the issue in this group.\n"
            "Press <b>Add Admin as Mediator</b> to bring admin here immediately.",
            parse_mode="HTML")
        await safe_log(ctx, f"⚠️ DISPUTE #{eid} by {u.full_name} ({u.id})")
        return

    if act == "markpaid":
        if not (is_buyer or is_adm):
            await q.answer("Only the buyer can mark as paid.", show_alert=True); return
        dbc("UPDATE escrows SET status='PAID',paid_at=? WHERE id=?",
            (datetime.utcnow().isoformat(), eid))
        await q.message.reply_text(
            f"💰 <b>Marked as Paid — Deal #{eid}</b>\n\n"
            f"{u.mention_html()} marked this deal as paid.\n\n"
            "📸 Please also upload the payment screenshot here.\n"
            f"Admin: /confirm {eid} to close the deal.",
            parse_mode="HTML"); return

    # ── AGREE ─────────────────────────────────────────
    if act == "ag":
        role = parts[1]  # 's' or 'b'
        if role == "s":
            if not is_seller and not is_adm:
                await q.answer("⚠️ Only the SELLER can agree for seller.", show_alert=True); return
            dbc("UPDATE escrows SET seller_agreed=1 WHERE id=?", (eid,))
        else:
            # First person to click buyer (who isn't seller) becomes buyer
            if e.get("buyer_id") is None and not is_seller:
                dbc("UPDATE escrows SET buyer_id=?,buyer_name=? WHERE id=?",
                    (u.id, u.username or u.full_name, eid))
                # Update local e for immediate use
                e = get_escrow(eid)
                is_buyer = True
            elif e.get("buyer_id") and not is_buyer and not is_adm:
                await q.answer("⚠️ Only the BUYER can agree for buyer.", show_alert=True); return
            elif is_seller and not is_adm:
                await q.answer("⚠️ You are the seller — use the Seller AGREE button.", show_alert=True); return
            dbc("UPDATE escrows SET buyer_agreed=1 WHERE id=?", (eid,))

        e = get_escrow(eid)
        await _refresh_deal_msg(ctx, e)
        if e.get("seller_agreed") and e.get("buyer_agreed"):
            dbc("UPDATE escrows SET status='AGREED',agreed_at=? WHERE id=?",
                (datetime.utcnow().isoformat(), eid))
            # Group already exists — just confirm and send QR
            asyncio.create_task(_on_both_agreed(ctx, eid))
        return

    # ── CANCEL ────────────────────────────────────────
    if act == "ca":
        role = parts[1]
        if role == "s":
            if not is_seller and not is_adm:
                await q.answer("⚠️ Only the SELLER can cancel for seller.", show_alert=True); return
            dbc("UPDATE escrows SET seller_agreed=0 WHERE id=?", (eid,))
        else:
            if e.get("buyer_id") and not is_buyer and not is_adm:
                await q.answer("⚠️ Only the BUYER can cancel for buyer.", show_alert=True); return
            dbc("UPDATE escrows SET buyer_agreed=0 WHERE id=?", (eid,))
        e = get_escrow(eid)
        await _refresh_deal_msg(ctx, e)
        try:
            await ctx.bot.send_message(e["origin_chat"],
                f"❌ {u.mention_html()} withdrew agreement on Deal #{eid}.",
                parse_mode="HTML")
        except: pass
        return

    if act == "ref":
        e = get_escrow(eid); await _refresh_deal_msg(ctx, e)
        await q.answer("✅ Refreshed!"); return

async def _on_both_agreed(ctx, eid: int):
    """Called when both seller and buyer press AGREE inside the private group."""
    e = get_escrow(eid)
    if not e: return
    private_gid = e.get("private_gid")
    amount      = e.get("amount", "—")

    msg = (
        f"🤝 <b>Both parties agreed — Deal #{eid}!</b>\n\n"
        f"  💼 Seller : {e.get('seller_name','—')}\n"
        f"  🛒 Buyer  : {e.get('buyer_name','—')}\n"
        f"  💰 Amount : <b>{amount}</b>\n\n"
        "Buyer, please pay now and upload the payment screenshot here.\n\n"
        f"🏦 UPI : <code>{UPI_ID}</code>\n"
        f"💰 Amount : <b>{amount}</b>"
    )
    if private_gid:
        try:
            await ctx.bot.send_message(private_gid, msg, parse_mode="HTML")
        except Exception as ex:
            log.warning("on_both_agreed msg: %s", ex)
    await safe_log(ctx, f"🤝 Both agreed on Deal #{eid}")


async def _refresh_deal_msg(ctx, e):
    gid = e.get("origin_chat"); mid = e.get("posted_msg_id")
    if not (gid and mid): return
    try:
        await ctx.bot.edit_message_caption(
            chat_id=gid, message_id=mid,
            caption=_escrow_caption(e), parse_mode="HTML",
            reply_markup=_deal_kb(e["id"], e))
    except:
        try:
            await ctx.bot.edit_message_text(
                chat_id=gid, message_id=mid,
                text=_escrow_caption(e), parse_mode="HTML",
                reply_markup=_deal_kb(e["id"], e))
        except: pass

# ══════════════════════════════════════════
#  PRIVATE GROUP CREATION
# ══════════════════════════════════════════
async def _create_private_group(ctx, eid):
    global BOT_ID, BOT_USERNAME
    e = get_escrow(eid)
    if not e: return
    gid       = e["origin_chat"]
    seller_id = e["seller_id"]
    buyer_id  = e.get("buyer_id")
    amount    = e.get("amount", "—")

    # Determine where to post status updates
    # If origin_chat is a private chat (DM), we post to seller's DM
    # The private group is always created regardless
    try:
        chat_info = await ctx.bot.get_chat(gid)
        is_dm_origin = chat_info.type == "private"
    except:
        is_dm_origin = False

    try:
        wait = await ctx.bot.send_message(gid,
            f"🔐 <b>Deal #{eid} — Both parties agreed!</b>\n\n"
            "⏳ Creating your private encrypted group…",
            parse_mode="HTML")
    except Exception as ex:
        log.warning("Could not send wait msg to origin: %s", ex)
        # Fallback: send to seller DM
        wait_gid = seller_id
        try:
            wait = await ctx.bot.send_message(seller_id,
                f"🔐 <b>Deal #{eid} — Both parties agreed!</b>\n\n"
                "⏳ Creating your private encrypted group…",
                parse_mode="HTML")
        except: pass
        wait = type("obj", (object,), {"message_id": 0})()

    private_gid = None; invite_link = None; raw_id = None

    if USERBOT_ENABLED and BOT_USERNAME:
        info = await ub_create_group(eid, seller_id, buyer_id, BOT_USERNAME)
        if info.get("ok"):
            raw_id      = info["raw_id"]
            private_gid = info["gid"]
            invite_link = info.get("link")
            dbc("UPDATE escrows SET private_gid=?,private_raw_id=?,invite_link=?,status='QR_SENT' WHERE id=?",
                (private_gid, raw_id, invite_link, eid))

            terms = (e.get("terms") or "Standard escrow terms apply.")

            # Welcome message inside private group
            welcome = (
                f"🔐 <b>Welcome to Your Private Escrow Group</b>\n\n"
                f"🔖 Deal ID     :  <b>#{eid}</b>\n"
                f"💼 Seller      :  {e.get('seller_name') or '—'}\n"
                f"🛒 Buyer       :  {e.get('buyer_name') or 'Buyer'}\n"
                f"💰 Amount      :  <b>{amount}</b>\n"
                f"💳 Mode        :  {e.get('mode','UPI')}\n"
                f"📅 Valid Till  :  {e.get('valid_till','—')}\n"
                f"🏷️ Fee         :  {_fee_str(e)} ({e.get('fee_pct',ESCROW_FEE_PCT)}%)\n\n"
                f"📜 <b>Terms:</b>  {terms[:300]}\n\n"
                f"🔒 <b>This group is end-to-end encrypted.</b>\n"
                "Only you two are here. Auto-deleted when deal closes.\n\n"
                f"<b>Next steps:</b>\n"
                f"  1️⃣  Buyer pays <b>{amount}</b>\n"
                f"  2️⃣  UPI: <code>{UPI_ID}</code>\n"
                f"  3️⃣  Upload payment screenshot here\n"
                f"  4️⃣  Seller confirms receipt\n"
                f"  5️⃣  Admin closes with /confirm {eid}\n\n"
                f"⚠️ <i>Escrow fee is non-refundable even if cancelled.</i>"
            )
            try:
                pmsg = await ctx.bot.send_message(
                    private_gid, welcome, parse_mode="HTML",
                    reply_markup=_private_kb(eid))
                dbc("UPDATE escrows SET private_msg_id=? WHERE id=?", (pmsg.message_id, eid))
                try: await ctx.bot.pin_chat_message(private_gid, pmsg.message_id)
                except: pass
            except Exception as ex:
                log.warning("Welcome msg to private group failed: %s", ex)

            # Send QR in private group
            await _send_qr(ctx, private_gid, eid, amount)

            # Update origin group message
            warn = ""
            if info.get("errors"):
                warn = ("\n\n⚠️ <i>Some users couldn't be auto-added (privacy settings). "
                        "They must join via the link below.</i>")
            try:
                await ctx.bot.edit_message_text(
                    chat_id=gid, message_id=wait.message_id,
                    text=(
                        f"✅ <b>Private Group Created — Deal #{eid}</b>\n\n"
                        f"💼 Seller : {e.get('seller_name') or '—'}\n"
                        f"🛒 Buyer  : {e.get('buyer_name') or 'Buyer'}\n"
                        f"💰 Amount : <b>{amount}</b>\n\n"
                        f"🔗 <a href='{invite_link}'>Join Your Private Deal Group</a>\n\n"
                        "<i>🔒 Only buyer &amp; seller. Auto-deleted on close.</i>"
                        + warn
                    ),
                    parse_mode="HTML", disable_web_page_preview=False)
            except Exception as ex:
                log.warning("Edit origin msg: %s", ex)
                await ctx.bot.send_message(gid,
                    f"✅ <b>Private group ready!</b>\n"
                    f"🔗 <a href='{invite_link}'>Join — Deal #{eid}</a>",
                    parse_mode="HTML")
        else:
            log.warning("Userbot failed: %s", info.get("error"))
            await _fallback_dm(ctx, e, gid, wait.message_id, amount)
    else:
        await _fallback_dm(ctx, e, gid, wait.message_id, amount)

    await safe_log(ctx,
        f"🤝 Deal #{eid} AGREED\n"
        f"Seller: {e.get('seller_name')}\nBuyer: {e.get('buyer_name')}\n"
        f"Amount: {amount}\nPrivate GID: {private_gid}")


async def _fallback_dm(ctx, e, gid, wait_mid, amount):
    eid = e["id"]
    msg = (
        f"🔐 <b>Deal #{eid} — Agreed!</b>\n\n"
        f"💰 Amount : <b>{amount}</b>\n"
        f"🏦 UPI    : <code>{UPI_ID}</code>\n\n"
        "Steps:\n"
        f"  1️⃣  Buyer pays {amount} to UPI above\n"
        "  2️⃣  Upload screenshot in the group\n"
        f"  3️⃣  Admin confirms: /confirm {eid}\n\n"
        "⚠️ <i>Escrow fee is non-refundable.</i>"
    )
    for uid in [e.get("seller_id"), e.get("buyer_id")]:
        if uid:
            try: await ctx.bot.send_message(uid, msg, parse_mode="HTML")
            except: pass
    await _send_qr(ctx, gid, eid, amount)
    try:
        await ctx.bot.edit_message_text(chat_id=gid, message_id=wait_mid,
            text=(
                f"✅ <b>Deal #{eid} Agreed!</b>\n\n"
                f"Both parties notified via DM.\n"
                f"💰 {amount}  |  UPI: <code>{UPI_ID}</code>\n\n"
                f"📸 Upload payment screenshot here.\n"
                f"Admin: /confirm {eid}"
            ), parse_mode="HTML")
    except: pass


async def _send_qr(ctx, chat_id, eid, amount):
    cap = (
        f"💳 <b>Payment Details — Deal #{eid}</b>\n\n"
        f"  💰 Amount  :  <b>{amount}</b>\n"
        f"  🏦 UPI ID  :  <code>{UPI_ID}</code>\n\n"
        "Scan the QR code or use the UPI ID above.\n"
        "After paying, send the <b>payment screenshot</b> in this group."
    )
    try:
        if QR_BYTES:
            bio = io.BytesIO(QR_BYTES); bio.name = "qr.png"
            await ctx.bot.send_photo(chat_id, photo=InputFile(bio), caption=cap, parse_mode="HTML")
        else:
            await ctx.bot.send_message(chat_id, cap, parse_mode="HTML")
    except Exception as e: log.warning("QR send: %s", e)

# ══════════════════════════════════════════
#  PHOTO HANDLER
# ══════════════════════════════════════════
async def photo_handler(update: Update, ctx):
    msg = update.message; u = update.effective_user
    if not msg or not u: return
    upsert_user(u)
    chat_id = update.effective_chat.id
    c = _conn().cursor()
    c.execute(
        "SELECT id FROM escrows WHERE (origin_chat=? OR private_gid=?) "
        "AND status IN ('QR_SENT','AGREED','PAID') ORDER BY created_at DESC LIMIT 1",
        (chat_id, chat_id))
    r = c.fetchone()
    if not r: await msg.reply_text("📸 Screenshot received. No active deal here."); return
    eid = r[0]
    # ── OCR: extract TX ID + amount from screenshot ──────
    cap = msg.caption or ""
    img_bytes = None
    try:
        bio2 = io.BytesIO()
        if msg.photo:
            f2 = await msg.photo[-1].get_file()
        else:
            f2 = await msg.document.get_file()
        await f2.download_to_memory(bio2)
        img_bytes = bio2.getvalue()
    except Exception as ex:
        log.warning("Photo download for OCR: %s", ex)

    # ── OCR: Try all strategies to extract TX ID + amount ──
    ocr_result = {"tx_id": None, "amount": None}

    # Step 1: Caption/message text (user may type TX ID in caption)
    if cap.strip():
        try:
            from plugins.ocr_plugin import extract_from_text
            ocr_result = extract_from_text(cap)
            log.info("Caption OCR result: %s", ocr_result)
        except Exception as ex:
            log.warning("Caption OCR: %s", ex)

    # Step 2: Full image OCR
    if img_bytes and (not ocr_result.get("tx_id") or not ocr_result.get("amount")):
        try:
            from plugins.ocr_plugin import extract_from_image_bytes
            img_result = extract_from_image_bytes(img_bytes)
            log.info("Image OCR result: %s", img_result)
            if not ocr_result.get("tx_id"):   ocr_result["tx_id"]  = img_result.get("tx_id")
            if not ocr_result.get("amount"):  ocr_result["amount"] = img_result.get("amount")
        except Exception as ex:
            log.warning("Image OCR: %s", ex)

    # Step 3: Pure regex fallback directly on caption
    if not ocr_result.get("tx_id") or not ocr_result.get("amount"):
        _tx_pats = [
            r'T\d{20,25}',
            r'UTR[:\s#.]*([A-Z0-9]{10,22})',
            r'(?:Transaction\s*ID|Txn\s*ID)[:\s#.]*([A-Z0-9]{8,25})',
            r'(?:ID|Ref)[:\s]*([A-Z0-9]{12,25})',
        ]
        _amt_pats = [
            r'₹\s*([0-9,]+(?:\.[0-9]{1,2})?)',
            r'Rs\.?\s*([0-9,]+(?:\.[0-9]{1,2})?)',
            r'(?:Amount|Amt|Paid)[:\s₹]*([0-9,]+(?:\.[0-9]{1,2})?)',
        ]
        for p in _tx_pats:
            m = re.search(p, cap, re.I)
            if m and not ocr_result.get("tx_id"):
                val = (m.group(1) if m.lastindex else m.group(0)).strip().upper()
                val = re.sub(r"[^A-Z0-9]", "", val)
                if len(val) >= 8: ocr_result["tx_id"] = val; break
        for p in _amt_pats:
            m = re.search(p, cap, re.I)
            if m and not ocr_result.get("amount"):
                ocr_result["amount"] = m.group(1).replace(",",""); break

    log.info("Final OCR result for deal #%s: %s", eid, ocr_result)

    tx_id  = ocr_result.get("tx_id")
    amount = ocr_result.get("amount")

    dbc("UPDATE escrows SET tx_id=?,tx_amount=?,paid_at=?,status='PAID' WHERE id=?",
        (tx_id, amount, datetime.utcnow().isoformat(), eid))

    conf_tx  = "✅" if tx_id  else "❓"
    conf_amt = "✅" if amount else "❓"
    tip = ""
    if not tx_id or not amount:
        tip = (
            "\n\n💡 <b>Tip for next time:</b> Type TX ID in the caption "
            "when uploading screenshot for instant detection.\n"
            "Example: <code>TX: T2605291651 Amount: ₹500</code>"
        )
    await msg.reply_text(
        f"✅ <b>Screenshot Received — Deal #{eid}</b>\n\n"
        f"  👤 Submitted by : {u.mention_html()}\n"
        f"  {conf_tx} TX ID  : <code>{tx_id  or 'Not detected'}</code>\n"
        f"  {conf_amt} Amount : <code>{amount or 'Not detected'}</code>\n\n"
        f"⏳ Admin: verify and use /confirm {eid}" + tip,
        parse_mode="HTML")
    if LOG_CHANNEL:
        try:
            await ctx.bot.forward_message(LOG_CHANNEL, chat_id, msg.message_id)
            await ctx.bot.send_message(LOG_CHANNEL,
                f"[PAYMENT] #{eid} | {u.full_name} | TX:{tx_id} | Amt:{amount}")
        except: pass

# ══════════════════════════════════════════
#  PROFILE CALLBACKS
# ══════════════════════════════════════════
async def _cb_profile(q, ctx, u):
    p = get_user(u.id)
    all_e  = rows("SELECT * FROM escrows WHERE seller_id=? OR buyer_id=? ORDER BY id DESC LIMIT 5",(u.id,u.id))
    total  = row("SELECT COUNT(*) c FROM escrows WHERE seller_id=? OR buyer_id=?",(u.id,u.id))["c"]
    closed = row("SELECT COUNT(*) c FROM escrows WHERE (seller_id=? OR buyer_id=?) AND status='CLOSED'",(u.id,u.id))["c"]
    active = row("SELECT COUNT(*) c FROM escrows WHERE (seller_id=? OR buyer_id=?) AND status IN ('PENDING','AGREED','QR_SENT','PAID')",(u.id,u.id))["c"]
    text = (
        f"👤 <b>Your Profile</b>\n\n"
        f"  🏷️ Name       : <b>{p.get('full_name') if p else u.full_name}</b>\n"
        f"  📌 Username   : @{u.username or 'N/A'}\n"
        f"  🆔 ID         : <code>{u.id}</code>\n"
        f"  📅 Joined     : {(p.get('joined') or '')[:10] if p else '—'}\n\n"
        f"  📊 Total Deals : <b>{total}</b>\n"
        f"  ✅ Completed   : <b>{closed}</b>\n"
        f"  ⏳ Active      : <b>{active}</b>\n"
        f"  ⭐ Rating      : <b>{p.get('rating',5.0):.1f}/5.0</b>\n"
        f"  🏷️ Fee Discount: <b>{p.get('fee_discount',0):.1f}%</b>\n"
    )
    if all_e:
        text += "\n<b>Recent Deals:</b>\n"
        for e in all_e[:4]:
            r2 = "💼" if e.get("seller_id")==u.id else "🛒"
            text += f"  {r2} #{e['id']} — {e.get('amount','—')} — {_se(e['status'])}{e['status']}\n"
    await q.message.reply_text(text, parse_mode="HTML")

async def _cb_mydeals(q, ctx, u):
    deals = rows(
        "SELECT * FROM escrows WHERE (seller_id=? OR buyer_id=?) "
        "AND status IN ('PENDING','AGREED','QR_SENT','PAID','DISPUTE') ORDER BY id DESC",(u.id,u.id))
    if not deals: await q.message.reply_text("⏳ No active deals."); return
    text = "⏳ <b>Your Active Deals</b>\n\n"
    for e in deals:
        role = "💼 Seller" if e.get("seller_id")==u.id else "🛒 Buyer"
        text += f"{_se(e['status'])} <b>#{e['id']}</b>  {role}  —  {e.get('amount','—')}  —  {e['status']}\n"
    await q.message.reply_text(text, parse_mode="HTML")

async def _cb_myhistory(q, ctx, u):
    deals = rows(
        "SELECT * FROM escrows WHERE (seller_id=? OR buyer_id=?) "
        "AND status IN ('CLOSED','CANCELLED') ORDER BY id DESC LIMIT 20",(u.id,u.id))
    if not deals: await q.message.reply_text("📜 No history yet."); return
    text = "📜 <b>Deal History</b>\n\n"
    for e in deals:
        role = "💼 Seller" if e.get("seller_id")==u.id else "🛒 Buyer"
        text += f"{_se(e['status'])} <b>#{e['id']}</b>  {role}  —  {e.get('amount','—')}  —  {(e.get('created_at') or '')[:10]}\n"
    await q.message.reply_text(text, parse_mode="HTML")

async def _cb_referral(q, ctx, u):
    p = get_user(u.id); code = p.get("referral_code","") if p else ""
    me = await ctx.bot.get_me()
    link = f"https://t.me/{me.username}?start=ref_{code}"
    await q.message.reply_text(
        f"🔗 <b>Your Referral Link</b>\n\n<code>{link}</code>\n\n"
        f"👥 Invites: <b>{p.get('invite_count',0) if p else 0}</b>\n"
        f"🏷️ Discount: <b>{p.get('fee_discount',0):.1f}%</b>\n\n"
        "Each successful invite = +0.5% fee discount (max 50%)",
        parse_mode="HTML")

# ══════════════════════════════════════════
#  STATIC TEXTS
# ══════════════════════════════════════════
HELP_TEXT = """
╔══════════════════════════════════════════╗
║     🔐  ESCROWER BOT — COMMAND CENTER    ║
╚══════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━
🔐  ESCROW DEAL COMMANDS
━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 /escrow  or  /form
   ↳ Start a new escrow deal

📊 /deals
   ↳ View active deals in this group

🔖 /dealinfo &lt;deal_id&gt;
   ↳ Full info on a specific deal

📜 /dealterms &lt;deal_id&gt;
   ↳ View terms of a deal

❌ /stopdeal &lt;deal_id&gt;
   ↳ Cancel a deal (parties only)

⚠️ /dispute &lt;deal_id&gt; [reason]
   ↳ Raise a dispute on a deal

━━━━━━━━━━━━━━━━━━━━━━━━━━
👤  MY ACCOUNT
━━━━━━━━━━━━━━━━━━━━━━━━━━

👤 /myprofile
   ↳ Your profile card

📋 /mytransactions
   ↳ All your escrow transactions

⏳ /mydeals
   ↳ Only your active deals

📜 /myhistory
   ↳ Completed & cancelled deals

📊 /mystats
   ↳ Your full statistics

⭐ /myrating
   ↳ Your trust score & rating

🏷️ /myfee
   ↳ Your escrow fee rate

🔗 /myreferral
   ↳ Your referral link

━━━━━━━━━━━━━━━━━━━━━━━━━━
📞  SUPPORT & HELP
━━━━━━━━━━━━━━━━━━━━━━━━━━

❓ /help
   ↳ This command list

📞 /contact
   ↳ Contact admin directly

🆘 /problem [description]
   ↳ Report a problem

🔐 /howitworks
   ↳ How escrow works (step by step)

📜 /terms
   ↳ Full terms & conditions

💰 /fees
   ↳ Fee structure & discounts

📊 /stats
   ↳ Group & bot statistics

🆔 /id
   ↳ Get your Telegram user ID

━━━━━━━━━━━━━━━━━━━━━━━━━━
🛡️  ADMIN COMMANDS
━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ /confirm &lt;id&gt;
   ↳ Confirm payment received — money held

💸 /payout &lt;id&gt;
   ↳ Confirm payout sent to seller — closes deal

❌ /cancelescrow &lt;id&gt;
   ↳ Force cancel a deal

💰 /setfee &lt;percent&gt;
   ↳ Set global escrow fee

🏷️ /setuserfee &lt;uid&gt; &lt;discount%&gt;
   ↳ Set custom fee for a user

👮 /addmediator &lt;deal_id&gt;
   ↳ Add admin to private deal group

⚖️ /resolvedispute &lt;id&gt; [resolution]
   ↳ Resolve a dispute & close deal

━━━━━━━━━━━━━━━━━━━━━━━━━━
🔧  GROUP MODERATION
━━━━━━━━━━━━━━━━━━━━━━━━━━

⛔ /ban  /unban &lt;id&gt;
   ↳ Ban or unban a user

🚪 /kick
   ↳ Kick a user (reply to them)

🔇 /mute  /unmute
   ↳ Mute or unmute a user

⚠️ /warn &lt;reason&gt;
   ↳ Warn a user (reply to them)

📋 /warnings
   ↳ See warnings for a user

🗑️ /clearwarn
   ↳ Clear all warnings for a user

⭐ /promote  /demote
   ↳ Give or remove admin rights

📌 /pin  /unpin
   ↳ Pin or unpin messages

🔒 /lock  /unlock
   ↳ Lock or unlock the group

🧹 /purge [n]  /del
   ↳ Delete messages

⏱️ /slowmode &lt;seconds&gt;
   ↳ Set message slowmode

━━━━━━━━━━━━━━━━━━━━━━━━━━
📢  BROADCAST & POLLS
━━━━━━━━━━━━━━━━━━━━━━━━━━

📣 /announce &lt;text&gt;
   ↳ Send announcement in group

📡 /broadcast &lt;text&gt;
   ↳ DM all bot users

📊 /poll Q|opt1|opt2|opt3
   ↳ Create a poll

━━━━━━━━━━━━━━━━━━━━━━━━━━
📊  DATA & LOGS  (admin)
━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 /alldeals
   ↳ View all escrow deals

⏳ /pendingdeals
   ↳ View pending/active deals

👥 /userstats  /botstats
   ↳ Full bot statistics

📋 /logs
   ↳ Recent activity logs

🔑 /auth &lt;password&gt;
   ↳ Admin session login

━━━━━━━━━━━━━━━━━━━━━━━━━━
💡  QUICK TIPS
━━━━━━━━━━━━━━━━━━━━━━━━━━

• Send /escrow in DM to start a deal instantly
• Every deal gets a private encrypted group
• Bot is admin of the group — fully automated
• Use /dispute if anything goes wrong
• Admin holds money safely until buyer confirms
• Group auto-deletes 5 min after deal closes

╔══════════════════════════════════════════╗
║  🔒 End-to-End Encrypted  •  Verified   ║
║  Every deal is private & secure  🛡️     ║
╚══════════════════════════════════════════╝
"""


TERMS_TEXT = f"""
📜 <b>Terms &amp; Conditions</b>

<b>1. Escrow Fee</b>
All deals carry a {ESCROW_FEE_PCT}% escrow fee (charged to seller). This fee is <b>non-refundable</b> even if the deal is cancelled.

<b>2. Privacy</b>
Each deal gets its own <b>private encrypted group</b>. Only the buyer, seller, and (if requested) admin mediator have access. The bot is admin of the group.

<b>3. Payments</b>
All payments go through the agreed UPI/bank details. Admin makes the final confirmation.

<b>4. Disputes</b>
Either party can raise a dispute at any time. Admin will review and make a final binding decision.

<b>5. Cancellation</b>
Either party can cancel. Escrow fee is non-refundable.

<b>6. Auto-deletion</b>
Private deal groups are automatically deleted when deal is closed or cancelled.

<b>7. Liability</b>
This bot is a facilitator only. Not responsible for quality of goods/services.

<b>8. End-to-end Privacy</b>
Deal communications are in a private Telegram group visible only to deal parties.
"""

HOWTO_TEXT = """
🔐 <b>How Escrower Works</b>

<b>Step 1 — Start Deal (in a group)</b>
Seller types /form in the group. Fills in buyer, item, amount, terms.

<b>Step 2 — Both Parties Agree</b>
Deal card appears in the group with buttons:
• Seller presses <b>"I'm Seller — AGREE"</b>
• Buyer presses <b>"I'm Buyer — AGREE"</b>
Each person can ONLY agree/cancel for their own role.

<b>Step 3 — Private Group Created</b>
A private group is automatically created with:
• Buyer only
• Seller only
• Bot as admin
Nobody else. A join link is posted in the main group.

<b>Step 4 — Payment</b>
Buyer pays via UPI. Uploads payment screenshot in the private group.

<b>Step 5 — Confirmation</b>
Admin verifies and confirms with /confirm.

<b>Step 6 — Deal Closed</b>
Deal is closed. Both parties rate each other. Private group is <b>auto-deleted</b>.

<b>Need help any time?</b>
Press <b>"Add Admin as Mediator"</b> inside the private group.
"""

# ══════════════════════════════════════════
#  USER COMMANDS
# ══════════════════════════════════════════
async def cmd_help(u, c):
    await u.message.reply_text(HELP_TEXT, parse_mode="HTML")

async def cmd_myprofile(update: Update, ctx):
    u = update.effective_user; upsert_user(u)
    p = get_user(u.id)
    total  = row("SELECT COUNT(*) c FROM escrows WHERE seller_id=? OR buyer_id=?",(u.id,u.id))["c"]
    closed = row("SELECT COUNT(*) c FROM escrows WHERE (seller_id=? OR buyer_id=?) AND status='CLOSED'",(u.id,u.id))["c"]
    active = row("SELECT COUNT(*) c FROM escrows WHERE (seller_id=? OR buyer_id=?) AND status IN ('PENDING','AGREED','QR_SENT','PAID')",(u.id,u.id))["c"]
    await update.message.reply_text(
        f"👤 <b>Your Profile</b>\n\n"
        f"  🏷️ Name       : <b>{p.get('full_name') if p else u.full_name}</b>\n"
        f"  📌 Username   : @{u.username or 'N/A'}\n"
        f"  🆔 ID         : <code>{u.id}</code>\n"
        f"  📅 Joined     : {(p.get('joined') or '')[:10] if p else '—'}\n\n"
        f"  📊 Total Deals : <b>{total}</b>\n"
        f"  ✅ Completed   : <b>{closed}</b>\n"
        f"  ⏳ Active      : <b>{active}</b>\n"
        f"  ⭐ Rating      : <b>{p.get('rating',5.0):.1f}/5.0</b>\n"
        f"  🏷️ Fee Discount: <b>{p.get('fee_discount',0):.1f}%</b>\n",
        parse_mode="HTML")

async def cmd_mytransactions(update: Update, ctx):
    u = update.effective_user; upsert_user(u)
    deals = rows("SELECT * FROM escrows WHERE seller_id=? OR buyer_id=? ORDER BY id DESC LIMIT 30",(u.id,u.id))
    if not deals: await update.message.reply_text("📋 No transactions yet."); return
    text = "📋 <b>All Transactions</b>\n\n"
    for e in deals:
        r2 = "💼" if e.get("seller_id")==u.id else "🛒"
        text += f"{r2} #{e['id']} — {e.get('amount','—')} — {_se(e['status'])}{e['status']} — {(e.get('created_at') or '')[:10]}\n"
    await update.message.reply_text(text, parse_mode="HTML")

async def cmd_mydeals(update: Update, ctx):
    u = update.effective_user; upsert_user(u)
    deals = rows("SELECT * FROM escrows WHERE (seller_id=? OR buyer_id=?) AND status IN ('PENDING','AGREED','QR_SENT','PAID','DISPUTE') ORDER BY id DESC",(u.id,u.id))
    if not deals: await update.message.reply_text("⏳ No active deals."); return
    text = "⏳ <b>Active Deals</b>\n\n"
    for e in deals:
        role = "💼 Seller" if e.get("seller_id")==u.id else "🛒 Buyer"
        text += f"{_se(e['status'])} <b>#{e['id']}</b>  {role}  —  {e.get('amount','—')}\n"
    await update.message.reply_text(text, parse_mode="HTML")

async def cmd_myhistory(update: Update, ctx):
    u = update.effective_user; upsert_user(u)
    deals = rows("SELECT * FROM escrows WHERE (seller_id=? OR buyer_id=?) AND status IN ('CLOSED','CANCELLED') ORDER BY id DESC LIMIT 20",(u.id,u.id))
    if not deals: await update.message.reply_text("📜 No history yet."); return
    text = "📜 <b>Deal History</b>\n\n"
    for e in deals:
        role = "💼 Seller" if e.get("seller_id")==u.id else "🛒 Buyer"
        text += f"{_se(e['status'])} <b>#{e['id']}</b>  {role}  —  {e.get('amount','—')}  —  {(e.get('created_at') or '')[:10]}\n"
    await update.message.reply_text(text, parse_mode="HTML")

async def cmd_mystats(update: Update, ctx):
    u = update.effective_user; upsert_user(u); p = get_user(u.id)
    all_e  = rows("SELECT * FROM escrows WHERE seller_id=? OR buyer_id=?",(u.id,u.id))
    total  = len(all_e)
    closed = sum(1 for e in all_e if e["status"]=="CLOSED")
    canc   = sum(1 for e in all_e if e["status"]=="CANCELLED")
    active = sum(1 for e in all_e if e["status"] in ("PENDING","AGREED","QR_SENT","PAID"))
    disp   = sum(1 for e in all_e if e["status"]=="DISPUTE")
    as_s   = sum(1 for e in all_e if e.get("seller_id")==u.id)
    await update.message.reply_text(
        f"📊 <b>Your Statistics</b>\n\n"
        f"  📋 Total Deals  : <b>{total}</b>\n"
        f"  ✅ Completed    : <b>{closed}</b>\n"
        f"  ❌ Cancelled    : <b>{canc}</b>\n"
        f"  ⏳ Active       : <b>{active}</b>\n"
        f"  ⚠️ Disputes     : <b>{disp}</b>\n\n"
        f"  💼 As Seller    : <b>{as_s}</b>\n"
        f"  🛒 As Buyer     : <b>{total - as_s}</b>\n\n"
        f"  ⭐ Rating       : <b>{p.get('rating',5.0):.1f}/5.0</b>\n"
        f"  🏷️ Fee Discount : <b>{p.get('fee_discount',0):.1f}%</b>\n",
        parse_mode="HTML")

async def cmd_myrating(update: Update, ctx):
    u = update.effective_user; upsert_user(u); p = get_user(u.id)
    rating = p.get("rating",5.0) if p else 5.0
    stars  = "⭐" * round(rating)
    await update.message.reply_text(
        f"⭐ <b>Your Trust Rating</b>\n\n{stars}\n<b>{rating:.1f}/5.0</b>\n\n"
        f"Completed deals: {p.get('deal_count',0) if p else 0}",
        parse_mode="HTML")

async def cmd_myfee(update: Update, ctx):
    u = update.effective_user; upsert_user(u); p = get_user(u.id)
    disc = p.get("fee_discount",0) if p else 0
    eff  = max(0, ESCROW_FEE_PCT - disc)
    await update.message.reply_text(
        f"🏷️ <b>Your Fee</b>\n\n  Standard : {ESCROW_FEE_PCT}%\n  Discount : {disc:.1f}%\n  <b>Effective: {eff:.1f}%</b>",
        parse_mode="HTML")

async def cmd_fees(update: Update, ctx):
    await update.message.reply_text(
        f"💰 <b>Fee Structure</b>\n\n  Standard : <b>{ESCROW_FEE_PCT}%</b>\n"
        "  Max Discount : 50%\n  <b>Fee is non-refundable</b>", parse_mode="HTML")

async def cmd_terms(update: Update, ctx):
    await update.message.reply_text(TERMS_TEXT, parse_mode="HTML")

async def cmd_howitworks(update: Update, ctx):
    await update.message.reply_text(HOWTO_TEXT, parse_mode="HTML")

async def cmd_contact(update: Update, ctx):
    u = update.effective_user; upsert_user(u)
    await update.message.reply_text("📞 Admin notified and will reach you shortly.", parse_mode="HTML")
    await safe_log(ctx, f"📞 Contact: {u.full_name} ({u.id})")

async def cmd_problem(update: Update, ctx):
    u = update.effective_user; upsert_user(u)
    detail = " ".join(ctx.args) if ctx.args else "No details."
    await update.message.reply_text("🆘 Problem reported. Admin notified.", parse_mode="HTML")
    await safe_log(ctx, f"🆘 Problem: {u.full_name} ({u.id})\n{detail}")

async def cmd_dispute(update: Update, ctx):
    u = update.effective_user; upsert_user(u)
    if not ctx.args: await update.message.reply_text("Usage: /dispute <deal_id> [reason]"); return
    try: eid = int(ctx.args[0])
    except: await update.message.reply_text("❌ Invalid ID."); return
    e = get_escrow(eid)
    if not e: await update.message.reply_text("❌ Deal not found."); return
    if u.id not in (e.get("seller_id"), e.get("buyer_id")) and not await is_admin(update, ctx):
        await update.message.reply_text("❌ Only deal parties can raise a dispute."); return
    reason = " ".join(ctx.args[1:]) if len(ctx.args)>1 else "No reason provided."
    dbc("UPDATE escrows SET status='DISPUTE',dispute_at=?,dispute_by=? WHERE id=?",
        (datetime.utcnow().isoformat(), u.id, eid))
    dbc("INSERT INTO disputes(escrow_id,raised_by,reason,ts) VALUES(?,?,?,?)",
        (eid, u.id, reason, datetime.utcnow().isoformat()))
    await update.message.reply_text(
        f"⚠️ <b>Dispute Raised — Deal #{eid}</b>\n\nReason: {reason}\n\nAdmin notified.",
        parse_mode="HTML")
    await safe_log(ctx, f"⚠️ DISPUTE #{eid} by {u.full_name}\n{reason}")

async def cmd_dealinfo(update: Update, ctx):
    u = update.effective_user
    if not ctx.args: await update.message.reply_text("Usage: /dealinfo <id>"); return
    try: eid = int(ctx.args[0])
    except: await update.message.reply_text("❌ Invalid ID."); return
    e = get_escrow(eid)
    if not e: await update.message.reply_text("❌ Deal not found."); return
    if u.id not in (e.get("seller_id"), e.get("buyer_id")) and not await is_admin(update, ctx):
        await update.message.reply_text("❌ Access denied."); return
    await update.message.reply_text(_escrow_caption(e), parse_mode="HTML")

async def cmd_dealterms(update: Update, ctx):
    if not ctx.args: await update.message.reply_text("Usage: /dealterms <id>"); return
    try: eid = int(ctx.args[0])
    except: await update.message.reply_text("❌ Invalid ID."); return
    e = get_escrow(eid)
    if not e: await update.message.reply_text("❌ Deal not found."); return
    t = e.get("terms") or "Standard escrow terms apply."
    await update.message.reply_text(
        f"📜 <b>Deal #{eid} Terms</b>\n\n{t}\n\n⚠️ <i>Fee: {e.get('fee_pct',ESCROW_FEE_PCT)}% — non-refundable.</i>",
        parse_mode="HTML")

async def cmd_deals(update: Update, ctx):
    gid = update.effective_chat.id
    all_e = rows("SELECT * FROM escrows WHERE origin_chat=? AND status IN ('PENDING','AGREED','QR_SENT','PAID','DISPUTE') ORDER BY id DESC", (gid,))
    if not all_e: await update.message.reply_text("✅ No active deals here."); return
    text = "📋 <b>Active Deals</b>\n\n"
    for e in all_e:
        text += (f"{_se(e['status'])} <b>#{e['id']}</b>  "
                 f"{e.get('seller_name','?')} ↔ {e.get('buyer_name') or '?'}\n"
                 f"   💰 {e.get('amount','—')}  |  {e['status']}\n\n")
    await update.message.reply_text(text, parse_mode="HTML")

async def cmd_stopdeal(update: Update, ctx):
    u = update.effective_user; upsert_user(u)
    if not ctx.args: await update.message.reply_text("Usage: /stopdeal <id>"); return
    try: eid = int(ctx.args[0])
    except: await update.message.reply_text("❌ Invalid ID."); return
    e = get_escrow(eid)
    if not e: await update.message.reply_text("❌ Deal not found."); return
    if u.id not in (e.get("seller_id"), e.get("buyer_id")) and not await is_admin(update, ctx):
        await update.message.reply_text("❌ Only deal parties or admin can cancel."); return
    dbc("UPDATE escrows SET status='CANCELLED',cancelled_at=? WHERE id=?",
        (datetime.utcnow().isoformat(), eid))
    gid = e.get("private_gid") or e.get("origin_chat") or update.effective_chat.id
    try:
        await ctx.bot.send_message(gid,
            f"❌ <b>Deal #{eid} Cancelled</b> by {u.mention_html()}.\n"
            "<i>Escrow fee is non-refundable.</i>", parse_mode="HTML")
    except: pass
    await update.message.reply_text(f"❌ Deal #{eid} cancelled.")
    asyncio.create_task(_cleanup_group(ctx, eid))
    await safe_log(ctx, f"❌ Deal #{eid} cancelled by {u.full_name}")

async def cmd_myreferral(update: Update, ctx):
    u = update.effective_user; upsert_user(u); p = get_user(u.id)
    code = p.get("referral_code","") if p else ""
    me   = await ctx.bot.get_me()
    link = f"https://t.me/{me.username}?start=ref_{code}"
    await update.message.reply_text(
        f"🔗 <b>Your Referral Link</b>\n\n<code>{link}</code>\n\n"
        f"👥 Invites: {p.get('invite_count',0) if p else 0}\n"
        f"🏷️ Discount: {p.get('fee_discount',0):.1f}%",
        parse_mode="HTML")

async def cmd_stats(update: Update, ctx):
    c = update.effective_chat
    try: members = await ctx.bot.get_chat_member_count(c.id)
    except: members = "?"
    total  = row("SELECT COUNT(*) c FROM escrows")["c"]
    closed = row("SELECT COUNT(*) c FROM escrows WHERE status='CLOSED'")["c"]
    active = row("SELECT COUNT(*) c FROM escrows WHERE status IN ('PENDING','AGREED','QR_SENT','PAID')")["c"]
    await update.message.reply_text(
        f"📊 <b>Stats</b>\n\n  👥 Members: {members}\n  🔐 Active: {active}\n  ✅ Closed: {closed}\n  📋 Total: {total}",
        parse_mode="HTML")

async def cmd_id(update: Update, ctx):
    u = update.effective_user; c = update.effective_chat
    if update.message.reply_to_message:
        t = update.message.reply_to_message.from_user
        await update.message.reply_text(f"👤 <b>{t.full_name}</b>\n🆔 <code>{t.id}</code>", parse_mode="HTML")
    else:
        await update.message.reply_text(f"👤 You: <code>{u.id}</code>\n💬 Chat: <code>{c.id}</code>", parse_mode="HTML")

# ══════════════════════════════════════════
#  /confirm  — admin close deal
# ══════════════════════════════════════════
async def cmd_confirm(update: Update, ctx):
    """Admin confirms payment received → money is now held safely → deal can proceed."""
    if not await is_admin(update, ctx): await update.message.reply_text("🚫 Admin only."); return
    if not ctx.args: await update.message.reply_text("Usage: /confirm <id>"); return
    try: eid = int(ctx.args[0])
    except: await update.message.reply_text("❌ Invalid ID."); return
    e = get_escrow(eid)
    if not e: await update.message.reply_text("❌ Deal not found."); return
    if e.get("status") not in ("PAID","QR_SENT","AGREED"):
        await update.message.reply_text(f"⚠️ Deal #{eid} status is {e.get('status')} — expected PAID."); return

    now = datetime.utcnow().isoformat()
    dbc("UPDATE escrows SET status='MONEY_HELD', money_held_at=? WHERE id=?", (now, eid))

    pgid = e.get("private_gid") or e.get("origin_chat")
    amount = e.get("amount","—")

    # Notify inside private group
    deal_done_kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Deal Done — Release Money 💸", callback_data=f"dealdone|{eid}")
    ],[
        InlineKeyboardButton("⚠️ Raise Dispute", callback_data=f"dispute|{eid}"),
        InlineKeyboardButton("👮 Add Mediator",  callback_data=f"addadmin|{eid}"),
    ]])
    try:
        await ctx.bot.send_message(pgid,
            f"🏦 <b>Payment Confirmed — Money Held Safely!</b>\n\n"
            f"  🔖 Deal    : <b>#{eid}</b>\n"
            f"  💰 Amount  : <b>{amount}</b>\n"
            f"  👮 Held by : Admin (Escrow)\n\n"
            f"✅ <b>Admin has confirmed receipt of ₹{amount}.</b>\n"
            f"The money is now held safely in escrow.\n\n"
            f"<b>Seller</b> — you may now proceed with delivering the item/service.\n"
            f"<b>Buyer</b> — once you receive it, press the button below to release payment to seller.\n\n"
            f"⚠️ <i>If there is any issue, raise a dispute immediately.</i>",
            parse_mode="HTML", reply_markup=deal_done_kb)
    except Exception as ex:
        log.warning("Confirm msg failed: %s", ex)

    await update.message.reply_text(
        f"✅ <b>Deal #{eid} — Payment Confirmed!</b>\n"
        f"Money held in escrow. Parties notified to proceed.\n"
        f"Waiting for buyer to press 'Deal Done — Release Money'.",
        parse_mode="HTML")
    await safe_log(ctx, f"🏦 #{eid} MONEY_HELD by {update.effective_user.full_name} | Amount: {amount}")


async def cmd_payout(update: Update, ctx):
    """Admin confirms payout sent to seller — triggers group deletion."""
    global PAYOUT_WAIT
    if not await is_admin(update, ctx): await update.message.reply_text("🚫 Admin only."); return
    if not ctx.args: await update.message.reply_text("Usage: /payout <id>"); return
    try: eid = int(ctx.args[0])
    except: await update.message.reply_text("❌ Invalid ID."); return
    e = get_escrow(eid)
    if not e: await update.message.reply_text("❌ Deal not found."); return

    now = datetime.utcnow().isoformat()
    dbc("UPDATE escrows SET status='CLOSED', closed_at=? WHERE id=?", (now, eid))
    dbc("UPDATE users SET deal_count=deal_count+1 WHERE uid IN (?,?)",
        (e.get("seller_id"), e.get("buyer_id")))

    pgid = e.get("private_gid") or e.get("origin_chat")
    PAYOUT_WAIT[eid] = True

    def kb_rate(rated):
        return InlineKeyboardMarkup([[
            InlineKeyboardButton("⭐ 5 — Excellent", callback_data=f"_r5|{eid}|{rated}"),
            InlineKeyboardButton("⭐ 4 — Good",      callback_data=f"_r4|{eid}|{rated}"),
        ],[
            InlineKeyboardButton("⭐ 3 — Average",   callback_data=f"_r3|{eid}|{rated}"),
            InlineKeyboardButton("⭐ 2 — Poor",      callback_data=f"_r2|{eid}|{rated}"),
        ],[
            InlineKeyboardButton("⭐ 1 — Terrible",  callback_data=f"_r1|{eid}|{rated}"),
        ]])

    try:
        await ctx.bot.send_message(pgid,
            f"🎉 <b>Deal #{e['id']} — COMPLETED!</b>\n\n"
            f"  💼 Seller  : {e.get('seller_name')}\n"
            f"  🛒 Buyer   : {e.get('buyer_name') or '—'}\n"
            f"  💰 Amount  : {e.get('amount')}\n\n"
            f"✅ Payment has been released to the seller.\n"
            f"Thank you for using <b>{BOT_NAME}</b>! 🙏\n\n"
            f"<i>This group will be automatically deleted in 5 minutes.</i>",
            parse_mode="HTML")
    except: pass

    for uid, rated in [(e.get("seller_id"), e.get("buyer_id")),
                       (e.get("buyer_id"),  e.get("seller_id"))]:
        if uid and rated:
            try:
                await ctx.bot.send_message(uid,
                    f"✅ <b>Deal #{eid} completed!</b>\n"
                    f"Please rate your experience with your deal partner:",
                    reply_markup=kb_rate(rated))
            except: pass

    await update.message.reply_text(f"✅ Deal #{eid} fully closed. Group deletes in 5 min.")
    await safe_log(ctx, f"✅ #{eid} CLOSED + PAYOUT confirmed by {update.effective_user.full_name}")
    asyncio.create_task(_cleanup_group(ctx, eid, delay=300))

# ══════════════════════════════════════════
#  BOTH AGREED — notify inside private group
# ══════════════════════════════════════════
async def _on_both_agreed(ctx, eid: int):
    """Called when both seller and buyer have agreed inside the private group."""
    e = get_escrow(eid)
    if not e: return
    pgid = e.get("private_gid")
    if not pgid: return

    amount = e.get("amount", "—")

    # Update the pinned deal card
    await _refresh_deal_msg(ctx, e)

    # Send confirmation + QR
    try:
        await ctx.bot.send_message(
            pgid,
            f"🎉 <b>Both parties agreed — Deal #{eid}!</b>\n\n"
            f"  💼 Seller : {e.get('seller_name')}\n"
            f"  🛒 Buyer  : {e.get('buyer_name') or 'Buyer'}\n"
            f"  💰 Amount : <b>{amount}</b>\n\n"
            f"  🏦 UPI ID : <code>{UPI_ID}</code>\n\n"
            "📸 Buyer: pay now and upload the payment screenshot here.\n"
            f"Admin will confirm with /confirm {eid}",
            parse_mode="HTML"
        )
        await _send_qr(ctx, pgid, eid, amount)
    except Exception as ex:
        log.warning("_on_both_agreed msg failed: %s", ex)

    await safe_log(ctx, f"🤝 Both agreed on #{eid} | Amount: {amount}")


# ══════════════════════════════════════════
#  GROUP CLEANUP
# ══════════════════════════════════════════
async def _cleanup_group(ctx, eid, delay=120):
    await asyncio.sleep(delay)
    e = get_escrow(eid)
    if not e: return
    raw_id = e.get("private_raw_id")
    if raw_id: await ub_delete_group(raw_id)
    gid = e.get("origin_chat")
    if gid:
        try:
            img = make_welcome_img("everyone")
            bio = io.BytesIO(img); bio.name="ready.png"
            await ctx.bot.send_photo(gid, photo=InputFile(bio),
                caption=f"♻️ <b>Deal #{eid}</b> processed. Private group deleted.\n"
                        "Type /form to start a new deal.",
                parse_mode="HTML")
        except: pass

# ══════════════════════════════════════════
#  ADMIN COMMANDS
# ══════════════════════════════════════════
async def cmd_auth(update: Update, ctx):
    u = update.effective_user
    if not ctx.args: await update.message.reply_text("Usage: /auth <password>"); return
    if ctx.args[0] == ADMIN_PASSWORD:
        AUTHED.add(u.id)
        await update.message.reply_text("✅ Authenticated as admin.", parse_mode="HTML")
        await safe_log(ctx, f"[AUTH] {u.full_name} ({u.id})")
    else: await update.message.reply_text("❌ Wrong password.")

async def cmd_cancelescrow(update: Update, ctx):
    if not await is_admin(update, ctx): return
    if not ctx.args: await update.message.reply_text("Usage: /cancelescrow <id>"); return
    try: eid = int(ctx.args[0])
    except: return
    e = get_escrow(eid)
    if not e: await update.message.reply_text("Not found."); return
    dbc("UPDATE escrows SET status='CANCELLED',cancelled_at=? WHERE id=?",
        (datetime.utcnow().isoformat(), eid))
    gid = e.get("private_gid") or e.get("origin_chat")
    try: await ctx.bot.send_message(gid, f"❌ Deal #{eid} force-cancelled by admin.", parse_mode="HTML")
    except: pass
    await update.message.reply_text(f"❌ Deal #{eid} cancelled.")
    asyncio.create_task(_cleanup_group(ctx, eid))

async def cmd_setfee(update: Update, ctx):
    global ESCROW_FEE_PCT
    if not await is_admin(update, ctx): return
    if not ctx.args: await update.message.reply_text("Usage: /setfee <percent>"); return
    try:
        ESCROW_FEE_PCT = float(ctx.args[0])
        await update.message.reply_text(f"✅ Global fee: <b>{ESCROW_FEE_PCT}%</b>", parse_mode="HTML")
    except: await update.message.reply_text("❌ Invalid value.")

async def cmd_setuserfee(update: Update, ctx):
    if not await is_admin(update, ctx): return
    if len(ctx.args) < 2: await update.message.reply_text("Usage: /setuserfee <uid> <discount%>"); return
    try:
        uid = int(ctx.args[0]); disc = float(ctx.args[1])
        dbc("UPDATE users SET fee_discount=? WHERE uid=?", (disc, uid))
        await update.message.reply_text(f"✅ User <code>{uid}</code> discount: {disc}%", parse_mode="HTML")
    except: await update.message.reply_text("❌ Invalid.")

async def _get_reply_uid(update):
    return update.message.reply_to_message.from_user.id if update.message.reply_to_message else None

async def cmd_ban(update: Update, ctx):
    if not await is_admin(update, ctx): return
    uid = await _get_reply_uid(update) or (int(ctx.args[0]) if ctx.args else None)
    if not uid: await update.message.reply_text("Reply to user or /ban <id>."); return
    try:
        await ctx.bot.ban_chat_member(update.effective_chat.id, uid)
        dbc("UPDATE users SET is_banned=1 WHERE uid=?", (uid,))
        await update.message.reply_text(f"⛔ Banned <code>{uid}</code>.", parse_mode="HTML")
    except Exception as e: await update.message.reply_text(f"Failed: {e}")

async def cmd_unban(update: Update, ctx):
    if not await is_admin(update, ctx): return
    if not ctx.args: await update.message.reply_text("Usage: /unban <id>"); return
    try:
        uid = int(ctx.args[0])
        await ctx.bot.unban_chat_member(update.effective_chat.id, uid)
        dbc("UPDATE users SET is_banned=0 WHERE uid=?", (uid,))
        await update.message.reply_text(f"✅ Unbanned <code>{uid}</code>.", parse_mode="HTML")
    except Exception as e: await update.message.reply_text(f"Failed: {e}")

async def cmd_kick(update: Update, ctx):
    if not await is_admin(update, ctx): return
    uid = await _get_reply_uid(update)
    if not uid: await update.message.reply_text("Reply to a user."); return
    try:
        await ctx.bot.ban_chat_member(update.effective_chat.id, uid,
            until_date=datetime.utcnow()+timedelta(seconds=35))
        await ctx.bot.unban_chat_member(update.effective_chat.id, uid)
        await update.message.reply_text("🚪 Kicked.")
    except Exception as e: await update.message.reply_text(f"Failed: {e}")

async def cmd_mute(update: Update, ctx):
    if not await is_admin(update, ctx): return
    uid = await _get_reply_uid(update)
    if not uid: await update.message.reply_text("Reply to a user."); return
    try:
        await ctx.bot.restrict_chat_member(update.effective_chat.id, uid,
            ChatPermissions(can_send_messages=False))
        await update.message.reply_text("🔇 Muted.")
    except Exception as e: await update.message.reply_text(f"Failed: {e}")

async def cmd_unmute(update: Update, ctx):
    if not await is_admin(update, ctx): return
    uid = await _get_reply_uid(update)
    if not uid: await update.message.reply_text("Reply to a user."); return
    try:
        await ctx.bot.restrict_chat_member(update.effective_chat.id, uid,
            ChatPermissions(can_send_messages=True, can_send_media_messages=True,
                can_send_other_messages=True, can_add_web_page_previews=True))
        await update.message.reply_text("🔊 Unmuted.")
    except Exception as e: await update.message.reply_text(f"Failed: {e}")

async def cmd_warn(update: Update, ctx):
    if not await is_admin(update, ctx): return
    uid = await _get_reply_uid(update)
    if not uid or not ctx.args: await update.message.reply_text("Reply + /warn <reason>"); return
    reason = " ".join(ctx.args)
    dbc("INSERT INTO warnings(chat_id,user_id,warned_by,reason,ts) VALUES(?,?,?,?,?)",
        (update.effective_chat.id, uid, update.effective_user.id, reason, datetime.utcnow().isoformat()))
    count = row("SELECT COUNT(*) c FROM warnings WHERE chat_id=? AND user_id=?",
                (update.effective_chat.id, uid))["c"]
    t = update.message.reply_to_message.from_user
    await update.message.reply_text(
        f"⚠️ {t.mention_html()} warned ({count} total)\n<i>{reason}</i>", parse_mode="HTML")

async def cmd_warnings(update: Update, ctx):
    uid = await _get_reply_uid(update)
    if not uid: await update.message.reply_text("Reply to a user."); return
    ws = rows("SELECT * FROM warnings WHERE chat_id=? AND user_id=? ORDER BY id DESC",
              (update.effective_chat.id, uid))
    if not ws: await update.message.reply_text("No warnings."); return
    t = update.message.reply_to_message.from_user
    text = f"⚠️ <b>Warnings for {t.full_name}</b>\n\n"
    for w in ws: text += f"  • {w['ts'][:10]} — {w['reason']}\n"
    await update.message.reply_text(text, parse_mode="HTML")

async def cmd_clearwarn(update: Update, ctx):
    if not await is_admin(update, ctx): return
    uid = await _get_reply_uid(update)
    if not uid: await update.message.reply_text("Reply to a user."); return
    dbc("DELETE FROM warnings WHERE chat_id=? AND user_id=?", (update.effective_chat.id, uid))
    await update.message.reply_text("✅ Warnings cleared.")

async def cmd_promote(update: Update, ctx):
    if not await is_admin(update, ctx): return
    uid = await _get_reply_uid(update)
    if not uid: await update.message.reply_text("Reply to a user."); return
    try:
        await ctx.bot.promote_chat_member(update.effective_chat.id, uid,
            can_change_info=True, can_delete_messages=True,
            can_restrict_members=True, can_pin_messages=True, can_invite_users=True)
        await update.message.reply_text("⭐ Promoted.")
    except Exception as e: await update.message.reply_text(f"Failed: {e}")

async def cmd_demote(update: Update, ctx):
    if not await is_admin(update, ctx): return
    uid = await _get_reply_uid(update)
    if not uid: await update.message.reply_text("Reply to a user."); return
    try:
        await ctx.bot.promote_chat_member(update.effective_chat.id, uid,
            can_change_info=False, can_delete_messages=False,
            can_restrict_members=False, can_pin_messages=False, can_invite_users=False)
        await update.message.reply_text("🔻 Demoted.")
    except Exception as e: await update.message.reply_text(f"Failed: {e}")

async def cmd_pin(update: Update, ctx):
    if not await is_admin(update, ctx): return
    if not update.message.reply_to_message: await update.message.reply_text("Reply to a message."); return
    try:
        await ctx.bot.pin_chat_message(update.effective_chat.id,
            update.message.reply_to_message.message_id)
        await update.message.reply_text("📌 Pinned.")
    except Exception as e: await update.message.reply_text(f"Failed: {e}")

async def cmd_unpin(update: Update, ctx):
    if not await is_admin(update, ctx): return
    try:
        await ctx.bot.unpin_all_chat_messages(update.effective_chat.id)
        await update.message.reply_text("📌 All unpinned.")
    except Exception as e: await update.message.reply_text(f"Failed: {e}")

async def cmd_lock(update: Update, ctx):
    if not await is_admin(update, ctx): return
    try:
        await ctx.bot.set_chat_permissions(update.effective_chat.id, ChatPermissions(can_send_messages=False))
        await update.message.reply_text("🔒 Locked.")
    except Exception as e: await update.message.reply_text(f"Failed: {e}")

async def cmd_unlock(update: Update, ctx):
    if not await is_admin(update, ctx): return
    try:
        await ctx.bot.set_chat_permissions(update.effective_chat.id,
            ChatPermissions(can_send_messages=True, can_send_media_messages=True,
                can_send_other_messages=True, can_add_web_page_previews=True))
        await update.message.reply_text("🔓 Unlocked.")
    except Exception as e: await update.message.reply_text(f"Failed: {e}")

async def cmd_purge(update: Update, ctx):
    if not await is_admin(update, ctx): return
    if not update.message.reply_to_message: await update.message.reply_text("Reply to start."); return
    count = int(ctx.args[0]) if ctx.args else 50
    start = update.message.reply_to_message.message_id; deleted = 0
    for i in range(start, start+count):
        try: await ctx.bot.delete_message(update.effective_chat.id, i); deleted += 1
        except: pass
    await update.message.reply_text(f"🧹 Purged ~{deleted} messages.")

async def cmd_del(update: Update, ctx):
    if not await is_admin(update, ctx): return
    if not update.message.reply_to_message: await update.message.reply_text("Reply to a message."); return
    try: await ctx.bot.delete_message(update.effective_chat.id,
        update.message.reply_to_message.message_id)
    except Exception as e: await update.message.reply_text(f"Failed: {e}")

async def cmd_slowmode(update: Update, ctx):
    if not await is_admin(update, ctx): return
    if not ctx.args: await update.message.reply_text("Usage: /slowmode <sec>"); return
    try:
        await ctx.bot.set_chat_slow_mode_delay(update.effective_chat.id, int(ctx.args[0]))
        await update.message.reply_text(f"⏱ Slowmode: {ctx.args[0]}s")
    except Exception as e: await update.message.reply_text(f"Failed: {e}")

async def cmd_announce(update: Update, ctx):
    if not await is_admin(update, ctx): return
    if not ctx.args: await update.message.reply_text("Usage: /announce <text>"); return
    txt = " ".join(ctx.args)
    await ctx.bot.send_message(update.effective_chat.id,
        f"📣 <b>Announcement</b>\n\n{txt}\n\n— {update.effective_user.mention_html()}",
        parse_mode="HTML")

async def cmd_poll(update: Update, ctx):
    if not await is_admin(update, ctx): return
    if not ctx.args: await update.message.reply_text("Usage: /poll Q|opt1|opt2"); return
    parts = " ".join(ctx.args).split("|")
    if len(parts) < 3: await update.message.reply_text("Need at least 2 options."); return
    await ctx.bot.send_poll(update.effective_chat.id, parts[0].strip(),
        [p.strip() for p in parts[1:]], is_anonymous=False)

async def cmd_broadcast(update: Update, ctx):
    if not await is_admin(update, ctx): return
    if not ctx.args: await update.message.reply_text("Usage: /broadcast <text>"); return
    txt = " ".join(ctx.args)
    all_users = rows("SELECT uid FROM users WHERE is_banned=0")
    sent = failed = 0
    for usr in all_users:
        try:
            await ctx.bot.send_message(usr["uid"],
                f"📣 <b>Announcement</b>\n\n{txt}", parse_mode="HTML"); sent += 1
        except: failed += 1
    await update.message.reply_text(f"📣 Sent: {sent} | Failed: {failed}")

async def cmd_userstats(update: Update, ctx):
    if not await is_admin(update, ctx): return
    total_u = row("SELECT COUNT(*) c FROM users")["c"]
    banned  = row("SELECT COUNT(*) c FROM users WHERE is_banned=1")["c"]
    total   = row("SELECT COUNT(*) c FROM escrows")["c"]
    closed  = row("SELECT COUNT(*) c FROM escrows WHERE status='CLOSED'")["c"]
    active  = row("SELECT COUNT(*) c FROM escrows WHERE status IN ('PENDING','AGREED','QR_SENT','PAID')")["c"]
    await update.message.reply_text(
        f"📊 <b>Bot Statistics</b>\n\n"
        f"  👥 Users    : {total_u}\n  ⛔ Banned   : {banned}\n\n"
        f"  🔐 Escrows  : {total}\n  ✅ Closed   : {closed}\n  ⏳ Active   : {active}",
        parse_mode="HTML")

async def cmd_alldeals(update: Update, ctx):
    if not await is_admin(update, ctx): return
    all_e = rows("SELECT * FROM escrows ORDER BY id DESC LIMIT 30")
    if not all_e: await update.message.reply_text("No deals."); return
    text = "📋 <b>All Deals (last 30)</b>\n\n"
    for e in all_e:
        text += f"{_se(e['status'])} #{e['id']} — {e.get('seller_name','?')} ↔ {e.get('buyer_name') or '?'} — {e.get('amount','?')} — {e['status']}\n"
    await update.message.reply_text(text, parse_mode="HTML")

async def cmd_pendingdeals(update: Update, ctx):
    if not await is_admin(update, ctx): return
    all_e = rows("SELECT * FROM escrows WHERE status IN ('PENDING','AGREED','QR_SENT','PAID','DISPUTE') ORDER BY id DESC")
    if not all_e: await update.message.reply_text("✅ No pending deals."); return
    text = "⏳ <b>Pending Deals</b>\n\n"
    for e in all_e:
        text += f"{_se(e['status'])} #{e['id']} — {e.get('seller_name','?')} ↔ {e.get('buyer_name') or '?'} — {e.get('amount','?')}\n"
    await update.message.reply_text(text, parse_mode="HTML")

async def cmd_logs(update: Update, ctx):
    if not await is_admin(update, ctx): return
    all_logs = rows("SELECT * FROM logs ORDER BY id DESC LIMIT 20")
    if not all_logs: await update.message.reply_text("No logs."); return
    text = "📋 <b>Recent Logs</b>\n\n"
    for l in all_logs:
        text += f"  [{l['ts'][:16]}] {l['event']}: {l['detail'][:60]}\n"
    await update.message.reply_text(text, parse_mode="HTML")

async def cmd_resolvedispute(update: Update, ctx):
    if not await is_admin(update, ctx): return
    if not ctx.args: await update.message.reply_text("Usage: /resolvedispute <id> [resolution]"); return
    try: eid = int(ctx.args[0])
    except: await update.message.reply_text("❌ Invalid ID."); return
    resolution = " ".join(ctx.args[1:]) if len(ctx.args) > 1 else "Resolved by admin."
    dbc("UPDATE escrows SET status='CLOSED',closed_at=? WHERE id=?", (datetime.utcnow().isoformat(), eid))
    dbc("UPDATE disputes SET status='RESOLVED',resolved_by=?,resolution=? WHERE escrow_id=?",
        (update.effective_user.id, resolution, eid))
    e = get_escrow(eid)
    gid = e.get("private_gid") or e.get("origin_chat") if e else None
    if gid:
        try: await ctx.bot.send_message(gid,
            f"⚖️ <b>Dispute #{eid} Resolved</b>\n\n{resolution}", parse_mode="HTML")
        except: pass
    await update.message.reply_text(f"✅ Dispute on #{eid} resolved.")
    asyncio.create_task(_cleanup_group(ctx, eid))

async def cmd_addmediator(update: Update, ctx):
    if not await is_admin(update, ctx): return
    if not ctx.args: await update.message.reply_text("Usage: /addmediator <deal_id>"); return
    try: eid = int(ctx.args[0])
    except: return
    e = get_escrow(eid)
    if not e: await update.message.reply_text("Not found."); return
    raw_id = e.get("private_raw_id"); added = []
    if raw_id and USERBOT_ENABLED:
        for aid in ADMIN_IDS:
            ok = await ub_add_user(raw_id, aid)
            if ok: added.append(aid)
    dbc("UPDATE escrows SET admin_added=1 WHERE id=?", (eid,))
    await update.message.reply_text(
        f"👮 Admin added to Deal #{eid}. Added: {len(added)}")

async def cmd_setterms(update: Update, ctx):
    if not await is_admin(update, ctx): return
    if not ctx.args: await update.message.reply_text("Usage: /setterms <text>"); return
    dblog("SET_TERMS", " ".join(ctx.args))
    await update.message.reply_text("✅ Default terms updated.")

async def cmd_botstats(update: Update, ctx): await cmd_userstats(update, ctx)


async def cmd_dbbackup(update: Update, ctx):
    """Admin: download a backup of the database."""
    if not await is_admin(update, ctx): return
    db_path = _get_db_path()
    if not os.path.exists(db_path):
        await update.message.reply_text("❌ Database file not found."); return
    try:
        with open(db_path, "rb") as f:
            data = f.read()
        bio = io.BytesIO(data); bio.name = "escrow_backup.db"
        await update.message.reply_document(
            document=InputFile(bio),
            caption=f"🗄️ Database backup\n{len(data)//1024} KB\n{datetime.utcnow().isoformat()[:16]} UTC"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Backup failed: {e}")


async def cmd_dbinfo(update: Update, ctx):
    """Admin: show database info."""
    if not await is_admin(update, ctx): return
    db_path = _get_db_path()
    exists  = os.path.exists(db_path)
    size    = os.path.getsize(db_path) // 1024 if exists else 0
    on_disk = os.path.isdir("/var/data")
    total_u = row("SELECT COUNT(*) c FROM users")["c"]
    total_e = row("SELECT COUNT(*) c FROM escrows")["c"]
    await update.message.reply_text(
        f"🗄️ <b>Database Info</b>\n\n"
        f"  📁 Path          : <code>{db_path}</code>\n"
        f"  💾 Size          : {size} KB\n"
        f"  🔒 Persistent    : {'✅ Yes (/var/data)' if on_disk else '❌ No — add Render Disk!'}\n\n"
        f"  👥 Users         : {total_u}\n"
        f"  🔐 Escrows       : {total_e}\n",
        parse_mode="HTML"
    )

# ══════════════════════════════════════════
#  NEW MEMBER WELCOME
# ══════════════════════════════════════════
async def new_member_handler(update: Update, ctx):
    for m in update.message.new_chat_members:
        upsert_user(m)
        img = make_welcome_img(m.first_name)
        bio = io.BytesIO(img); bio.name="welcome.png"
        kb  = InlineKeyboardMarkup([[
            InlineKeyboardButton("📋 Start Deal", callback_data="start_escrow_noop"),
            InlineKeyboardButton("❓ Help",        callback_data="show_help"),
        ]])
        try:
            await ctx.bot.send_photo(update.effective_chat.id, photo=InputFile(bio),
                caption=(
                    f"👋 <b>Welcome, {m.mention_html()}!</b>\n\n"
                    "I'm your escrow bot. Type <code>/form</code> here to start a secure deal.\n\n"
                    "Every deal gets a <b>private encrypted group</b> — buyer &amp; seller only."
                ), parse_mode="HTML", reply_markup=kb)
        except:
            try: await ctx.bot.send_message(update.effective_chat.id,
                f"👋 Welcome {m.mention_html()}! Type /form to start an escrow.", parse_mode="HTML")
            except: pass

# handle start_escrow_noop in groups
async def noop_cb(update: Update, ctx):
    q = update.callback_query; await q.answer()
    if q.data == "start_escrow_noop":
        await q.message.reply_text("Type <code>/form</code> in this group to start a deal.", parse_mode="HTML")

# ══════════════════════════════════════════
#  KEEP-ALIVE
# ══════════════════════════════════════════
async def _health(req): return web.Response(text="✅ Alive")

async def start_web():
    app = web.Application()
    app.router.add_get("/", _health)
    app.router.add_get("/health", _health)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    log.info("HTTP server on port %d", PORT)

async def ping_loop():
    """
    Keep-alive pinger.
    Pings RENDER_URL every PING_INTERVAL seconds so Render free tier never sleeps.
    Also pings every 14 minutes (just under Render's 15-min timeout).
    """
    if not RENDER_URL:
        log.warning("RENDER_URL not set — keep-alive disabled. Bot may sleep on Render free tier.")
        return
    await asyncio.sleep(30)   # let server start first
    interval = min(PING_INTERVAL, 840)  # never exceed 14 min
    consecutive_fails = 0
    async with aiohttp.ClientSession() as s:
        while True:
            try:
                async with s.get(
                    f"{RENDER_URL}/health",
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as r:
                    log.info("✅ Keep-alive ping → %s (%d)", RENDER_URL, r.status)
                    consecutive_fails = 0
            except Exception as e:
                consecutive_fails += 1
                log.warning("❌ Ping failed (%dx): %s", consecutive_fails, e)
            await asyncio.sleep(interval)

# ══════════════════════════════════════════
#  BOT COMMANDS MENU
# ══════════════════════════════════════════
BOT_COMMANDS = [
    BotCommand("start",          "🏠 Start the bot"),
    BotCommand("help",           "❓ All commands"),
    BotCommand("form",           "📋 Start escrow deal (in group)"),
    BotCommand("escrow",         "🔐 Start escrow deal (in group)"),
    BotCommand("deals",          "📊 Active deals"),
    BotCommand("dealinfo",       "🔖 Deal details"),
    BotCommand("dealterms",      "📜 Deal terms"),
    BotCommand("stopdeal",       "❌ Cancel a deal"),
    BotCommand("dispute",        "⚠️ Raise a dispute"),
    BotCommand("confirm",        "✅ Confirm payment received (admin)"),
    BotCommand("payout",         "💸 Confirm payout sent (admin)"),
    BotCommand("myprofile",      "👤 Your profile"),
    BotCommand("mytransactions", "📋 All transactions"),
    BotCommand("mydeals",        "⏳ Active deals"),
    BotCommand("myhistory",      "📜 Deal history"),
    BotCommand("mystats",        "📊 Statistics"),
    BotCommand("myrating",       "⭐ Trust rating"),
    BotCommand("myfee",          "🏷️ Your fee rate"),
    BotCommand("myreferral",     "🔗 Referral link"),
    BotCommand("fees",           "💰 Fee structure"),
    BotCommand("terms",          "📜 Terms & conditions"),
    BotCommand("howitworks",     "🔐 How it works"),
    BotCommand("contact",        "📞 Contact admin"),
    BotCommand("problem",        "🆘 Report problem"),
    BotCommand("stats",          "📊 Group stats"),
    BotCommand("id",             "🆔 Get user/chat ID"),
    BotCommand("auth",           "🔑 Admin login"),
]

# ══════════════════════════════════════════
#  BUILD APP
# ══════════════════════════════════════════
def build_app():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    H = app.add_handler
    H(CommandHandler("start",          cmd_start))
    H(CommandHandler("help",           cmd_help))
    H(CommandHandler("form",           cmd_form))
    H(CommandHandler("escrow",         cmd_escrow))
    H(CommandHandler("deals",          cmd_deals))
    H(CommandHandler("dealinfo",       cmd_dealinfo))
    H(CommandHandler("dealterms",      cmd_dealterms))
    H(CommandHandler("stopdeal",       cmd_stopdeal))
    H(CommandHandler("dispute",        cmd_dispute))
    H(CommandHandler("confirm",        cmd_confirm))
    H(CommandHandler("payout",         cmd_payout))
    H(CommandHandler("myprofile",      cmd_myprofile))
    H(CommandHandler("mytransactions", cmd_mytransactions))
    H(CommandHandler("mydeals",        cmd_mydeals))
    H(CommandHandler("myhistory",      cmd_myhistory))
    H(CommandHandler("mystats",        cmd_mystats))
    H(CommandHandler("myrating",       cmd_myrating))
    H(CommandHandler("myfee",          cmd_myfee))
    H(CommandHandler("myreferral",     cmd_myreferral))
    H(CommandHandler("fees",           cmd_fees))
    H(CommandHandler("terms",          cmd_terms))
    H(CommandHandler("howitworks",     cmd_howitworks))
    H(CommandHandler("contact",        cmd_contact))
    H(CommandHandler("problem",        cmd_problem))
    H(CommandHandler("stats",          cmd_stats))
    H(CommandHandler("id",             cmd_id))
    H(CommandHandler("auth",           cmd_auth))
    H(CommandHandler("cancelescrow",   cmd_cancelescrow))
    H(CommandHandler("setfee",         cmd_setfee))
    H(CommandHandler("setuserfee",     cmd_setuserfee))
    H(CommandHandler("ban",            cmd_ban))
    H(CommandHandler("unban",          cmd_unban))
    H(CommandHandler("kick",           cmd_kick))
    H(CommandHandler("mute",           cmd_mute))
    H(CommandHandler("unmute",         cmd_unmute))
    H(CommandHandler("warn",           cmd_warn))
    H(CommandHandler("warnings",       cmd_warnings))
    H(CommandHandler("clearwarn",      cmd_clearwarn))
    H(CommandHandler("promote",        cmd_promote))
    H(CommandHandler("demote",         cmd_demote))
    H(CommandHandler("pin",            cmd_pin))
    H(CommandHandler("unpin",          cmd_unpin))
    H(CommandHandler("lock",           cmd_lock))
    H(CommandHandler("unlock",         cmd_unlock))
    H(CommandHandler("purge",          cmd_purge))
    H(CommandHandler("del",            cmd_del))
    H(CommandHandler("slowmode",       cmd_slowmode))
    H(CommandHandler("announce",       cmd_announce))
    H(CommandHandler("poll",           cmd_poll))
    H(CommandHandler("broadcast",      cmd_broadcast))
    H(CommandHandler("userstats",      cmd_userstats))
    H(CommandHandler("botstats",       cmd_botstats))
    H(CommandHandler("alldeals",       cmd_alldeals))
    H(CommandHandler("pendingdeals",   cmd_pendingdeals))
    H(CommandHandler("logs",           cmd_logs))
    H(CommandHandler("resolvedispute", cmd_resolvedispute))
    H(CommandHandler("addmediator",    cmd_addmediator))
    H(CommandHandler("setterms",       cmd_setterms))
    H(CommandHandler("dbbackup",       cmd_dbbackup))
    H(CommandHandler("dbinfo",         cmd_dbinfo))
    H(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    H(MessageHandler(filters.PHOTO | filters.Document.IMAGE, photo_handler))
    H(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_member_handler))
    H(CallbackQueryHandler(noop_cb, pattern="^start_escrow_noop$"))
    H(CallbackQueryHandler(callback_handler))

    # ── Load all plugins from plugins/ folder ──────────
    db_funcs = {"row": row, "rows": rows, "dbc": dbc, "get_escrow": get_escrow, "get_user": get_user}
    loaded, failed = _load_plugins(app, db_funcs)
    log.info("Plugins loaded: %s", loaded)
    if failed:
        log.warning("Failed plugins: %s", failed)

    return app

# ══════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════
async def main():
    global userbot, BOT_ID, BOT_USERNAME

    # 1. Telethon userbot
    if USERBOT_ENABLED:
        log.info("Starting userbot…")
        try:
            if TELETHON_SESSION:
                from telethon.sessions import StringSession
                userbot = TelegramClient(StringSession(TELETHON_SESSION), TG_API_ID, TG_API_HASH)
            else:
                userbot = TelegramClient("userbot", TG_API_ID, TG_API_HASH)
            await userbot.start()
            me = await userbot.get_me()
            log.info("✅ Userbot: %s (%s)", me.first_name, me.id)
        except Exception as e:
            log.error("❌ Userbot failed: %s — DM fallback mode", e)
            userbot = None
    else:
        log.warning("Userbot disabled — set TG_API_ID + TG_API_HASH + TELETHON_SESSION")

    # 2. HTTP + ping
    await start_web()
    asyncio.create_task(ping_loop())

    # 3. PTB bot
    tg_app = build_app()
    bot_info = await tg_app.bot.get_me()
    BOT_ID       = bot_info.id
    BOT_USERNAME = bot_info.username
    log.info("Bot: @%s (id=%s)", bot_info.username, BOT_ID)

    try: await tg_app.bot.set_my_commands(BOT_COMMANDS)
    except Exception as e: log.warning("Commands: %s", e)

    log.info("🚀 Escrower Bot running!")
    await tg_app.initialize()
    await tg_app.start()
    await tg_app.updater.start_polling(drop_pending_updates=True)

    try: await asyncio.Event().wait()
    finally:
        await tg_app.updater.stop()
        await tg_app.stop()
        await tg_app.shutdown()
        if userbot: await userbot.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
