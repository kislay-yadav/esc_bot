"""
Plugin: Force Subscribe
========================
Adds force-subscribe-to-channel gate before bot use, plus admin commands
to manage it. Self-contained — does not modify main.py's fragile f-strings.

Commands added:
  /setforcesub @channel [invite_link]   (admin)
  /removeforcesub                        (admin)
  /checkforcesub                         (admin)

Also exposes:
  is_subscribed(bot, uid)  -> bool          (call this from main.py if needed)
  force_sub_markup()       -> InlineKeyboardMarkup
"""

import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler

log = logging.getLogger("ForceSub")

_db = None

# In-memory state (simple — survives until restart; fine for this feature)
STATE = {
    "channel": "",     # e.g. "@mychannel" or "-1001234567890"
    "link":    "",      # invite link shown to user
    "enabled": False,
}


def register(app, db_funcs: dict):
    global _db
    _db = db_funcs
    app.add_handler(CommandHandler("setforcesub",    cmd_setforcesub))
    app.add_handler(CommandHandler("removeforcesub", cmd_removeforcesub))
    app.add_handler(CommandHandler("checkforcesub",  cmd_checkforcesub))
    app.add_handler(CallbackQueryHandler(cb_check_sub, pattern="^fs_check$"))
    log.info("ForceSub plugin registered")


async def _is_admin(update) -> bool:
    from config.settings import ADMIN_IDS
    uid = update.effective_user.id
    if uid in ADMIN_IDS:
        return True
    try:
        m = await update.effective_chat.get_member(uid)
        return m.status in ("administrator", "creator")
    except Exception:
        return False


async def is_subscribed(bot, uid: int) -> bool:
    """Public helper — returns True if force-sub is off or user is a member."""
    if not STATE["enabled"] or not STATE["channel"]:
        return True
    try:
        member = await bot.get_chat_member(chat_id=STATE["channel"], user_id=uid)
        return member.status not in ("left", "kicked")
    except Exception as e:
        log.warning("Force-sub check failed for %s: %s", uid, e)
        return True  # fail open so a bad config never locks everyone out


def force_sub_markup() -> InlineKeyboardMarkup:
    link = STATE["link"] or ("https://t.me/" + STATE["channel"].lstrip("@")
                              if STATE["channel"] and not STATE["channel"].startswith("-")
                              else "https://t.me/")
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Join Channel", url=link)],
        [InlineKeyboardButton("🔄 I Joined — Check Again", callback_data="fs_check")],
    ])


async def cmd_setforcesub(update, ctx):
    if not await _is_admin(update):
        await update.message.reply_text("🚫 Admin only.")
        return
    if not ctx.args:
        await update.message.reply_text(
            "Usage: /setforcesub @channel [invite_link]\n"
            "Example: /setforcesub @mychannel https://t.me/+abc123"
        )
        return

    STATE["channel"] = ctx.args[0]
    STATE["link"]    = ctx.args[1] if len(ctx.args) > 1 else ""
    STATE["enabled"] = True

    try:
        chat  = await ctx.bot.get_chat(STATE["channel"])
        title = chat.title or STATE["channel"]
        link  = STATE["link"] or ("https://t.me/" + STATE["channel"].lstrip("@"))
        text = (
            "✅ <b>Force Sub Enabled!</b>\n\n"
            "Channel : <b>" + title + "</b>\n"
            "ID      : <code>" + STATE["channel"] + "</code>\n"
            "Link    : " + link + "\n\n"
            "Users must now join before using the bot.\n"
            "Use /removeforcesub to disable."
        )
        await update.message.reply_text(text, parse_mode="HTML")
    except Exception as e:
        STATE["enabled"] = False
        STATE["channel"] = ""
        await update.message.reply_text(
            "❌ Failed: " + str(e) + "\nMake sure the bot is an admin of that channel."
        )


async def cmd_removeforcesub(update, ctx):
    if not await _is_admin(update):
        await update.message.reply_text("🚫 Admin only.")
        return
    old = STATE["channel"]
    STATE["channel"] = ""
    STATE["link"]    = ""
    STATE["enabled"] = False
    await update.message.reply_text(
        "✅ <b>Force Sub Disabled!</b>\nWas: <code>" + (old or "none") + "</code>",
        parse_mode="HTML"
    )


async def cmd_checkforcesub(update, ctx):
    if not await _is_admin(update):
        await update.message.reply_text("🚫 Admin only.")
        return
    if not STATE["enabled"]:
        await update.message.reply_text(
            "📢 <b>Force Sub: DISABLED</b>\nUse /setforcesub @channel to enable.",
            parse_mode="HTML"
        )
        return
    try:
        chat  = await ctx.bot.get_chat(STATE["channel"])
        count = await ctx.bot.get_chat_member_count(STATE["channel"])
        link  = STATE["link"] or ("https://t.me/" + STATE["channel"].lstrip("@"))
        text = (
            "📢 <b>Force Sub: ACTIVE</b>\n\n"
            "Channel : <b>" + chat.title + "</b>\n"
            "Members : <b>" + str(count) + "</b>\n"
            "Link    : " + link
        )
        await update.message.reply_text(text, parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text("⚠️ Check failed: " + str(e))


async def cb_check_sub(update, ctx):
    q  = update.callback_query
    u  = q.from_user
    await q.answer()
    if await is_subscribed(ctx.bot, u.id):
        await q.answer("✅ Verified! Welcome.", show_alert=False)
        try:
            await q.message.delete()
        except Exception:
            pass
        await ctx.bot.send_message(
            chat_id=u.id,
            text="✅ <b>Subscription verified!</b>\n\nSend /start to begin.",
            parse_mode="HTML"
        )
    else:
        await q.answer("❌ You haven't joined yet! Please join first.", show_alert=True)
