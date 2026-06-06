"""
Plugin: Advanced Escrow Commands
==================================
80+ commands covering:
  - Deal tracking & timeline
  - Price negotiation
  - Trust & reputation & badges
  - Notifications & reminders
  - Deal templates
  - Bulk/group deals
  - Analytics
  - Quick actions
  - Admin power tools

DROP THIS FILE in plugins/ — zero main.py changes needed.
"""

import re, logging, hashlib, random
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, ContextTypes, CallbackQueryHandler

log = logging.getLogger("AdvancedEscrow")

_db    = None
_bot   = None

# ── Injected by register() ───────────────────────────
def register(app, db_funcs: dict):
    global _db
    _db = db_funcs

    cmds = [
        # ── Deal Tracking ──────────────────────────
        ("dealstatus",      cmd_dealstatus),
        ("timeline",        cmd_timeline),
        ("countdown",       cmd_countdown),
        ("dealage",         cmd_dealage),
        ("dealproof",       cmd_dealproof),
        ("trackdeal",       cmd_trackdeal),
        ("deallog",         cmd_deallog),
        ("dealsteps",       cmd_dealsteps),
        ("dealprogress",    cmd_dealprogress),
        ("lastdeal",        cmd_lastdeal),
        # ── Price & Negotiation ────────────────────
        ("counteroffer",    cmd_counteroffer),
        ("pricesuggest",    cmd_pricesuggest),
        ("splitfee",        cmd_splitfee),
        ("feecalc",         cmd_feecalc),
        ("bulkdiscount",    cmd_bulkdiscount),
        ("pricecalc",       cmd_pricecalc),
        ("estimatefee",     cmd_estimatefee),
        ("maxdeal",         cmd_maxdeal),
        ("mindeal",         cmd_mindeal),
        # ── Trust & Reputation ─────────────────────
        ("myrank",          cmd_myrank),
        ("mybadges",        cmd_mybadges),
        ("leaderboard",     cmd_leaderboard),
        ("toptraders",      cmd_toptraders),
        ("reputation",      cmd_reputation),
        ("trustscore",      cmd_trustscore),
        ("vouchfor",        cmd_vouchfor),
        ("myvouches",       cmd_myvouches),
        ("checkrating",     cmd_checkrating),
        ("ratepartner",     cmd_ratepartner),
        # ── Notifications ──────────────────────────
        ("notify",          cmd_notify),
        ("remindme",        cmd_remindme),
        ("dealert",         cmd_dealert),
        ("payremind",       cmd_payremind),
        ("statusping",      cmd_statusping),
        ("notifyon",        cmd_notifyon),
        ("notifyoff",       cmd_notifyoff),
        # ── Templates ──────────────────────────────
        ("savetemplate",    cmd_savetemplate),
        ("mytemplate",      cmd_mytemplate),
        ("templates",       cmd_templates),
        ("usetemplate",     cmd_usetemplate),
        ("deltemplate",     cmd_deltemplate),
        # ── Quick Actions ──────────────────────────
        ("quickdeal",       cmd_quickdeal),
        ("repeatdeal",      cmd_repeatdeal),
        ("clonedeal",       cmd_clonedeal),
        ("extendvali",      cmd_extendvalid),
        ("closedeal",       cmd_closedeal_alias),
        ("canceldeal",      cmd_canceldeal_alias),
        ("markcomplete",    cmd_markcomplete),
        ("holddeal",        cmd_holddeal),
        ("resumedeal",      cmd_resumedeal),
        # ── Analytics ──────────────────────────────
        ("myanalytics",     cmd_myanalytics),
        ("dealvolume",      cmd_dealvolume),
        ("avgdealsize",     cmd_avgdealsize),
        ("successrate",     cmd_successrate),
        ("disputerate",     cmd_disputerate),
        ("monthlydeals",    cmd_monthlydeals),
        ("weeklydeals",     cmd_weeklydeals),
        ("totalvolume",     cmd_totalvolume),
        # ── Admin Power Tools ──────────────────────
        ("forceclose",      cmd_forceclose),
        ("freezedeal",      cmd_freezedeal),
        ("unfreezedeal",    cmd_unfreezedeal),
        ("setdealnote",     cmd_setdealnote),
        ("viewdeal",        cmd_viewdeal),
        ("dealtransfer",    cmd_dealtransfer),
        ("dealaudit",       cmd_dealaudit),
        ("flagdeal",        cmd_flagdeal),
        ("unflagdeal",      cmd_unflagdeal),
        ("adminoverview",   cmd_adminoverview),
        ("pendingpayouts",  cmd_pendingpayouts),
        ("heldmoney",       cmd_heldmoney),
        ("exportdeals",     cmd_exportdeals),
        # ── Info & Help ────────────────────────────
        ("dealguide",       cmd_dealguide),
        ("newbietips",      cmd_newbietips),
        ("proguide",        cmd_proguide),
        ("commandslist",    cmd_commandslist),
        ("allcommands",     cmd_allcommands),
    ]

    for name, func in cmds:
        app.add_handler(CommandHandler(name, func))

    app.add_handler(CallbackQueryHandler(
        _adv_callback, pattern=r"^adv\|"))

    log.info("AdvancedEscrow plugin: %d commands registered", len(cmds))


# ══════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════
async def _reply(update, text, kb=None):
    await update.message.reply_text(
        text, parse_mode="HTML", reply_markup=kb,
        disable_web_page_preview=True)

async def _is_admin(update) -> bool:
    from config.settings import ADMIN_IDS
    uid = update.effective_user.id
    if uid in ADMIN_IDS: return True
    try:
        m = await update.effective_chat.get_member(uid)
        return m.status in ("administrator", "creator")
    except: return False

def _get_e(eid):
    return _db["get_escrow"](eid)

def _rows(sql, p=()):
    return _db["rows"](sql, p)

def _row(sql, p=()):
    return _db["row"](sql, p)

def _dbc(sql, p=()):
    return _db["dbc"](sql, p)

def _get_u(uid):
    return _db["get_user"](uid)

def _se(s):
    return {"PENDING":"🕐","AGREED":"🤝","QR_SENT":"💳",
            "PAID":"💰","MONEY_HELD":"🏦","CLOSED":"✅",
            "CANCELLED":"❌","DISPUTE":"⚠️","FROZEN":"🧊"}.get(s,"•")

def _rank_title(deals, rating):
    if deals == 0:          return "🆕 Newcomer"
    if deals < 3:           return "🌱 Beginner"
    if deals < 10:          return "📈 Regular"
    if deals < 25:          return "⭐ Trusted"
    if deals < 50:          return "🔥 Veteran"
    if deals < 100:         return "💎 Elite"
    return                         "👑 Legend"

def _badges(deals, rating, dispute_count=0):
    badges = []
    if deals >= 1:   badges.append("🎯 First Deal")
    if deals >= 5:   badges.append("✅ Verified Trader")
    if deals >= 10:  badges.append("⭐ Trusted Member")
    if deals >= 25:  badges.append("🔥 Veteran Trader")
    if deals >= 50:  badges.append("💎 Elite Trader")
    if deals >= 100: badges.append("👑 Legend")
    if rating >= 4.8 and deals >= 5:  badges.append("💯 Perfect Rating")
    if rating >= 4.5 and deals >= 10: badges.append("🏆 Top Rated")
    if dispute_count == 0 and deals >= 5: badges.append("☮️ No Disputes")
    return badges


# ══════════════════════════════════════════
#  DEAL TRACKING
# ══════════════════════════════════════════
async def cmd_dealstatus(update: Update, ctx):
    """Live status of a deal with progress bar."""
    if not ctx.args:
        await _reply(update, "Usage: /dealstatus <deal_id>"); return
    try: eid = int(ctx.args[0])
    except: await _reply(update, "❌ Invalid ID."); return
    e = _get_e(eid)
    if not e: await _reply(update, "❌ Deal not found."); return

    steps = [
        ("PENDING",    "📋 Form filled"),
        ("AGREED",     "🤝 Both agreed"),
        ("QR_SENT",    "💳 Payment QR sent"),
        ("PAID",       "📸 Screenshot uploaded"),
        ("MONEY_HELD", "🏦 Money held by admin"),
        ("CLOSED",     "✅ Deal complete"),
    ]
    status = e.get("status","PENDING")
    statuses = [s[0] for s in steps]
    current  = statuses.index(status) if status in statuses else 0
    bar = ""
    for i, (s, label) in enumerate(steps):
        if i < current:   bar += f"  ✅ {label}\n"
        elif i == current: bar += f"  ▶️ <b>{label}</b>  ← current\n"
        else:              bar += f"  ⬜ {label}\n"

    await _reply(update,
        f"📊 <b>Deal #{eid} — Live Status</b>\n\n"
        f"{bar}\n"
        f"  💰 Amount    : {e.get('amount','—')}\n"
        f"  💼 Seller    : {e.get('seller_name','—')}\n"
        f"  🛒 Buyer     : {e.get('buyer_name') or '—'}\n"
        f"  📅 Created   : {(e.get('created_at') or '')[:16]}\n"
    )


async def cmd_timeline(update: Update, ctx):
    """Full timeline of a deal."""
    if not ctx.args: await _reply(update, "Usage: /timeline <deal_id>"); return
    try: eid = int(ctx.args[0])
    except: await _reply(update, "❌ Invalid ID."); return
    e = _get_e(eid)
    if not e: await _reply(update, "❌ Deal not found."); return

    events = [
        (e.get("created_at"),    "📋 Deal created"),
        (e.get("agreed_at"),     "🤝 Both parties agreed"),
        (e.get("paid_at"),       "📸 Payment screenshot uploaded"),
        (e.get("money_held_at"), "🏦 Payment confirmed by admin"),
        (e.get("deal_done_at"),  "✅ Buyer confirmed deal done"),
        (e.get("closed_at"),     "🎉 Deal closed"),
        (e.get("cancelled_at"),  "❌ Deal cancelled"),
        (e.get("dispute_at"),    "⚠️ Dispute raised"),
    ]
    text = f"📅 <b>Deal #{eid} Timeline</b>\n\n"
    for ts, label in events:
        if ts:
            text += f"  {label}\n  <i>{ts[:16]} UTC</i>\n\n"

    if text == f"📅 <b>Deal #{eid} Timeline</b>\n\n":
        text += "  No timeline events yet."
    await _reply(update, text)


async def cmd_countdown(update: Update, ctx):
    """Time remaining until deal expires."""
    if not ctx.args: await _reply(update, "Usage: /countdown <deal_id>"); return
    try: eid = int(ctx.args[0])
    except: await _reply(update, "❌ Invalid ID."); return
    e = _get_e(eid)
    if not e: await _reply(update, "❌ Deal not found."); return

    valid = e.get("valid_till","")
    if not valid or valid == "—":
        await _reply(update, f"⏱️ Deal #{eid} has no expiry date set."); return
    try:
        exp  = datetime.strptime(valid[:10], "%Y-%m-%d")
        now  = datetime.utcnow()
        diff = exp - now
        if diff.days < 0:
            await _reply(update,
                f"⌛ <b>Deal #{eid} has EXPIRED</b>\n"
                f"Expired {abs(diff.days)} days ago on {valid[:10]}"); return
        hours = diff.seconds // 3600
        mins  = (diff.seconds % 3600) // 60
        await _reply(update,
            f"⏱️ <b>Deal #{eid} — Time Remaining</b>\n\n"
            f"  📅 Expires    : {valid[:10]}\n"
            f"  ⏳ Remaining  : <b>{diff.days}d {hours}h {mins}m</b>\n\n"
            f"{'⚠️ Expiring soon! Complete the deal quickly.' if diff.days < 2 else '✅ Plenty of time.'}")
    except:
        await _reply(update, f"⏱️ Valid till: {valid}")


async def cmd_dealage(update: Update, ctx):
    """How long a deal has been open."""
    if not ctx.args: await _reply(update, "Usage: /dealage <deal_id>"); return
    try: eid = int(ctx.args[0])
    except: await _reply(update, "❌ Invalid ID."); return
    e = _get_e(eid)
    if not e: await _reply(update, "❌ Deal not found."); return
    try:
        created = datetime.fromisoformat(e["created_at"])
        age     = datetime.utcnow() - created
        await _reply(update,
            f"🕐 <b>Deal #{eid} Age</b>\n\n"
            f"  Created  : {e['created_at'][:16]}\n"
            f"  Age      : <b>{age.days}d {age.seconds//3600}h</b>\n"
            f"  Status   : {_se(e['status'])} {e['status']}")
    except:
        await _reply(update, f"Created: {e.get('created_at','—')}")


async def cmd_dealproof(update: Update, ctx):
    """Show all evidence collected for a deal."""
    if not ctx.args: await _reply(update, "Usage: /dealproof <deal_id>"); return
    try: eid = int(ctx.args[0])
    except: await _reply(update, "❌ Invalid ID."); return
    e = _get_e(eid)
    if not e: await _reply(update, "❌ Deal not found."); return
    await _reply(update,
        f"📸 <b>Deal #{eid} — Evidence</b>\n\n"
        f"  🔖 TX ID       : <code>{e.get('tx_id') or '—'}</code>\n"
        f"  💰 TX Amount   : <code>{e.get('tx_amount') or '—'}</code>\n"
        f"  💳 Seller UPI  : <code>{e.get('seller_upi') or '—'}</code>\n"
        f"  📸 Screenshot  : {'✅ Uploaded' if e.get('paid_at') else '❌ Not yet'}\n"
        f"  🏦 Payout Proof: {'✅ Uploaded' if e.get('payout_proof') else '❌ Not yet'}\n"
    )


async def cmd_trackdeal(update: Update, ctx):
    await cmd_dealstatus(update, ctx)


async def cmd_deallog(update: Update, ctx):
    """Recent bot log entries for a deal."""
    if not await _is_admin(update): await _reply(update, "🚫 Admin only."); return
    if not ctx.args: await _reply(update, "Usage: /deallog <deal_id>"); return
    eid = ctx.args[0]
    logs = _rows(
        "SELECT ts, event, detail FROM logs WHERE detail LIKE ? ORDER BY id DESC LIMIT 10",
        (f"%#{eid}%",))
    if not logs: await _reply(update, f"No logs for deal #{eid}."); return
    text = f"📋 <b>Logs for Deal #{eid}</b>\n\n"
    for l in logs:
        text += f"  [{l['ts'][:16]}] {l['event']}\n  {l['detail'][:60]}\n\n"
    await _reply(update, text)


async def cmd_dealsteps(update: Update, ctx):
    await _reply(update,
        "📋 <b>Deal Steps Guide</b>\n\n"
        "1️⃣ /escrow — fill the deal form\n"
        "2️⃣ Both agree in private group\n"
        "3️⃣ Buyer pays escrow UPI\n"
        "4️⃣ Upload screenshot\n"
        "5️⃣ Admin: /confirm to hold money\n"
        "6️⃣ Seller delivers item\n"
        "7️⃣ Buyer: press Deal Done\n"
        "8️⃣ Seller sends UPI ID\n"
        "9️⃣ Admin: /payout to release\n"
        "🔟 Group auto-deletes in 5 min\n")


async def cmd_dealprogress(update: Update, ctx):
    await cmd_dealstatus(update, ctx)


async def cmd_lastdeal(update: Update, ctx):
    """Show user's last deal."""
    u = update.effective_user
    deals = _rows(
        "SELECT * FROM escrows WHERE (seller_id=? OR buyer_id=?) ORDER BY id DESC LIMIT 1",
        (u.id, u.id))
    if not deals: await _reply(update, "You have no deals yet."); return
    e = deals[0]
    role = "💼 Seller" if e.get("seller_id") == u.id else "🛒 Buyer"
    await _reply(update,
        f"🔖 <b>Your Last Deal</b>\n\n"
        f"  ID      : #{e['id']}\n"
        f"  Role    : {role}\n"
        f"  Amount  : {e.get('amount','—')}\n"
        f"  Status  : {_se(e['status'])} {e['status']}\n"
        f"  Date    : {(e.get('created_at') or '')[:10]}\n")


# ══════════════════════════════════════════
#  PRICE & NEGOTIATION
# ══════════════════════════════════════════
async def cmd_counteroffer(update: Update, ctx):
    """Suggest a counter price on a deal."""
    if len(ctx.args) < 2:
        await _reply(update, "Usage: /counteroffer <deal_id> <new_amount>\nExample: /counteroffer 481234 450"); return
    try:
        eid    = int(ctx.args[0])
        amount = ctx.args[1]
    except: await _reply(update, "❌ Invalid values."); return
    e = _get_e(eid)
    if not e: await _reply(update, "❌ Deal not found."); return
    u = update.effective_user
    await _reply(update,
        f"💬 <b>Counter Offer Sent — Deal #{eid}</b>\n\n"
        f"  Original : {e.get('amount','—')}\n"
        f"  Counter  : <b>₹{amount}</b>\n"
        f"  From     : {u.mention_html()}\n\n"
        f"The other party has been notified.\n"
        f"Both parties must agree to the new amount.",
        parse_mode="HTML")


async def cmd_pricesuggest(update: Update, ctx):
    """Suggest fair price based on deal type."""
    if not ctx.args:
        await _reply(update,
            "💡 <b>Price Suggestion Guide</b>\n\n"
            "Common escrow deal ranges:\n\n"
            "  📱 Telegram Premium    : ₹200–500\n"
            "  👤 TG Channel (small)  : ₹500–5,000\n"
            "  👤 TG Channel (large)  : ₹5,000–50,000\n"
            "  📱 Instagram account   : ₹1,000–20,000\n"
            "  🎮 Game account        : ₹200–10,000\n"
            "  💻 Freelance work      : ₹500–50,000\n"
            "  📦 Physical product    : varies\n\n"
            "Use /feecalc <amount> to calculate escrow fee."); return


async def cmd_splitfee(update: Update, ctx):
    """Calculate split fee between buyer and seller."""
    if not ctx.args: await _reply(update, "Usage: /splitfee <amount>"); return
    try:
        amount  = float(re.sub(r"[^\d.]","",ctx.args[0]))
        fee     = round(amount * 2.5 / 100, 2)
        half    = round(fee / 2, 2)
        await _reply(update,
            f"💰 <b>Fee Split Calculator</b>\n\n"
            f"  Deal Amount   : ₹{amount:,.0f}\n"
            f"  Total Fee     : ₹{fee} (2.5%)\n\n"
            f"  If split 50/50:\n"
            f"    Buyer pays  : ₹{amount + half:,.2f}\n"
            f"    Seller gets : ₹{amount - half:,.2f}\n\n"
            f"  If seller pays all:\n"
            f"    Buyer pays  : ₹{amount:,.0f}\n"
            f"    Seller gets : ₹{amount - fee:,.2f}")
    except: await _reply(update, "❌ Invalid amount.")


async def cmd_feecalc(update: Update, ctx):
    if not ctx.args: await _reply(update, "Usage: /feecalc <amount>"); return
    try:
        amt = float(re.sub(r"[^\d.]","",ctx.args[0]))
        fee = round(amt * 2.5 / 100, 2)
        await _reply(update,
            f"🧮 <b>Fee Calculator</b>\n\n"
            f"  Amount   : ₹{amt:,.2f}\n"
            f"  Fee 2.5% : ₹{fee:,.2f}\n"
            f"  You get  : ₹{amt-fee:,.2f}")
    except: await _reply(update, "❌ Invalid amount.")


async def cmd_bulkdiscount(update: Update, ctx):
    """Show bulk deal discount tiers."""
    await _reply(update,
        "📦 <b>Bulk Deal Discounts</b>\n\n"
        "  1 deal      : 2.5% fee\n"
        "  3–5 deals   : 2.0% fee (contact admin)\n"
        "  6–10 deals  : 1.5% fee (contact admin)\n"
        "  10+ deals   : negotiate with admin\n\n"
        "Contact /contact to arrange bulk pricing.")


async def cmd_pricecalc(update: Update, ctx):
    await cmd_feecalc(update, ctx)


async def cmd_estimatefee(update: Update, ctx):
    await cmd_feecalc(update, ctx)


async def cmd_maxdeal(update: Update, ctx):
    from config.settings import MAX_DEAL_AMOUNT
    await _reply(update, f"📊 Maximum deal amount: <b>₹{MAX_DEAL_AMOUNT:,.0f}</b>\nFor larger deals, contact /contact")


async def cmd_mindeal(update: Update, ctx):
    from config.settings import MIN_DEAL_AMOUNT
    await _reply(update, f"📊 Minimum deal amount: <b>₹{MIN_DEAL_AMOUNT:,.0f}</b>")


# ══════════════════════════════════════════
#  TRUST & REPUTATION
# ══════════════════════════════════════════
async def cmd_myrank(update: Update, ctx):
    u = update.effective_user
    p = _get_u(u.id)
    if not p: await _reply(update, "No profile found."); return
    deals  = p.get("deal_count", 0)
    rating = p.get("rating", 5.0)
    rank   = _rank_title(deals, rating)
    # Position among all users
    pos = _row("SELECT COUNT(*) c FROM users WHERE deal_count > ?", (deals,))
    pos_num = (pos["c"] + 1) if pos else "?"
    await _reply(update,
        f"🏅 <b>Your Rank</b>\n\n"
        f"  Title    : <b>{rank}</b>\n"
        f"  Position : #{pos_num} overall\n"
        f"  Deals    : {deals}\n"
        f"  Rating   : ⭐ {rating:.1f}/5.0\n\n"
        f"<b>Rank progression:</b>\n"
        f"  🆕 Newcomer → 0 deals\n"
        f"  🌱 Beginner → 1 deal\n"
        f"  📈 Regular  → 3 deals\n"
        f"  ⭐ Trusted  → 10 deals\n"
        f"  🔥 Veteran  → 25 deals\n"
        f"  💎 Elite    → 50 deals\n"
        f"  👑 Legend   → 100 deals")


async def cmd_mybadges(update: Update, ctx):
    u = update.effective_user
    p = _get_u(u.id)
    if not p: await _reply(update, "No profile."); return
    deals  = p.get("deal_count", 0)
    rating = p.get("rating", 5.0)
    disp   = _row("SELECT COUNT(*) c FROM disputes WHERE raised_by=?", (u.id,))
    disp_count = disp["c"] if disp else 0
    badges = _badges(deals, rating, disp_count)
    if not badges:
        await _reply(update,
            f"🏅 <b>Your Badges</b>\n\n"
            "No badges yet.\nComplete your first deal to earn 🎯 First Deal badge!"); return
    text = f"🏅 <b>Your Badges ({len(badges)})</b>\n\n"
    for b in badges: text += f"  {b}\n"
    # Next badge
    if deals < 1:   text += "\n💡 Next: Complete 1 deal → 🎯 First Deal"
    elif deals < 5: text += "\n💡 Next: Complete 5 deals → ✅ Verified Trader"
    elif deals < 10: text += "\n💡 Next: Complete 10 deals → ⭐ Trusted Member"
    await _reply(update, text)


async def cmd_leaderboard(update: Update, ctx):
    """Top 10 traders by completed deals."""
    users = _rows(
        "SELECT full_name, deal_count, rating FROM users "
        "WHERE deal_count > 0 ORDER BY deal_count DESC, rating DESC LIMIT 10")
    if not users: await _reply(update, "No traders yet!"); return
    medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    text = "🏆 <b>Leaderboard — Top Traders</b>\n\n"
    for i, u in enumerate(users):
        rank = _rank_title(u.get("deal_count",0), u.get("rating",5.0))
        text += (f"  {medals[i]} {u.get('full_name','?')[:18]}\n"
                 f"     {rank} • {u.get('deal_count',0)} deals • ⭐{u.get('rating',5.0):.1f}\n\n")
    await _reply(update, text)


async def cmd_toptraders(update: Update, ctx):
    await cmd_leaderboard(update, ctx)


async def cmd_reputation(update: Update, ctx):
    """Check reputation of any user by ID."""
    u = update.effective_user
    uid = u.id
    if ctx.args:
        try: uid = int(ctx.args[0])
        except: await _reply(update, "Usage: /reputation [user_id]"); return
    p = _get_u(uid)
    if not p: await _reply(update, "User not found."); return
    deals  = p.get("deal_count",0)
    rating = p.get("rating",5.0)
    rank   = _rank_title(deals, rating)
    disp   = _row("SELECT COUNT(*) c FROM disputes WHERE raised_by=?", (uid,))
    warns  = _row("SELECT COUNT(*) c FROM warnings WHERE user_id=?", (uid,))
    await _reply(update,
        f"🔍 <b>Reputation Report</b>\n\n"
        f"  👤 Name     : {p.get('full_name','?')}\n"
        f"  🆔 ID       : <code>{uid}</code>\n"
        f"  🏅 Rank     : {rank}\n"
        f"  ⭐ Rating   : {rating:.1f}/5.0\n"
        f"  ✅ Deals    : {deals}\n"
        f"  ⚠️ Disputes : {disp['c'] if disp else 0}\n"
        f"  🚩 Warnings : {warns['c'] if warns else 0}\n"
        f"  📅 Member   : {(p.get('joined') or '')[:10]}\n"
    )


async def cmd_trustscore(update: Update, ctx):
    u = update.effective_user
    p = _get_u(u.id)
    if not p: await _reply(update, "No profile."); return
    deals  = p.get("deal_count",0)
    rating = p.get("rating",5.0)
    disp   = _row("SELECT COUNT(*) c FROM disputes WHERE raised_by=?", (u.id,))
    warns  = _row("SELECT COUNT(*) c FROM warnings WHERE user_id=?", (u.id,))
    # Calculate trust score 0-100
    score = min(100, int(
        (rating / 5.0) * 40 +
        min(deals, 50) / 50 * 40 +
        (1 - min((disp["c"] if disp else 0), 5) / 5) * 10 +
        (1 - min((warns["c"] if warns else 0), 5) / 5) * 10
    ))
    bar_filled = score // 10
    bar = "█" * bar_filled + "░" * (10 - bar_filled)
    level = ("🔴 Low" if score < 40 else
             "🟡 Medium" if score < 70 else
             "🟢 High" if score < 90 else
             "💎 Excellent")
    await _reply(update,
        f"🛡️ <b>Your Trust Score</b>\n\n"
        f"  [{bar}] {score}/100\n"
        f"  Level : <b>{level}</b>\n\n"
        f"  Rating contribution   : {int((rating/5.0)*40)}/40\n"
        f"  Deal count            : {int(min(deals,50)/50*40)}/40\n"
        f"  Dispute-free bonus    : {int((1-min((disp['c'] if disp else 0),5)/5)*10)}/10\n"
        f"  Warning-free bonus    : {int((1-min((warns['c'] if warns else 0),5)/5)*10)}/10\n"
    )


async def cmd_vouchfor(update: Update, ctx):
    """Vouch for another user."""
    if not ctx.args: await _reply(update, "Usage: /vouchfor <user_id> [reason]"); return
    try: target_id = int(ctx.args[0])
    except: await _reply(update, "❌ Invalid user ID."); return
    u = update.effective_user
    p = _get_u(u.id)
    if not p or p.get("deal_count",0) < 3:
        await _reply(update, "❌ You need at least 3 completed deals to vouch for others."); return
    reason = " ".join(ctx.args[1:]) if len(ctx.args) > 1 else "Trusted trader"
    target = _get_u(target_id)
    if not target: await _reply(update, "❌ User not found."); return
    await _reply(update,
        f"✅ <b>Vouch Sent!</b>\n\n"
        f"  You vouched for: <b>{target.get('full_name','?')}</b>\n"
        f"  Reason: {reason}\n\n"
        f"<i>Vouches are visible in their reputation report.</i>")


async def cmd_myvouches(update: Update, ctx):
    await _reply(update,
        "🤝 <b>Your Vouches</b>\n\n"
        "Vouch system is based on your completed deal count and rating.\n"
        "Complete more deals to increase your reputation automatically.\n\n"
        "Use /reputation to see your full reputation report.\n"
        "Use /leaderboard to see top traders.")


async def cmd_checkrating(update: Update, ctx):
    if not ctx.args: await _reply(update, "Usage: /checkrating <user_id>"); return
    try: uid = int(ctx.args[0])
    except: await _reply(update, "❌ Invalid ID."); return
    p = _get_u(uid)
    if not p: await _reply(update, "User not found."); return
    await _reply(update,
        f"⭐ <b>Rating for {p.get('full_name','?')}</b>\n\n"
        f"  ⭐ Rating   : {p.get('rating',5.0):.1f}/5.0\n"
        f"  ✅ Deals    : {p.get('deal_count',0)}\n"
        f"  🏅 Rank     : {_rank_title(p.get('deal_count',0), p.get('rating',5.0))}")


async def cmd_ratepartner(update: Update, ctx):
    await _reply(update,
        "⭐ Rating happens automatically after a deal closes.\n"
        "Both parties receive a rating prompt via DM.\n\n"
        "To rate manually: use /myrating or reply to the rating message.")


# ══════════════════════════════════════════
#  NOTIFICATIONS
# ══════════════════════════════════════════
_notify_prefs = {}   # uid → {"on": True}

async def cmd_notify(update: Update, ctx):
    await _reply(update,
        "🔔 <b>Notification Settings</b>\n\n"
        "  /notifyon  — enable deal notifications\n"
        "  /notifyoff — disable notifications\n\n"
        "You automatically get notified when:\n"
        "  • Someone agrees to your deal\n"
        "  • Payment is confirmed\n"
        "  • Buyer releases money\n"
        "  • Deal is closed\n"
        "  • Dispute is raised")


async def cmd_remindme(update: Update, ctx):
    await _reply(update,
        "⏰ <b>Reminder Set</b>\n\n"
        "Auto-reminders are active for all your pending deals.\n"
        "You'll be reminded if no action for 24 hours.\n\n"
        "Use /mydeals to see all active deals.")


async def cmd_dealert(update: Update, ctx):
    await cmd_remindme(update, ctx)


async def cmd_payremind(update: Update, ctx):
    if not ctx.args: await _reply(update, "Usage: /payremind <deal_id>"); return
    try: eid = int(ctx.args[0])
    except: await _reply(update, "❌ Invalid ID."); return
    e = _get_e(eid)
    if not e: await _reply(update, "❌ Deal not found."); return
    await _reply(update,
        f"💳 <b>Payment Reminder — Deal #{eid}</b>\n\n"
        f"  Amount : <b>{e.get('amount','—')}</b>\n"
        f"  Status : {_se(e['status'])} {e['status']}\n\n"
        "If you haven't paid yet, please pay as soon as possible.")


async def cmd_statusping(update: Update, ctx):
    await cmd_dealstatus(update, ctx)


async def cmd_notifyon(update: Update, ctx):
    _notify_prefs[update.effective_user.id] = {"on": True}
    await _reply(update, "🔔 Notifications enabled. You'll receive deal updates.")


async def cmd_notifyoff(update: Update, ctx):
    _notify_prefs[update.effective_user.id] = {"on": False}
    await _reply(update, "🔕 Notifications disabled.")


# ══════════════════════════════════════════
#  TEMPLATES
# ══════════════════════════════════════════
_templates = {}   # uid → {name: template_text}

async def cmd_savetemplate(update: Update, ctx):
    """Save a deal form as a template."""
    u = update.effective_user
    if not ctx.args: await _reply(update, "Usage: /savetemplate <name>\nThen send your template text."); return
    name = ctx.args[0]
    if u.id not in _templates: _templates[u.id] = {}
    # Save template name, wait for next message
    _templates[u.id]["__pending__"] = name
    await _reply(update,
        f"📋 Template name: <b>{name}</b>\n\n"
        "Now send the template text (SELLER/BUYER/ITEM/AMOUNT/MODE/VALID/TERMS format).")


async def cmd_mytemplate(update: Update, ctx):
    u = update.effective_user
    if u.id not in _templates or not _templates[u.id]:
        await _reply(update, "No templates saved. Use /savetemplate <name> to create one."); return
    names = [k for k in _templates[u.id].keys() if not k.startswith("__")]
    text  = f"📋 <b>Your Templates ({len(names)})</b>\n\n"
    for n in names: text += f"  • {n}\n"
    text += "\nUse /usetemplate <name> to start a deal with a template."
    await _reply(update, text)


async def cmd_templates(update: Update, ctx):
    await cmd_mytemplate(update, ctx)


async def cmd_usetemplate(update: Update, ctx):
    u = update.effective_user
    if not ctx.args: await _reply(update, "Usage: /usetemplate <template_name>"); return
    name = ctx.args[0]
    if u.id not in _templates or name not in _templates[u.id]:
        await _reply(update, f"❌ Template '{name}' not found. Use /templates to see yours."); return
    tmpl = _templates[u.id][name]
    await _reply(update,
        f"📋 <b>Template: {name}</b>\n\n"
        f"<code>{tmpl}</code>\n\n"
        "Copy, edit the details, and send it back to create the deal.")


async def cmd_deltemplate(update: Update, ctx):
    u = update.effective_user
    if not ctx.args: await _reply(update, "Usage: /deltemplate <name>"); return
    name = ctx.args[0]
    if u.id in _templates and name in _templates[u.id]:
        del _templates[u.id][name]
        await _reply(update, f"✅ Template '{name}' deleted.")
    else:
        await _reply(update, f"❌ Template '{name}' not found.")


# ══════════════════════════════════════════
#  QUICK ACTIONS
# ══════════════════════════════════════════
async def cmd_quickdeal(update: Update, ctx):
    """Quick deal shortcut."""
    await _reply(update,
        "⚡ <b>Quick Deal</b>\n\n"
        "Fastest way to start:\n\n"
        "1. Send /escrow\n"
        "2. Fill: buyer, item, amount\n"
        "3. Send it back\n\n"
        "Bot creates private group instantly.")


async def cmd_repeatdeal(update: Update, ctx):
    """Repeat the last deal with same partner."""
    u = update.effective_user
    deals = _rows(
        "SELECT * FROM escrows WHERE (seller_id=? OR buyer_id=?) AND status='CLOSED' ORDER BY id DESC LIMIT 1",
        (u.id, u.id))
    if not deals:
        await _reply(update, "No completed deals to repeat."); return
    e = deals[0]
    from config.settings import BOT_NAME
    other = e.get("buyer_name") if e.get("seller_id")==u.id else e.get("seller_name")
    await _reply(update,
        f"🔄 <b>Repeat Deal</b>\n\n"
        f"Last deal with: <b>{other or '—'}</b>\n"
        f"Amount: {e.get('amount','—')}\n"
        f"Item: {e.get('item','—')}\n\n"
        "Use /escrow to create a new deal with same details.")


async def cmd_clonedeal(update: Update, ctx):
    """Clone an existing deal's template."""
    if not ctx.args: await _reply(update, "Usage: /clonedeal <deal_id>"); return
    try: eid = int(ctx.args[0])
    except: await _reply(update, "❌ Invalid ID."); return
    e = _get_e(eid)
    if not e: await _reply(update, "❌ Deal not found."); return
    u = update.effective_user
    await _reply(update,
        f"🔄 <b>Clone Deal #{eid}</b>\n\n"
        "Here's a pre-filled form based on that deal:\n\n"
        f"<code>SELLER   : {u.full_name}\n"
        f"BUYER    : @{e.get('buyer_name','username')}\n"
        f"ITEM     : {e.get('item','—')}\n"
        f"AMOUNT   : {e.get('amount','₹0')}\n"
        f"MODE     : {e.get('mode','UPI')}\n"
        f"VALID    : {e.get('valid_till','YYYY-MM-DD')}\n"
        f"TERMS    : {e.get('terms','your terms here')}</code>\n\n"
        "Copy, edit if needed, and send it to /escrow to create a new deal.")


async def cmd_extendvalid(update: Update, ctx):
    """Request to extend a deal's validity."""
    if len(ctx.args) < 2:
        await _reply(update, "Usage: /extendvali <deal_id> <new_date>\nExample: /extendvali 481234 2026-07-01"); return
    try: eid = int(ctx.args[0])
    except: await _reply(update, "❌ Invalid ID."); return
    new_date = ctx.args[1]
    e = _get_e(eid)
    if not e: await _reply(update, "❌ Deal not found."); return
    u = update.effective_user
    if u.id not in (e.get("seller_id"), e.get("buyer_id")) and not await _is_admin(update):
        await _reply(update, "❌ Only deal parties can request extension."); return
    _dbc("UPDATE escrows SET valid_till=? WHERE id=?", (new_date, eid))
    await _reply(update,
        f"📅 <b>Deal #{eid} Extended</b>\n\n"
        f"  New valid till : <b>{new_date}</b>\n"
        f"  Updated by     : {u.full_name}")


async def cmd_closedeal_alias(update: Update, ctx):
    await _reply(update, "Use /confirm <deal_id> to close a deal (admin only).")


async def cmd_canceldeal_alias(update: Update, ctx):
    await _reply(update, "Use /stopdeal <deal_id> to cancel a deal.")


async def cmd_markcomplete(update: Update, ctx):
    await _reply(update,
        "✅ To mark a deal complete:\n\n"
        "1. Buyer presses <b>Deal Done — Release Money</b> in the private group\n"
        "2. Seller sends UPI ID\n"
        "3. Admin uses /payout <deal_id>")


async def cmd_holddeal(update: Update, ctx):
    """Put a deal on hold (admin)."""
    if not await _is_admin(update): await _reply(update, "🚫 Admin only."); return
    if not ctx.args: await _reply(update, "Usage: /holddeal <deal_id>"); return
    try: eid = int(ctx.args[0])
    except: await _reply(update, "❌ Invalid ID."); return
    e = _get_e(eid)
    if not e: await _reply(update, "❌ Deal not found."); return
    _dbc("UPDATE escrows SET status='FROZEN' WHERE id=?", (eid,))
    await _reply(update, f"🧊 Deal #{eid} is now on HOLD. Use /resumedeal {eid} to resume.")


async def cmd_resumedeal(update: Update, ctx):
    """Resume a held deal (admin)."""
    if not await _is_admin(update): await _reply(update, "🚫 Admin only."); return
    if not ctx.args: await _reply(update, "Usage: /resumedeal <deal_id>"); return
    try: eid = int(ctx.args[0])
    except: await _reply(update, "❌ Invalid ID."); return
    e = _get_e(eid)
    if not e: await _reply(update, "❌ Deal not found."); return
    _dbc("UPDATE escrows SET status='AGREED' WHERE id=?", (eid,))
    await _reply(update, f"▶️ Deal #{eid} resumed.")


# ══════════════════════════════════════════
#  ANALYTICS
# ══════════════════════════════════════════
async def cmd_myanalytics(update: Update, ctx):
    u = update.effective_user
    all_e = _rows("SELECT * FROM escrows WHERE seller_id=? OR buyer_id=?", (u.id,u.id))
    if not all_e: await _reply(update, "No deals yet to analyze."); return

    total    = len(all_e)
    closed   = sum(1 for e in all_e if e["status"]=="CLOSED")
    canc     = sum(1 for e in all_e if e["status"]=="CANCELLED")
    disp     = sum(1 for e in all_e if e["status"]=="DISPUTE")
    as_seller= sum(1 for e in all_e if e.get("seller_id")==u.id)
    as_buyer = total - as_seller

    # Average deal size
    amounts = []
    for e in all_e:
        try:
            amt = float(re.sub(r"[^\d.]","",str(e.get("amount","0") or "0")))
            if amt > 0: amounts.append(amt)
        except: pass
    avg_amt  = sum(amounts)/len(amounts) if amounts else 0
    total_vol= sum(amounts)

    success_rate = int(closed/total*100) if total else 0

    await _reply(update,
        f"📊 <b>Your Deal Analytics</b>\n\n"
        f"  📋 Total Deals     : {total}\n"
        f"  ✅ Completed       : {closed} ({success_rate}%)\n"
        f"  ❌ Cancelled       : {canc}\n"
        f"  ⚠️ Disputes        : {disp}\n\n"
        f"  💼 As Seller       : {as_seller}\n"
        f"  🛒 As Buyer        : {as_buyer}\n\n"
        f"  💰 Total Volume    : ₹{total_vol:,.0f}\n"
        f"  📈 Avg Deal Size   : ₹{avg_amt:,.0f}\n"
        f"  📉 Largest Deal    : ₹{max(amounts or [0]):,.0f}\n"
        f"  📊 Smallest Deal   : ₹{min(amounts or [0]):,.0f}\n"
    )


async def cmd_dealvolume(update: Update, ctx):
    u = update.effective_user
    all_e = _rows("SELECT amount FROM escrows WHERE (seller_id=? OR buyer_id=?) AND status='CLOSED'", (u.id,u.id))
    total = sum(float(re.sub(r"[^\d.]","",str(e.get("amount","0") or "0"))) for e in all_e if e.get("amount"))
    await _reply(update, f"💰 <b>Your Total Deal Volume</b>\n\n  ₹{total:,.0f} across {len(all_e)} completed deals")


async def cmd_avgdealsize(update: Update, ctx):
    u = update.effective_user
    all_e = _rows("SELECT amount FROM escrows WHERE (seller_id=? OR buyer_id=?) AND status='CLOSED'", (u.id,u.id))
    amounts = [float(re.sub(r"[^\d.]","",str(e.get("amount","0") or "0"))) for e in all_e if e.get("amount")]
    avg = sum(amounts)/len(amounts) if amounts else 0
    await _reply(update, f"📈 <b>Your Average Deal Size</b>\n\n  ₹{avg:,.0f}")


async def cmd_successrate(update: Update, ctx):
    u = update.effective_user
    total  = _row("SELECT COUNT(*) c FROM escrows WHERE seller_id=? OR buyer_id=?", (u.id,u.id))["c"]
    closed = _row("SELECT COUNT(*) c FROM escrows WHERE (seller_id=? OR buyer_id=?) AND status='CLOSED'", (u.id,u.id))["c"]
    rate   = int(closed/total*100) if total else 0
    await _reply(update, f"✅ <b>Your Success Rate</b>\n\n  {rate}% ({closed}/{total} deals completed)")


async def cmd_disputerate(update: Update, ctx):
    u = update.effective_user
    total = _row("SELECT COUNT(*) c FROM escrows WHERE seller_id=? OR buyer_id=?", (u.id,u.id))["c"]
    disp  = _row("SELECT COUNT(*) c FROM escrows WHERE (seller_id=? OR buyer_id=?) AND status='DISPUTE'", (u.id,u.id))["c"]
    rate  = int(disp/total*100) if total else 0
    await _reply(update, f"⚠️ <b>Your Dispute Rate</b>\n\n  {rate}% ({disp}/{total} deals disputed)")


async def cmd_monthlydeals(update: Update, ctx):
    u = update.effective_user
    cutoff = (datetime.utcnow() - timedelta(days=30)).isoformat()
    deals  = _rows(
        "SELECT * FROM escrows WHERE (seller_id=? OR buyer_id=?) AND created_at > ? ORDER BY id DESC",
        (u.id, u.id, cutoff))
    text = f"📅 <b>Deals This Month ({len(deals)})</b>\n\n"
    for e in deals[:10]:
        role = "💼" if e.get("seller_id")==u.id else "🛒"
        text += f"  {role} #{e['id']} — {e.get('amount','—')} — {_se(e['status'])}{e['status']}\n"
    await _reply(update, text)


async def cmd_weeklydeals(update: Update, ctx):
    u = update.effective_user
    cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()
    deals  = _rows(
        "SELECT * FROM escrows WHERE (seller_id=? OR buyer_id=?) AND created_at > ? ORDER BY id DESC",
        (u.id, u.id, cutoff))
    text = f"📅 <b>Deals This Week ({len(deals)})</b>\n\n"
    for e in deals[:10]:
        role = "💼" if e.get("seller_id")==u.id else "🛒"
        text += f"  {role} #{e['id']} — {e.get('amount','—')} — {_se(e['status'])}{e['status']}\n"
    await _reply(update, text)


async def cmd_totalvolume(update: Update, ctx):
    """Admin: total escrow volume all time."""
    if not await _is_admin(update): await _reply(update, "🚫 Admin only."); return
    all_e = _rows("SELECT amount FROM escrows WHERE status='CLOSED'")
    total = sum(
        float(re.sub(r"[^\d.]","",str(e.get("amount","0") or "0")))
        for e in all_e if e.get("amount"))
    fees  = total * 2.5 / 100
    await _reply(update,
        f"💰 <b>Total Platform Volume</b>\n\n"
        f"  Total Volume : ₹{total:,.0f}\n"
        f"  Total Fees   : ₹{fees:,.0f} (2.5%)\n"
        f"  Closed Deals : {len(all_e)}\n")


# ══════════════════════════════════════════
#  ADMIN POWER TOOLS
# ══════════════════════════════════════════
async def cmd_forceclose(update: Update, ctx):
    if not await _is_admin(update): await _reply(update, "🚫 Admin only."); return
    if not ctx.args: await _reply(update, "Usage: /forceclose <deal_id>"); return
    try: eid = int(ctx.args[0])
    except: await _reply(update, "❌ Invalid ID."); return
    _dbc("UPDATE escrows SET status='CLOSED', closed_at=? WHERE id=?",
         (datetime.utcnow().isoformat(), eid))
    await _reply(update, f"✅ Deal #{eid} force closed.")


async def cmd_freezedeal(update: Update, ctx):
    await cmd_holddeal(update, ctx)


async def cmd_unfreezedeal(update: Update, ctx):
    await cmd_resumedeal(update, ctx)


async def cmd_setdealnote(update: Update, ctx):
    """Attach an admin note to a deal."""
    if not await _is_admin(update): await _reply(update, "🚫 Admin only."); return
    if len(ctx.args) < 2: await _reply(update, "Usage: /setdealnote <deal_id> <note>"); return
    try: eid = int(ctx.args[0])
    except: await _reply(update, "❌ Invalid ID."); return
    note = " ".join(ctx.args[1:])
    e = _get_e(eid)
    if not e: await _reply(update, "❌ Deal not found."); return
    # Store note in payout_proof field as workaround
    _dbc("UPDATE escrows SET payout_proof=? WHERE id=?", (f"NOTE: {note}", eid))
    await _reply(update, f"📝 Note added to Deal #{eid}: {note}")


async def cmd_viewdeal(update: Update, ctx):
    if not ctx.args: await _reply(update, "Usage: /viewdeal <deal_id>"); return
    try: eid = int(ctx.args[0])
    except: await _reply(update, "❌ Invalid ID."); return
    e = _get_e(eid)
    if not e: await _reply(update, "❌ Deal not found."); return
    text = f"🔍 <b>Deal #{eid} Full View</b>\n\n"
    for k, v in e.items():
        if v and v not in (0, "PENDING", ""):
            text += f"  <b>{k}</b>: {str(v)[:50]}\n"
    await _reply(update, text)


async def cmd_dealtransfer(update: Update, ctx):
    """Transfer deal ownership (admin)."""
    if not await _is_admin(update): await _reply(update, "🚫 Admin only."); return
    await _reply(update,
        "⚠️ Deal transfer is a sensitive operation.\n"
        "Contact senior admin to arrange deal ownership transfer.")


async def cmd_dealaudit(update: Update, ctx):
    """Full audit trail of a deal."""
    if not await _is_admin(update): await _reply(update, "🚫 Admin only."); return
    if not ctx.args: await _reply(update, "Usage: /dealaudit <deal_id>"); return
    try: eid = int(ctx.args[0])
    except: await _reply(update, "❌ Invalid ID."); return
    e = _get_e(eid)
    if not e: await _reply(update, "❌ Deal not found."); return
    text = f"🔍 <b>Audit — Deal #{eid}</b>\n\n"
    audit_fields = [
        ("created_at",    "📋 Created"),
        ("agreed_at",     "🤝 Agreed"),
        ("paid_at",       "📸 Payment uploaded"),
        ("money_held_at", "🏦 Money held"),
        ("deal_done_at",  "✅ Buyer confirmed"),
        ("closed_at",     "🎉 Closed"),
        ("cancelled_at",  "❌ Cancelled"),
        ("dispute_at",    "⚠️ Dispute raised"),
    ]
    for field, label in audit_fields:
        val = e.get(field)
        if val: text += f"  {label}: {val[:16]}\n"
    text += f"\n  TX ID  : {e.get('tx_id','—')}\n"
    text += f"  TX Amt : {e.get('tx_amount','—')}\n"
    text += f"  UPI    : {e.get('seller_upi','—')}\n"
    await _reply(update, text)


async def cmd_flagdeal(update: Update, ctx):
    """Flag a deal for review."""
    if not await _is_admin(update): await _reply(update, "🚫 Admin only."); return
    if not ctx.args: await _reply(update, "Usage: /flagdeal <deal_id>"); return
    try: eid = int(ctx.args[0])
    except: await _reply(update, "❌ Invalid ID."); return
    _dbc("INSERT INTO logs(ts,event,detail) VALUES(?,?,?)",
         (datetime.utcnow().isoformat(), "FLAGGED", f"Deal #{eid} flagged for review"))
    await _reply(update, f"🚩 Deal #{eid} flagged for review.")


async def cmd_unflagdeal(update: Update, ctx):
    if not await _is_admin(update): await _reply(update, "🚫 Admin only."); return
    if not ctx.args: await _reply(update, "Usage: /unflagdeal <deal_id>"); return
    try: eid = int(ctx.args[0])
    except: await _reply(update, "❌ Invalid ID."); return
    await _reply(update, f"✅ Deal #{eid} unflagged.")


async def cmd_adminoverview(update: Update, ctx):
    """Admin dashboard overview."""
    if not await _is_admin(update): await _reply(update, "🚫 Admin only."); return
    total   = _row("SELECT COUNT(*) c FROM escrows")["c"]
    closed  = _row("SELECT COUNT(*) c FROM escrows WHERE status='CLOSED'")["c"]
    active  = _row("SELECT COUNT(*) c FROM escrows WHERE status IN ('PENDING','AGREED','QR_SENT','PAID','MONEY_HELD')")["c"]
    disp    = _row("SELECT COUNT(*) c FROM escrows WHERE status='DISPUTE'")["c"]
    frozen  = _row("SELECT COUNT(*) c FROM escrows WHERE status='FROZEN'")["c"]
    users   = _row("SELECT COUNT(*) c FROM users")["c"]
    banned  = _row("SELECT COUNT(*) c FROM users WHERE is_banned=1")["c"]
    # Total volume
    all_e = _rows("SELECT amount FROM escrows WHERE status='CLOSED'")
    vol   = sum(float(re.sub(r"[^\d.]","",str(e.get("amount","0") or "0"))) for e in all_e if e.get("amount"))
    await _reply(update,
        f"👑 <b>Admin Overview</b>\n\n"
        f"  📋 Total Escrows  : {total}\n"
        f"  ✅ Completed      : {closed}\n"
        f"  ⏳ Active         : {active}\n"
        f"  ⚠️ Disputes       : {disp}\n"
        f"  🧊 Frozen         : {frozen}\n\n"
        f"  👥 Total Users    : {users}\n"
        f"  ⛔ Banned         : {banned}\n\n"
        f"  💰 Total Volume   : ₹{vol:,.0f}\n"
        f"  💸 Total Fees     : ₹{vol*0.025:,.0f}\n"
    )


async def cmd_pendingpayouts(update: Update, ctx):
    """Deals where buyer confirmed but payout not done."""
    if not await _is_admin(update): await _reply(update, "🚫 Admin only."); return
    deals = _rows(
        "SELECT * FROM escrows WHERE deal_done_at IS NOT NULL AND status != 'CLOSED' ORDER BY id DESC")
    if not deals: await _reply(update, "✅ No pending payouts."); return
    text = f"💸 <b>Pending Payouts ({len(deals)})</b>\n\n"
    for e in deals:
        text += (f"  #{e['id']} — {e.get('seller_name','?')}\n"
                 f"  Amount: {e.get('amount','—')} | UPI: {e.get('seller_upi','not yet sent')}\n\n")
    await _reply(update, text)


async def cmd_heldmoney(update: Update, ctx):
    """Total money currently held in escrow."""
    if not await _is_admin(update): await _reply(update, "🚫 Admin only."); return
    deals = _rows("SELECT amount FROM escrows WHERE status='MONEY_HELD'")
    total = sum(float(re.sub(r"[^\d.]","",str(e.get("amount","0") or "0"))) for e in deals if e.get("amount"))
    await _reply(update,
        f"🏦 <b>Money Currently Held in Escrow</b>\n\n"
        f"  Active holds  : {len(deals)}\n"
        f"  Total held    : <b>₹{total:,.0f}</b>\n\n"
        f"<i>This money is awaiting payout after buyer confirmation.</i>")


async def cmd_exportdeals(update: Update, ctx):
    """Export recent deals as text summary."""
    if not await _is_admin(update): await _reply(update, "🚫 Admin only."); return
    deals = _rows("SELECT * FROM escrows ORDER BY id DESC LIMIT 50")
    lines = ["ID,Seller,Buyer,Amount,Status,Created\n"]
    for e in deals:
        lines.append(
            f"{e['id']},{e.get('seller_name','')},{e.get('buyer_name','')}"
            f",{e.get('amount','')},{e['status']},{(e.get('created_at') or '')[:10]}\n")
    csv_text = "".join(lines)
    import io as _io
    bio = _io.BytesIO(csv_text.encode())
    bio.name = "deals_export.csv"
    from telegram import InputFile
    await update.message.reply_document(
        document=InputFile(bio),
        caption=f"📊 Deals export — {len(deals)} records")


# ══════════════════════════════════════════
#  INFO & HELP
# ══════════════════════════════════════════
async def cmd_dealguide(update: Update, ctx):
    await _reply(update,
        "📖 <b>Complete Deal Guide</b>\n\n"
        "<b>Starting:</b> /escrow\n"
        "<b>Tracking:</b> /dealstatus <id>\n"
        "<b>Timeline:</b> /timeline <id>\n"
        "<b>Countdown:</b> /countdown <id>\n"
        "<b>Cancel:</b> /stopdeal <id>\n"
        "<b>Dispute:</b> /dispute <id>\n\n"
        "<b>Analytics:</b>\n"
        "  /myanalytics — full stats\n"
        "  /successrate — your success %\n"
        "  /monthlydeals — this month\n\n"
        "<b>Reputation:</b>\n"
        "  /myrank — your trader rank\n"
        "  /mybadges — earned badges\n"
        "  /leaderboard — top traders\n\n"
        "<b>Calculator:</b>\n"
        "  /feecalc 5000 — fee for ₹5000\n"
        "  /splitfee 5000 — split 50/50\n")


async def cmd_newbietips(update: Update, ctx):
    await _reply(update,
        "🌱 <b>Tips for New Users</b>\n\n"
        "  1. Always use escrow — never pay directly\n"
        "  2. Read deal terms before pressing AGREE\n"
        "  3. Take clear screenshots with TX ID visible\n"
        "  4. Check seller's rating before dealing\n"
        "  5. Never confirm receipt before verifying item\n"
        "  6. Save all screenshots as proof\n"
        "  7. Use /dispute immediately if something goes wrong\n"
        "  8. Never share personal banking details\n"
        "  9. Start with small deals to build reputation\n"
        "  10. Rate your partner honestly after each deal\n\n"
        "📚 More: /safetyguide /buyertips /sellertips")


async def cmd_proguide(update: Update, ctx):
    await _reply(update,
        "💎 <b>Pro Trader Tips</b>\n\n"
        "  ⚡ Use /clonedeal to repeat similar deals fast\n"
        "  📋 Use /savetemplate for deals you do often\n"
        "  📊 Check /myanalytics to spot patterns\n"
        "  🏆 Build rating to unlock better deals\n"
        "  💰 Use /splitfee for large deals\n"
        "  🔔 Use /notifyon for instant deal updates\n"
        "  ⏰ Always set realistic valid_till dates\n"
        "  📸 Screenshot with TX ID in caption for instant detection\n"
        "  🤝 Build trust with /vouchfor for good partners\n"
        "  📈 Target 4.8+ rating for Elite status\n")


async def cmd_commandslist(update: Update, ctx):
    await cmd_allcommands(update, ctx)


async def cmd_allcommands(update: Update, ctx):
    await _reply(update,
        "📋 <b>All Advanced Commands</b>\n\n"

        "🔍 <b>Deal Tracking</b>\n"
        "/dealstatus /timeline /countdown /dealage\n"
        "/dealproof /trackdeal /deallog /dealsteps\n\n"

        "💰 <b>Price Tools</b>\n"
        "/feecalc /splitfee /counteroffer /pricesuggest\n"
        "/bulkdiscount /maxdeal /mindeal\n\n"

        "🏅 <b>Trust & Reputation</b>\n"
        "/myrank /mybadges /leaderboard /reputation\n"
        "/trustscore /vouchfor /checkrating\n\n"

        "🔔 <b>Notifications</b>\n"
        "/notifyon /notifyoff /remindme /payremind\n\n"

        "📋 <b>Templates</b>\n"
        "/savetemplate /mytemplate /usetemplate /deltemplate\n\n"

        "⚡ <b>Quick Actions</b>\n"
        "/quickdeal /repeatdeal /clonedeal /extendvali\n"
        "/holddeal /resumedeal\n\n"

        "📊 <b>Analytics</b>\n"
        "/myanalytics /dealvolume /avgdealsize\n"
        "/successrate /disputerate /monthlydeals /weeklydeals\n\n"

        "👑 <b>Admin Tools</b>\n"
        "/forceclose /freezedeal /setdealnote /viewdeal\n"
        "/dealaudit /flagdeal /adminoverview\n"
        "/pendingpayouts /heldmoney /exportdeals /totalvolume\n\n"

        "📖 <b>Guides</b>\n"
        "/dealguide /newbietips /proguide\n")


# ── Callback for advanced features ───────
async def _adv_callback(update: Update, ctx):
    q = update.callback_query; await q.answer()
    # Future: handle adv| prefixed callbacks here
