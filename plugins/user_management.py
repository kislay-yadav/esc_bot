"""
Plugin: User Management
========================
Admin commands for managing users.
Add to bot by keeping this file in plugins/.
Remove by deleting or renaming to .disabled

Commands added:
  /userlist    — paginated list of all users
  /userinfo    — detailed info on a user
  /usersearch  — search user by name/username
  /topusers    — top users by deal count
  /toprating   — top users by rating
  /bannedlist  — list of banned users
  /activeusers — users active in last 7 days
"""

import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, ContextTypes

log = logging.getLogger("UserMgmt")

_db = None   # injected by register()


def register(app, db_funcs: dict):
    global _db
    _db = db_funcs
    app.add_handler(CommandHandler("userlist",    cmd_userlist))
    app.add_handler(CommandHandler("userinfo",    cmd_userinfo))
    app.add_handler(CommandHandler("usersearch",  cmd_usersearch))
    app.add_handler(CommandHandler("topusers",    cmd_topusers))
    app.add_handler(CommandHandler("toprating",   cmd_toprating))
    app.add_handler(CommandHandler("bannedlist",  cmd_bannedlist))
    app.add_handler(CommandHandler("activeusers", cmd_activeusers))
    log.info("User management plugin registered")


async def _require_admin(update: Update, ctx) -> bool:
    from config.settings import ADMIN_IDS
    uid = update.effective_user.id
    if uid in ADMIN_IDS: return True
    try:
        m = await update.effective_chat.get_member(uid)
        if m.status in ("administrator","creator"): return True
    except: pass
    await update.message.reply_text("🚫 Admin only."); return False


async def cmd_userlist(update: Update, ctx):
    """Paginated user list."""
    if not await _require_admin(update, ctx): return
    page = int(ctx.args[0]) if ctx.args else 1
    per  = 20
    offset = (page-1) * per
    users = _db["rows"](
        "SELECT uid, full_name, username, deal_count, rating, is_banned, joined "
        "FROM users ORDER BY joined DESC LIMIT ? OFFSET ?", (per, offset))
    total = _db["row"]("SELECT COUNT(*) c FROM users")["c"]
    pages = (total + per - 1) // per

    text = f"👥 <b>User List — Page {page}/{pages}</b> ({total} total)\n\n"
    for u in users:
        banned = "⛔" if u.get("is_banned") else "✅"
        name   = (u.get("full_name") or "?")[:20]
        uname  = f"@{u['username']}" if u.get("username") else "—"
        text  += (f"{banned} <code>{u['uid']}</code>  {name}  {uname}\n"
                  f"   Deals: {u.get('deal_count',0)}  Rating: {u.get('rating',5.0):.1f}⭐\n\n")

    kb = []
    if page > 1:    kb.append(InlineKeyboardButton(f"◀ Page {page-1}", callback_data=f"ul|{page-1}"))
    if page < pages: kb.append(InlineKeyboardButton(f"Page {page+1} ▶", callback_data=f"ul|{page+1}"))
    markup = InlineKeyboardMarkup([kb]) if kb else None
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=markup)


async def cmd_userinfo(update: Update, ctx):
    """Detailed info on a user by ID or reply."""
    if not await _require_admin(update, ctx): return
    uid = None
    if update.message.reply_to_message:
        uid = update.message.reply_to_message.from_user.id
    elif ctx.args:
        try: uid = int(ctx.args[0])
        except: await update.message.reply_text("Usage: /userinfo <uid> or reply to user"); return
    if not uid: await update.message.reply_text("Provide uid or reply to user."); return

    u = _db["row"]("SELECT * FROM users WHERE uid=?", (uid,))
    if not u: await update.message.reply_text(f"❌ User {uid} not found."); return

    total  = _db["row"]("SELECT COUNT(*) c FROM escrows WHERE seller_id=? OR buyer_id=?", (uid,uid))["c"]
    closed = _db["row"]("SELECT COUNT(*) c FROM escrows WHERE (seller_id=? OR buyer_id=?) AND status='CLOSED'", (uid,uid))["c"]
    active = _db["row"]("SELECT COUNT(*) c FROM escrows WHERE (seller_id=? OR buyer_id=?) AND status IN ('PENDING','AGREED','QR_SENT','PAID','MONEY_HELD')", (uid,uid))["c"]
    warns  = _db["row"]("SELECT COUNT(*) c FROM warnings WHERE user_id=?", (uid,))["c"]

    text = (
        f"👤 <b>User Info</b>\n\n"
        f"  🆔 ID           : <code>{uid}</code>\n"
        f"  🏷️ Name         : {u.get('full_name','—')}\n"
        f"  📌 Username     : @{u.get('username') or 'N/A'}\n"
        f"  📅 Joined       : {(u.get('joined') or '')[:10]}\n"
        f"  🕐 Last Seen    : {(u.get('last_seen') or '')[:16]}\n\n"
        f"  📊 Total Deals  : {total}\n"
        f"  ✅ Completed    : {closed}\n"
        f"  ⏳ Active       : {active}\n"
        f"  ⭐ Rating       : {u.get('rating',5.0):.1f}/5.0\n"
        f"  🏷️ Fee Discount : {u.get('fee_discount',0):.1f}%\n"
        f"  👥 Invites      : {u.get('invite_count',0)}\n"
        f"  ⚠️ Warnings     : {warns}\n"
        f"  ⛔ Banned       : {'Yes' if u.get('is_banned') else 'No'}\n"
        f"  🔗 Referral     : <code>{u.get('referral_code','—')}</code>\n"
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⛔ Ban",  callback_data=f"admin_ban|{uid}"),
        InlineKeyboardButton("✅ Unban",callback_data=f"admin_unban|{uid}"),
    ]])
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)


async def cmd_usersearch(update: Update, ctx):
    """Search user by name or username."""
    if not await _require_admin(update, ctx): return
    if not ctx.args: await update.message.reply_text("Usage: /usersearch <name or @username>"); return
    q = " ".join(ctx.args).lstrip("@")
    users = _db["rows"](
        "SELECT uid, full_name, username, deal_count, rating, is_banned "
        "FROM users WHERE full_name LIKE ? OR username LIKE ? LIMIT 15",
        (f"%{q}%", f"%{q}%"))
    if not users: await update.message.reply_text(f"❌ No users found for '{q}'."); return
    text = f"🔍 <b>Search: '{q}'</b> — {len(users)} result(s)\n\n"
    for u in users:
        banned = "⛔" if u.get("is_banned") else "✅"
        text += (f"{banned} <code>{u['uid']}</code>  {u.get('full_name','?')[:20]}  "
                 f"@{u.get('username') or '—'}  "
                 f"Deals:{u.get('deal_count',0)}  ⭐{u.get('rating',5.0):.1f}\n")
    await update.message.reply_text(text, parse_mode="HTML")


async def cmd_topusers(update: Update, ctx):
    """Top users by deal count."""
    if not await _require_admin(update, ctx): return
    users = _db["rows"](
        "SELECT uid, full_name, username, deal_count, rating "
        "FROM users ORDER BY deal_count DESC LIMIT 15")
    text = "🏆 <b>Top Users by Deal Count</b>\n\n"
    for i, u in enumerate(users, 1):
        medal = ["🥇","🥈","🥉"].get(i-1, f"{i}.")  if i <= 3 else f"{i}."
        text += (f"{medal} {u.get('full_name','?')[:18]}  "
                 f"Deals: <b>{u.get('deal_count',0)}</b>  "
                 f"⭐{u.get('rating',5.0):.1f}\n")
    await update.message.reply_text(text, parse_mode="HTML")


async def cmd_toprating(update: Update, ctx):
    """Top users by trust rating."""
    if not await _require_admin(update, ctx): return
    users = _db["rows"](
        "SELECT uid, full_name, username, deal_count, rating "
        "FROM users WHERE deal_count > 0 ORDER BY rating DESC LIMIT 15")
    text = "⭐ <b>Top Trusted Users</b>\n\n"
    for i, u in enumerate(users, 1):
        medal = ["🥇","🥈","🥉"][i-1] if i <= 3 else f"{i}."
        text += (f"{medal} {u.get('full_name','?')[:18]}  "
                 f"⭐ <b>{u.get('rating',5.0):.1f}</b>  "
                 f"Deals: {u.get('deal_count',0)}\n")
    await update.message.reply_text(text, parse_mode="HTML")


async def cmd_bannedlist(update: Update, ctx):
    """List all banned users."""
    if not await _require_admin(update, ctx): return
    users = _db["rows"](
        "SELECT uid, full_name, username FROM users WHERE is_banned=1")
    if not users: await update.message.reply_text("✅ No banned users."); return
    text = f"⛔ <b>Banned Users ({len(users)})</b>\n\n"
    for u in users:
        text += f"  <code>{u['uid']}</code>  {u.get('full_name','?')[:20]}  @{u.get('username') or '—'}\n"
    await update.message.reply_text(text, parse_mode="HTML")


async def cmd_activeusers(update: Update, ctx):
    """Users active in last 7 days."""
    if not await _require_admin(update, ctx): return
    cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()
    users = _db["rows"](
        "SELECT uid, full_name, username, last_seen, deal_count "
        "FROM users WHERE last_seen > ? AND is_banned=0 "
        "ORDER BY last_seen DESC LIMIT 30", (cutoff,))
    text = f"🟢 <b>Active Users (last 7 days) — {len(users)}</b>\n\n"
    for u in users:
        text += (f"  {u.get('full_name','?')[:18]}  "
                 f"@{u.get('username') or '—'}  "
                 f"Seen: {(u.get('last_seen') or '')[:10]}\n")
    await update.message.reply_text(text, parse_mode="HTML")
