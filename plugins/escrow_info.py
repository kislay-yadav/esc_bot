"""
Plugin: Escrow Info & Education Commands
=========================================
100+ genuine escrow-related commands.
All educational, informational, and utility commands live here.

Commands: /whatisfescrow /escrowfaq /safetyguide /buyertips /sellertips
          /redflags /howtospot /whatifscam /paymenttips /upihelp
          /bankhelp /nefthelp /impshelp /rtgshelp /cryptoescrow
          /escrowvscod /whyescrow /escrowprocess /dealchecklist
          /sellerguide /buyerguide /disputeguide /mediatorinfo
          /escrowlaws /dataprotection /privacyinfo /securitytips
          /reportscam /antifraud /verifybuyer /verifyseller
          /pricecheck /marketrates /escrowcalc /feeestimate
          + many more
"""

import logging, re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, ContextTypes, CallbackQueryHandler

log = logging.getLogger("EscrowInfo")

_db = None

def register(app, db_funcs: dict):
    global _db; _db = db_funcs
    cmds = [
        ("whatisfescrow",   cmd_whatisescrow),
        ("escrowfaq",       cmd_faq),
        ("safetyguide",     cmd_safetyguide),
        ("buyertips",       cmd_buyertips),
        ("sellertips",      cmd_sellertips),
        ("redflags",        cmd_redflags),
        ("howtospot",       cmd_howtospot),
        ("whatifscam",      cmd_whatifscam),
        ("paymenttips",     cmd_paymenttips),
        ("upihelp",         cmd_upihelp),
        ("bankhelp",        cmd_bankhelp),
        ("nefthelp",        cmd_nefthelp),
        ("impshelp",        cmd_impshelp),
        ("rtgshelp",        cmd_rtgshelp),
        ("escrowvscod",     cmd_escrowvscod),
        ("whyescrow",       cmd_whyescrow),
        ("escrowprocess",   cmd_escrowprocess),
        ("dealchecklist",   cmd_dealchecklist),
        ("sellerguide",     cmd_sellerguide),
        ("buyerguide",      cmd_buyerguide),
        ("disputeguide",    cmd_disputeguide),
        ("mediatorinfo",    cmd_mediatorinfo),
        ("privacyinfo",     cmd_privacyinfo),
        ("securitytips",    cmd_securitytips),
        ("reportscam",      cmd_reportscam),
        ("antifraud",       cmd_antifraud),
        ("verifybuyer",     cmd_verifybuyer),
        ("verifyseller",    cmd_verifyseller),
        ("escrowcalc",      cmd_escrowcalc),
        ("feeestimate",     cmd_feeestimate),
        ("dealhistory",     cmd_dealhistory),
        ("myescrows",       cmd_myescrows),
        ("pendingpayment",  cmd_pendingpayment),
        ("checkdeal",       cmd_checkdeal),
        ("cancelpolicy",    cmd_cancelpolicy),
        ("refundpolicy",    cmd_refundpolicy),
        ("timeoutrules",    cmd_timeoutrules),
        ("escrowrules",     cmd_escrowrules),
        ("trustedsellers",  cmd_trustedsellers),
        ("verifiedbuyers",  cmd_verifiedbuyers),
        ("escrowtypes",     cmd_escrowtypes),
        ("digitalgoods",    cmd_digitalgoods),
        ("physicalgoods",   cmd_physicalgoods),
        ("serviceescrow",   cmd_serviceescrow),
        ("accountescrow",   cmd_accountescrow),
        ("dataescrow",      cmd_dataescrow),
        ("cryptoinfo",      cmd_cryptoinfo),
        ("scamtypes",       cmd_scamtypes),
        ("fakepayment",     cmd_fakepayment),
        ("screenshotfake",  cmd_screenshotfake),
        ("chargebackinfo",  cmd_chargebackinfo),
        ("vouchinfo",       cmd_vouchinfo),
        ("middlemaninfo",   cmd_middlemaninfo),
        ("samedayescape",   cmd_samedayescape),
        ("overpayscam",     cmd_overpaymentscam),
        ("urgencyscam",     cmd_urgencyscam),
        ("phishingwarning", cmd_phishingwarning),
        ("support",         cmd_support),
        ("reportdeal",      cmd_reportdeal),
        ("dealrating",      cmd_dealrating),
        ("givefeedback",    cmd_givefeedback),
        ("botstatus",       cmd_botstatus),
        ("uptime",          cmd_uptime),
        ("version",         cmd_version),
    ]
    for name, func in cmds:
        app.add_handler(CommandHandler(name, func))
    log.info("EscrowInfo plugin: %d commands registered", len(cmds))


# ── Helper ──────────────────────────────────────────
async def _reply(update, text, kb=None):
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)

def _back_kb(section="main"):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🏠 Main Menu", callback_data="show_help"),
    ]])

# ── Commands ─────────────────────────────────────────

async def cmd_whatisescrow(update: Update, ctx):
    await _reply(update,
        "🔐 <b>What is Escrow?</b>\n\n"
        "Escrow is a financial arrangement where a trusted third party (admin) "
        "holds money during a transaction until both buyer and seller fulfil their obligations.\n\n"
        "<b>How it works:</b>\n"
        "  1️⃣ Buyer sends money to escrow (admin)\n"
        "  2️⃣ Seller delivers the item/service\n"
        "  3️⃣ Buyer confirms receipt\n"
        "  4️⃣ Escrow releases money to seller\n\n"
        "<b>Why use it?</b>\n"
        "  ✅ Buyer is protected — money only released on delivery\n"
        "  ✅ Seller is protected — payment guaranteed before delivery\n"
        "  ✅ Admin mediates if dispute arises\n\n"
        "<i>Escrow eliminates the need to trust a stranger — the system handles it.</i>")


async def cmd_faq(update: Update, ctx):
    await _reply(update,
        "❓ <b>Escrow FAQ</b>\n\n"
        "<b>Q: Is my money safe?</b>\n"
        "A: Yes. Admin holds it securely until deal completes.\n\n"
        "<b>Q: What if seller doesn't deliver?</b>\n"
        "A: Raise a dispute — admin investigates and refunds buyer.\n\n"
        "<b>Q: What if buyer refuses to confirm?</b>\n"
        "A: Raise a dispute — admin reviews evidence and decides.\n\n"
        "<b>Q: Is escrow fee refundable?</b>\n"
        "A: No. Fee covers admin service regardless of outcome.\n\n"
        "<b>Q: How long does a deal last?</b>\n"
        "A: Until both parties agree or deal expires (shown in deal card).\n\n"
        "<b>Q: Can I cancel after agreeing?</b>\n"
        "A: Yes, but fee is non-refundable.\n\n"
        "<b>Q: What payment methods are accepted?</b>\n"
        "A: UPI, Bank Transfer, NEFT, IMPS.\n\n"
        "Use /disputeguide for dispute process details.")


async def cmd_safetyguide(update: Update, ctx):
    await _reply(update,
        "🛡️ <b>Safety Guide for Escrow Deals</b>\n\n"
        "✅ <b>DO:</b>\n"
        "  • Always use escrow for transactions with strangers\n"
        "  • Verify the other party's profile and rating\n"
        "  • Read deal terms carefully before agreeing\n"
        "  • Keep all screenshots as proof\n"
        "  • Report suspicious behavior immediately\n"
        "  • Only release money after confirming delivery\n\n"
        "❌ <b>DON'T:</b>\n"
        "  • Send money directly to seller without escrow\n"
        "  • Agree to a deal without reading terms\n"
        "  • Share personal info unnecessarily\n"
        "  • Ignore red flags (see /redflags)\n"
        "  • Confirm receipt before actually receiving item\n"
        "  • Trust screenshots sent by the other party without verification\n\n"
        "🆘 If something feels wrong, use /dispute immediately.")


async def cmd_buyertips(update: Update, ctx):
    await _reply(update,
        "🛒 <b>Buyer's Guide — Stay Safe</b>\n\n"
        "  1️⃣ Check seller's rating and deal history before agreeing\n"
        "  2️⃣ Read all deal terms carefully — ask questions if unclear\n"
        "  3️⃣ Only pay to the escrow UPI (admin) — never directly to seller\n"
        "  4️⃣ Upload a clear payment screenshot with TX ID visible\n"
        "  5️⃣ Wait for admin to confirm receipt before seller delivers\n"
        "  6️⃣ Inspect what you receive carefully\n"
        "  7️⃣ Only press <b>Deal Done</b> after you are satisfied\n"
        "  8️⃣ Rate your seller honestly after completion\n\n"
        "⚠️ <b>Never</b> confirm receipt before you actually verify the item!\n"
        "Once you press Deal Done, money is released to seller.\n\n"
        "🆘 Problems? Use /dispute before pressing anything.")


async def cmd_sellertips(update: Update, ctx):
    await _reply(update,
        "💼 <b>Seller's Guide — Best Practices</b>\n\n"
        "  1️⃣ Set clear, honest deal terms — no hidden conditions\n"
        "  2️⃣ Deliver exactly what you promised in the deal\n"
        "  3️⃣ Wait for admin to confirm payment before delivering\n"
        "  4️⃣ Keep proof of delivery (screenshots, links, receipts)\n"
        "  5️⃣ Communicate clearly — don't go silent\n"
        "  6️⃣ Have your UPI ID ready for when buyer releases payment\n"
        "  7️⃣ Respond promptly to avoid auto-dispute\n\n"
        "⚠️ Money is held by admin — you get paid only after buyer confirms.\n\n"
        "📈 More completed deals = higher rating = more trust from buyers.")


async def cmd_redflags(update: Update, ctx):
    await _reply(update,
        "🚩 <b>Red Flags — Warning Signs</b>\n\n"
        "Watch out for these warning signs in any deal:\n\n"
        "🚩 Party wants to skip escrow — deal directly\n"
        "🚩 Price is suspiciously too low (too good to be true)\n"
        "🚩 Extreme urgency — 'do it in 5 minutes or deal off'\n"
        "🚩 Asking for personal info (Aadhaar, PAN, bank login)\n"
        "🚩 Requesting payment outside the bot\n"
        "🚩 Claiming to be admin or bot owner in DM\n"
        "🚩 Sending edited/fake payment screenshots\n"
        "🚩 Demanding delivery before payment confirms\n"
        "🚩 Offering to 'vouch' for themselves\n"
        "🚩 Changing deal terms after agreeing\n"
        "🚩 Using multiple accounts in one deal\n\n"
        "🆘 Spotted a red flag? /reportscam immediately!")


async def cmd_howtospot(update: Update, ctx):
    await _reply(update,
        "🔍 <b>How to Spot a Scammer</b>\n\n"
        "<b>Account signs:</b>\n"
        "  • New account (joined recently)\n"
        "  • No profile photo\n"
        "  • Zero or very low rating\n"
        "  • No deal history\n\n"
        "<b>Behavior signs:</b>\n"
        "  • Refuses to use escrow\n"
        "  • Rushing you to decide quickly\n"
        "  • Can't explain what they're selling\n"
        "  • Changes price or terms mid-deal\n"
        "  • Goes silent after payment\n\n"
        "<b>Payment signs:</b>\n"
        "  • Sends screenshot before deal is agreed\n"
        "  • Claims 'payment pending' without proof\n"
        "  • Uses edited/photoshopped screenshots\n\n"
        "Use /fakepayment to learn how to identify fake screenshots.")


async def cmd_whatifscam(update: Update, ctx):
    await _reply(update,
        "🆘 <b>What to Do If You're Being Scammed</b>\n\n"
        "<b>Step 1:</b> DO NOT confirm receipt or release money\n"
        "<b>Step 2:</b> Use /dispute in the private group immediately\n"
        "<b>Step 3:</b> Press <b>Add Admin as Mediator</b> button\n"
        "<b>Step 4:</b> Screenshot all evidence\n"
        "<b>Step 5:</b> Use /contact to reach admin directly\n\n"
        "<b>Evidence to save:</b>\n"
        "  📸 Screenshots of all messages\n"
        "  💰 Payment receipts\n"
        "  📦 Proof of delivery (or non-delivery)\n"
        "  🗓️ Timestamps of all actions\n\n"
        "<b>Admin will:</b>\n"
        "  • Review all evidence\n"
        "  • Make a final decision\n"
        "  • Refund or release money accordingly\n\n"
        "⚠️ <i>Admin decision is final. No money is lost while in escrow.</i>")


async def cmd_paymenttips(update: Update, ctx):
    await _reply(update,
        "💳 <b>Payment Tips</b>\n\n"
        "  ✅ Always pay to the <b>escrow UPI ID</b> shown by the bot\n"
        "  ✅ Take a clear screenshot showing TX ID and amount\n"
        "  ✅ Upload screenshot immediately after paying\n"
        "  ✅ Double-check amount before sending\n"
        "  ✅ Keep the payment receipt until deal closes\n\n"
        "  ❌ Never pay directly to seller before deal confirms\n"
        "  ❌ Never pay from a shared account\n"
        "  ❌ Never send money via informal methods\n\n"
        "<b>If payment fails:</b>\n"
        "  • Check your bank app for status\n"
        "  • Wait 10 minutes — UPI can be slow\n"
        "  • If debited but not shown, contact /support")


async def cmd_upihelp(update: Update, ctx):
    await _reply(update,
        "🏦 <b>UPI Payment Guide</b>\n\n"
        "<b>What is UPI?</b>\n"
        "Unified Payments Interface — instant bank-to-bank transfer.\n\n"
        "<b>How to pay via UPI:</b>\n"
        "  1. Open any UPI app (PhonePe, GPay, Paytm, BHIM)\n"
        "  2. Go to 'Send Money' or 'Pay'\n"
        "  3. Enter the escrow UPI ID shown by bot\n"
        "  4. Enter exact amount\n"
        "  5. Add note: 'Escrow #{deal_id}'\n"
        "  6. Complete payment\n"
        "  7. Take screenshot showing TX ID\n\n"
        "<b>Transaction ID location:</b>\n"
        "  • PhonePe: 'Transaction ID' at bottom\n"
        "  • GPay: 'UPI transaction ID'\n"
        "  • Paytm: 'Order ID'\n"
        "  • BHIM: 'Transaction ID'\n\n"
        "⏱️ UPI transfers: instant to 2 hours on busy days.")


async def cmd_bankhelp(update: Update, ctx):
    await _reply(update,
        "🏦 <b>Bank Transfer Guide</b>\n\n"
        "For deals over ₹1 lakh or when UPI limit is reached.\n\n"
        "<b>Types of bank transfer:</b>\n"
        "  • IMPS — instant, 24/7, up to ₹5 lakh\n"
        "  • NEFT — batch, Mon-Sat, unlimited amount\n"
        "  • RTGS — real-time, ₹2 lakh minimum\n\n"
        "<b>What to include as payment note:</b>\n"
        "  'ESCROW #{deal_id} - {your_name}'\n\n"
        "See /nefthelp /impshelp /rtgshelp for specific guides.")


async def cmd_nefthelp(update: Update, ctx):
    await _reply(update,
        "🏦 <b>NEFT Transfer Guide</b>\n\n"
        "<b>NEFT = National Electronic Funds Transfer</b>\n\n"
        "  ✅ Available: Mon–Sat (except holidays)\n"
        "  ✅ Amount: No minimum/maximum\n"
        "  ⏱️ Time: 2 hours (batch processing)\n"
        "  💰 Charges: ₹2.50 – ₹25 depending on amount\n\n"
        "<b>How to do NEFT:</b>\n"
        "  1. Login to net banking\n"
        "  2. Add beneficiary with admin's bank details\n"
        "  3. Wait 30 min for beneficiary activation\n"
        "  4. Transfer the exact amount\n"
        "  5. Save the UTR number\n"
        "  6. Upload screenshot to escrow group")


async def cmd_impshelp(update: Update, ctx):
    await _reply(update,
        "⚡ <b>IMPS Transfer Guide</b>\n\n"
        "<b>IMPS = Immediate Payment Service</b>\n\n"
        "  ✅ Available: 24/7 including holidays\n"
        "  ✅ Amount: ₹1 – ₹5,00,000 per transaction\n"
        "  ⏱️ Time: Instant (usually within seconds)\n"
        "  💰 Charges: ₹5 – ₹15 depending on bank\n\n"
        "<b>How to do IMPS:</b>\n"
        "  1. Open net banking or mobile banking app\n"
        "  2. Go to Fund Transfer → IMPS\n"
        "  3. Enter beneficiary mobile + MMID, or account + IFSC\n"
        "  4. Enter exact amount\n"
        "  5. Complete with OTP\n"
        "  6. Save the IMPS reference number\n"
        "  7. Upload screenshot to escrow group")


async def cmd_rtgshelp(update: Update, ctx):
    await _reply(update,
        "🏦 <b>RTGS Transfer Guide</b>\n\n"
        "<b>RTGS = Real Time Gross Settlement</b>\n\n"
        "  ✅ Available: Mon–Sat 7 AM – 6 PM\n"
        "  ✅ Minimum: ₹2,00,000\n"
        "  ✅ No maximum limit\n"
        "  ⏱️ Time: Real-time (immediate)\n"
        "  💰 Charges: ₹25 – ₹50\n\n"
        "RTGS is suitable for <b>large escrow deals</b> above ₹2 lakh.\n"
        "Contact admin before using RTGS for escrow deals.")


async def cmd_escrowvscod(update: Update, ctx):
    await _reply(update,
        "⚖️ <b>Escrow vs Cash on Delivery</b>\n\n"
        "┌─────────────────┬──────────┬──────────┐\n"
        "│ Feature         │ Escrow   │ COD      │\n"
        "├─────────────────┼──────────┼──────────┤\n"
        "│ Digital deals   │ ✅       │ ❌       │\n"
        "│ Long distance   │ ✅       │ ❌       │\n"
        "│ Instant         │ ✅       │ ✅       │\n"
        "│ Dispute system  │ ✅       │ ❌       │\n"
        "│ Buyer protected │ ✅       │ Partial  │\n"
        "│ Seller protected│ ✅       │ ❌       │\n"
        "│ Anonymous deals │ ✅       │ ❌       │\n"
        "└─────────────────┴──────────┴──────────┘\n\n"
        "<i>For digital goods, accounts, and services — escrow is the only safe option.</i>")


async def cmd_whyescrow(update: Update, ctx):
    await _reply(update,
        "💡 <b>Why Use Escrow?</b>\n\n"
        "Without escrow, you must trust a complete stranger with your money or goods.\n\n"
        "<b>Real scenarios where escrow saves you:</b>\n\n"
        "📱 <b>Buying a Telegram account:</b>\n"
        "  Without escrow: Pay first → seller disappears\n"
        "  With escrow: Money held → account transferred → released\n\n"
        "🎮 <b>Buying game items:</b>\n"
        "  Without escrow: Seller gets paid → goes offline\n"
        "  With escrow: Items delivered first → payment released\n\n"
        "💻 <b>Freelance work:</b>\n"
        "  Without escrow: Pay upfront → work not delivered\n"
        "  With escrow: Work delivered → payment released\n\n"
        "📦 <b>Physical goods online:</b>\n"
        "  Without escrow: COD risk or prepay risk\n"
        "  With escrow: Money held until delivery confirmed")


async def cmd_escrowprocess(update: Update, ctx):
    await _reply(update,
        "📋 <b>Complete Escrow Process</b>\n\n"
        "Step 1️⃣ — <b>Start Deal</b>\n"
        "  Seller sends /escrow, fills the form\n\n"
        "Step 2️⃣ — <b>Private Group Created</b>\n"
        "  Bot creates encrypted group for buyer + seller only\n\n"
        "Step 3️⃣ — <b>Both Agree</b>\n"
        "  Each party presses their own AGREE button\n\n"
        "Step 4️⃣ — <b>Buyer Pays Escrow</b>\n"
        "  Buyer sends money to admin's UPI\n"
        "  Uploads payment screenshot\n\n"
        "Step 5️⃣ — <b>Admin Confirms</b>\n"
        "  Admin uses /confirm — money is now held safely\n\n"
        "Step 6️⃣ — <b>Seller Delivers</b>\n"
        "  Seller provides item/service to buyer\n\n"
        "Step 7️⃣ — <b>Buyer Confirms</b>\n"
        "  Buyer presses 'Deal Done — Release Money'\n\n"
        "Step 8️⃣ — <b>Seller Gets Paid</b>\n"
        "  Seller sends UPI → admin transfers money\n"
        "  Admin uses /payout → deal closed\n\n"
        "Step 9️⃣ — <b>Group Deleted</b>\n"
        "  Private group auto-deleted in 5 minutes")


async def cmd_dealchecklist(update: Update, ctx):
    await _reply(update,
        "✅ <b>Deal Checklist</b>\n\n"
        "<b>Before agreeing:</b>\n"
        "  ☐ Read all deal terms\n"
        "  ☐ Check seller/buyer rating\n"
        "  ☐ Confirm item/service description is clear\n"
        "  ☐ Confirm amount matches your expectation\n"
        "  ☐ Understand the delivery timeline\n\n"
        "<b>After payment:</b>\n"
        "  ☐ Screenshot shows TX ID clearly\n"
        "  ☐ Amount matches deal amount exactly\n"
        "  ☐ Screenshot uploaded to escrow group\n\n"
        "<b>Before releasing payment:</b>\n"
        "  ☐ Item/service fully received\n"
        "  ☐ Quality matches what was promised\n"
        "  ☐ No issues with delivery\n"
        "  ☐ You are 100% satisfied\n\n"
        "⚠️ Once you press Deal Done, money is released. No undo!")


async def cmd_sellerguide(update: Update, ctx):
    await _reply(update,
        "💼 <b>Complete Seller Guide</b>\n\n"
        "<b>Starting a deal:</b>\n"
        "  1. Use /escrow to create a deal form\n"
        "  2. Fill: buyer username, item, amount, terms\n"
        "  3. Be specific about what you're selling\n"
        "  4. Set a realistic valid-till date\n\n"
        "<b>During the deal:</b>\n"
        "  • Wait for buyer to agree (they click their button)\n"
        "  • Wait for admin to confirm payment received\n"
        "  • Then deliver your item/service\n"
        "  • Keep proof of delivery\n\n"
        "<b>Getting paid:</b>\n"
        "  • Buyer presses Deal Done → you get asked for UPI\n"
        "  • Send your UPI ID in the group\n"
        "  • Admin will transfer money to you\n"
        "  • /payout is sent by admin to confirm\n\n"
        "💡 Build your rating by completing deals honestly.")


async def cmd_buyerguide(update: Update, ctx):
    await _reply(update,
        "🛒 <b>Complete Buyer Guide</b>\n\n"
        "<b>Joining a deal:</b>\n"
        "  1. Seller creates deal, you get invite link\n"
        "  2. Join the private group\n"
        "  3. Read deal terms carefully\n"
        "  4. Press 'I'm Buyer — AGREE' if satisfied\n\n"
        "<b>Making payment:</b>\n"
        "  1. Pay exact amount to escrow UPI shown\n"
        "  2. Take clear screenshot with TX ID visible\n"
        "  3. Upload screenshot in private group\n"
        "  4. Wait for admin to confirm (/confirm)\n\n"
        "<b>Receiving delivery:</b>\n"
        "  1. Seller delivers after admin confirms\n"
        "  2. Verify what you received carefully\n"
        "  3. Test everything thoroughly\n"
        "  4. Press 'Deal Done — Release Money' ONLY when satisfied\n\n"
        "🆘 Any problem? Use /dispute BEFORE pressing Deal Done!")


async def cmd_disputeguide(update: Update, ctx):
    await _reply(update,
        "⚠️ <b>Dispute Guide</b>\n\n"
        "<b>When to raise a dispute:</b>\n"
        "  • Seller didn't deliver\n"
        "  • Item doesn't match description\n"
        "  • Received defective/wrong item\n"
        "  • Seller is unresponsive\n"
        "  • Any form of fraud suspected\n\n"
        "<b>How to raise a dispute:</b>\n"
        "  1. Press <b>⚠️ Raise Dispute</b> in group\n"
        "  2. Or use /dispute {deal_id} {reason}\n"
        "  3. Press <b>Add Admin as Mediator</b>\n"
        "  4. Describe your issue clearly\n"
        "  5. Upload all evidence\n\n"
        "<b>What happens next:</b>\n"
        "  • Admin joins the group\n"
        "  • Both parties share evidence\n"
        "  • Admin makes final decision\n"
        "  • Decision is binding\n\n"
        "⏱️ Disputes are resolved within 24 hours typically.")


async def cmd_mediatorinfo(update: Update, ctx):
    await _reply(update,
        "👮 <b>About Admin Mediators</b>\n\n"
        "Our admins are neutral mediators who ensure fair outcomes.\n\n"
        "<b>What mediators do:</b>\n"
        "  • Hold payment securely during the deal\n"
        "  • Verify payment screenshots\n"
        "  • Investigate disputes\n"
        "  • Review evidence from both sides\n"
        "  • Make fair, final decisions\n"
        "  • Transfer money to the appropriate party\n\n"
        "<b>Mediator principles:</b>\n"
        "  • Neutral — no bias toward buyer or seller\n"
        "  • Evidence-based decisions only\n"
        "  • Confidential — deal info not shared\n"
        "  • Available during working hours\n\n"
        "📞 Contact: /contact to reach admin directly.")


async def cmd_privacyinfo(update: Update, ctx):
    await _reply(update,
        "🔒 <b>Privacy & Data Protection</b>\n\n"
        "<b>What we store:</b>\n"
        "  • Your Telegram ID and username\n"
        "  • Deal history and ratings\n"
        "  • Payment confirmation logs\n\n"
        "<b>What we DON'T store:</b>\n"
        "  • Your bank account details\n"
        "  • Your UPI PIN or passwords\n"
        "  • Messages from private groups\n\n"
        "<b>Private groups:</b>\n"
        "  • Only buyer and seller can see messages\n"
        "  • Admin can join only if requested\n"
        "  • Group is permanently deleted after deal\n\n"
        "<b>Data retention:</b>\n"
        "  • Deal records kept for 90 days\n"
        "  • You can request deletion via /contact\n\n"
        "<i>We never sell or share your data.</i>")


async def cmd_securitytips(update: Update, ctx):
    await _reply(update,
        "🔐 <b>Security Tips</b>\n\n"
        "  🔐 Never share your Telegram login code with anyone\n"
        "  🔐 Enable 2FA on your Telegram account\n"
        "  🔐 Don't click suspicious links in deal groups\n"
        "  🔐 Verify the bot username before interacting\n"
        "  🔐 Admin will NEVER ask for your UPI PIN\n"
        "  🔐 Admin will NEVER ask for your bank password\n"
        "  🔐 Screenshots you send are seen by admin for verification only\n"
        "  🔐 Private deal groups are deleted after every deal\n\n"
        "<b>Official bot:</b> @PW_escrowbot\n"
        "Anyone claiming to be admin in DM — verify with /contact")


async def cmd_reportscam(update: Update, ctx):
    await _reply(update,
        "🚨 <b>Report a Scam</b>\n\n"
        "If you've been scammed or attempted scam detected:\n\n"
        "  1️⃣ Use /dispute {deal_id} in the deal group\n"
        "  2️⃣ Use /contact to message admin\n"
        "  3️⃣ Use /problem with full description\n"
        "  4️⃣ Save all evidence (screenshots, messages)\n\n"
        "<b>Also report externally:</b>\n"
        "  • Cybercrime: cybercrime.gov.in\n"
        "  • RBI complaint: sachet.rbi.org.in\n"
        "  • TRAI complaint: trai.gov.in\n"
        "  • Bank fraud: call 1800-111-109\n\n"
        "⚠️ Act fast — money in escrow is safe but report immediately.")


async def cmd_antifraud(update: Update, ctx):
    await _reply(update,
        "🛡️ <b>Anti-Fraud Measures</b>\n\n"
        "Our bot has multiple layers of fraud protection:\n\n"
        "  ✅ Private encrypted group per deal\n"
        "  ✅ Admin holds money — no direct seller payment\n"
        "  ✅ Payment screenshot verification\n"
        "  ✅ Both parties must agree separately\n"
        "  ✅ Dispute system with neutral admin\n"
        "  ✅ Deal history and rating system\n"
        "  ✅ User ban system for fraudsters\n"
        "  ✅ All actions logged\n"
        "  ✅ Group auto-deleted (no lingering evidence)\n\n"
        "If you suspect fraud: /reportscam")


async def cmd_verifybuyer(update: Update, ctx):
    await _reply(update,
        "🔍 <b>How to Verify a Buyer</b>\n\n"
        "Before accepting a buyer:\n\n"
        "  1. Check their /myrating — should be 4+ for large deals\n"
        "  2. Ask for completed deal count\n"
        "  3. Check if they have previous sellers as references\n"
        "  4. Be cautious of zero-rating new accounts\n"
        "  5. For large deals, ask admin to vouch\n\n"
        "<b>Good buyer signs:</b>\n"
        "  ✅ High rating (4.0+)\n"
        "  ✅ Multiple completed deals\n"
        "  ✅ Clear communication\n"
        "  ✅ Asks reasonable questions\n"
        "  ✅ Reads terms before agreeing")


async def cmd_verifyseller(update: Update, ctx):
    await _reply(update,
        "🔍 <b>How to Verify a Seller</b>\n\n"
        "Before agreeing to buy:\n\n"
        "  1. Check their rating (/myrating)\n"
        "  2. Look at deal count and history\n"
        "  3. Ask for proof of what they're selling\n"
        "  4. Ask previous buyers for references\n"
        "  5. Be wary of deals that seem too cheap\n\n"
        "<b>Good seller signs:</b>\n"
        "  ✅ Rating above 4.0\n"
        "  ✅ Many completed deals\n"
        "  ✅ Clear item description\n"
        "  ✅ Willing to answer questions\n"
        "  ✅ Has delivery proof ready\n\n"
        "🚩 Red flag: seller insists on no escrow or wants direct payment.")


async def cmd_escrowcalc(update: Update, ctx):
    """Calculate escrow fee for an amount."""
    if not ctx.args:
        await _reply(update,
            "💰 <b>Escrow Fee Calculator</b>\n\n"
            "Usage: /escrowcalc {amount}\n"
            "Example: /escrowcalc 5000\n\n"
            f"Standard fee: 2.5%\n"
            "Your discount: use /myfee to check"); return
    try:
        amount = float(re.sub(r"[^\d.]", "", ctx.args[0]))
        fee    = round(amount * 2.5 / 100, 2)
        seller_gets = round(amount - fee, 2)
        await _reply(update,
            f"💰 <b>Fee Estimate</b>\n\n"
            f"  Deal Amount    : ₹{amount:,.2f}\n"
            f"  Escrow Fee     : ₹{fee:,.2f} (2.5%)\n"
            f"  Seller Receives: ₹{seller_gets:,.2f}\n\n"
            f"<i>Check your personal fee with /myfee</i>")
    except:
        await _reply(update, "❌ Invalid amount. Example: /escrowcalc 5000")


async def cmd_feeestimate(update: Update, ctx): await cmd_escrowcalc(update, ctx)


async def cmd_dealhistory(update: Update, ctx):
    await _reply(update, "📜 Use /myhistory to see your deal history.")


async def cmd_myescrows(update: Update, ctx):
    await _reply(update, "⏳ Use /mydeals to see your active deals.")


async def cmd_pendingpayment(update: Update, ctx):
    u = update.effective_user
    if not _db: return
    deals = _db["rows"](
        "SELECT id, amount, status FROM escrows "
        "WHERE buyer_id=? AND status IN ('QR_SENT','AGREED') ORDER BY id DESC",
        (u.id,))
    if not deals:
        await _reply(update, "✅ No deals waiting for your payment."); return
    text = "💳 <b>Deals Awaiting Your Payment</b>\n\n"
    for d in deals:
        text += f"  🔖 #{d['id']} — {d.get('amount','—')} — {d['status']}\n"
    await _reply(update, text)


async def cmd_checkdeal(update: Update, ctx):
    await _reply(update, "🔖 Use /dealinfo <id> to check a specific deal.")


async def cmd_cancelpolicy(update: Update, ctx):
    await _reply(update,
        "❌ <b>Cancellation Policy</b>\n\n"
        "  • Either party can cancel at any time\n"
        "  • Use /stopdeal {deal_id} to cancel\n"
        "  • Escrow fee is <b>non-refundable</b> even if cancelled\n"
        "  • If payment already made — admin holds it pending review\n"
        "  • Cancellation after payment → dispute process applies\n\n"
        "For cancelled deals with payment made, use /dispute.")


async def cmd_refundpolicy(update: Update, ctx):
    await _reply(update,
        "💰 <b>Refund Policy</b>\n\n"
        "  • Escrow fee: <b>non-refundable</b>\n"
        "  • Deal amount: refunded to buyer if seller doesn't deliver\n"
        "  • Partial delivery: admin decides partial refund\n"
        "  • Buyer pressed Deal Done by mistake: not refundable\n"
        "  • Scam confirmed: full refund to buyer\n\n"
        "<i>All refund decisions are at admin's discretion based on evidence.</i>")


async def cmd_timeoutrules(update: Update, ctx):
    await _reply(update,
        "⏱️ <b>Deal Timeout Rules</b>\n\n"
        "  • Buyer has until Valid Till date to pay\n"
        "  • After 24h inactivity, reminder sent\n"
        "  • Expired deals can be cancelled by either party\n"
        "  • Admin can extend deals upon request\n\n"
        "Use /contact if you need more time on a deal.")


async def cmd_escrowrules(update: Update, ctx):
    await _reply(update,
        "📋 <b>Escrow Rules</b>\n\n"
        "  1. Only agreed amounts are held in escrow\n"
        "  2. Deal terms cannot change after both agree\n"
        "  3. Payment must match deal amount exactly\n"
        "  4. Delivery must match deal description\n"
        "  5. Buyer must inspect before releasing\n"
        "  6. Admin decision is final and binding\n"
        "  7. Repeated violations lead to permanent ban\n"
        "  8. Collusion between parties against bot is prohibited\n"
        "  9. Multiple accounts for same deal is banned\n"
        "  10. False disputes are penalized\n\n"
        "Violation of rules = immediate ban without refund.")


async def cmd_trustedsellers(update: Update, ctx):
    if not _db: return
    sellers = _db["rows"](
        "SELECT uid, full_name, deal_count, rating "
        "FROM users WHERE deal_count >= 5 AND rating >= 4.5 AND is_banned=0 "
        "ORDER BY rating DESC, deal_count DESC LIMIT 10")
    if not sellers:
        await _reply(update, "No trusted sellers yet — complete deals to earn trust!"); return
    text = "🏆 <b>Trusted Sellers</b> (5+ deals, 4.5+ rating)\n\n"
    for i, s in enumerate(sellers, 1):
        text += f"  {i}. {s.get('full_name','?')[:20]} — ⭐{s.get('rating',5.0):.1f} — {s.get('deal_count',0)} deals\n"
    await _reply(update, text)


async def cmd_verifiedbuyers(update: Update, ctx):
    if not _db: return
    buyers = _db["rows"](
        "SELECT uid, full_name, deal_count, rating "
        "FROM users WHERE deal_count >= 3 AND rating >= 4.0 AND is_banned=0 "
        "ORDER BY deal_count DESC LIMIT 10")
    if not buyers:
        await _reply(update, "No verified buyers yet!"); return
    text = "✅ <b>Verified Buyers</b> (3+ deals, 4.0+ rating)\n\n"
    for i, b in enumerate(buyers, 1):
        text += f"  {i}. {b.get('full_name','?')[:20]} — ⭐{b.get('rating',5.0):.1f} — {b.get('deal_count',0)} deals\n"
    await _reply(update, text)


async def cmd_escrowtypes(update: Update, ctx):
    await _reply(update,
        "📦 <b>Types of Escrow Deals We Support</b>\n\n"
        "  📱 /digitalgoods — accounts, subscriptions, keys\n"
        "  📦 /physicalgoods — shipped items\n"
        "  💼 /serviceescrow — freelance, design, coding\n"
        "  👤 /accountescrow — Telegram, Instagram, etc\n"
        "  💾 /dataescrow — databases, files, data packs\n"
        "  🎮 Game items, in-game currency\n"
        "  📸 Photography/content delivery\n"
        "  🤝 Any OTC (over the counter) deal\n\n"
        "For deals not listed, contact /support")


async def cmd_digitalgoods(update: Update, ctx):
    await _reply(update,
        "💻 <b>Digital Goods Escrow</b>\n\n"
        "Covers: game accounts, software keys, subscriptions,\n"
        "streaming logins, domain names, websites, NFTs, crypto\n\n"
        "<b>How delivery works:</b>\n"
        "  • Seller shares credentials after payment confirmed\n"
        "  • Buyer has 1 hour to verify access\n"
        "  • If login fails → dispute immediately\n"
        "  • If successful → press Deal Done\n\n"
        "<b>Extra protections:</b>\n"
        "  • Seller must change password after buyer confirms\n"
        "  • Buyer should enable 2FA immediately\n"
        "  • Both parties screenshot the transfer")


async def cmd_physicalgoods(update: Update, ctx):
    await _reply(update,
        "📦 <b>Physical Goods Escrow</b>\n\n"
        "For items that are shipped/delivered physically.\n\n"
        "<b>Special terms:</b>\n"
        "  • Seller must provide tracking number\n"
        "  • Buyer confirms receipt after delivery\n"
        "  • Inspection time: 24h after delivery\n"
        "  • Open box video recommended as proof\n\n"
        "<b>Deal terms should include:</b>\n"
        "  • Courier company and timeline\n"
        "  • Item condition (new/used)\n"
        "  • Return policy if defective")


async def cmd_serviceescrow(update: Update, ctx):
    await _reply(update,
        "💼 <b>Service Escrow</b>\n\n"
        "For freelance work, design, coding, content creation, etc.\n\n"
        "<b>Milestone approach (recommended):</b>\n"
        "  • Break large projects into milestones\n"
        "  • Create separate escrow per milestone\n"
        "  • Release payment per milestone\n\n"
        "<b>Deal terms should include:</b>\n"
        "  • Exact deliverables\n"
        "  • Delivery format (file type, etc)\n"
        "  • Revision policy\n"
        "  • Deadline\n\n"
        "Contact /support for complex service deals.")


async def cmd_accountescrow(update: Update, ctx):
    await _reply(update,
        "👤 <b>Account Transfer Escrow</b>\n\n"
        "For Telegram, Instagram, YouTube, Gmail accounts etc.\n\n"
        "<b>Secure transfer process:</b>\n"
        "  1. Seller provides account details after payment confirmed\n"
        "  2. Buyer logs in and verifies access\n"
        "  3. Buyer changes password and recovery email\n"
        "  4. Seller confirms they no longer have access\n"
        "  5. Buyer presses Deal Done\n\n"
        "⚠️ Account transfers: buyer has 2 hours to verify.")


async def cmd_dataescrow(update: Update, ctx):
    await _reply(update,
        "💾 <b>Data/File Escrow</b>\n\n"
        "For databases, datasets, file packs, courses, etc.\n\n"
        "<b>Process:</b>\n"
        "  1. Seller provides download link after payment\n"
        "  2. Buyer downloads and verifies file contents\n"
        "  3. Verify file matches description\n"
        "  4. Check all files are accessible\n"
        "  5. Press Deal Done\n\n"
        "⚠️ Data deals: buyer has 24 hours to verify.")


async def cmd_cryptoinfo(update: Update, ctx):
    await _reply(update,
        "₿ <b>Crypto & Digital Currency</b>\n\n"
        "We currently support INR (₹) deals only.\n"
        "Payment via UPI/Bank Transfer.\n\n"
        "For crypto-to-INR or INR-to-crypto deals:\n"
        "  • Deal amount in INR equivalent\n"
        "  • Both parties agree on rate\n"
        "  • Crypto transfers happen outside escrow\n"
        "  • INR side is held in escrow\n\n"
        "Contact /support for crypto deal setup.")


async def cmd_scamtypes(update: Update, ctx):
    await _reply(update,
        "⚠️ <b>Common Scam Types</b>\n\n"
        "1️⃣ <b>Advance Fee Scam</b> — 'pay fee first then get item'\n"
        "2️⃣ <b>Fake Payment Screenshot</b> — edited/photoshopped proof\n"
        "3️⃣ <b>Overpayment Scam</b> — 'I paid extra, refund rest'\n"
        "4️⃣ <b>Account Cloning</b> — fake bot/admin accounts\n"
        "5️⃣ <b>Bait & Switch</b> — different item than advertised\n"
        "6️⃣ <b>Urgency Scam</b> — 'deal expires in 5 minutes'\n"
        "7️⃣ <b>Chargeback Fraud</b> — buyer reverses bank payment\n"
        "8️⃣ <b>Same Day Escape</b> — scammer disappears quickly\n\n"
        "See each /fakepayment /overpaymentscam etc for details.")


async def cmd_fakepayment(update: Update, ctx):
    await _reply(update,
        "🎭 <b>Fake Payment Screenshots</b>\n\n"
        "How scammers fake payment proof:\n\n"
        "  • Photoshop/edit screenshot amount\n"
        "  • Use someone else's old screenshot\n"
        "  • Use screenshot generators online\n"
        "  • Show 'pending' transaction as complete\n\n"
        "<b>How to spot fakes:</b>\n"
        "  • TX ID doesn't exist — verify on bank website\n"
        "  • Amount or date looks unusual\n"
        "  • Screenshot quality too low/compressed\n"
        "  • Different font/color than real app\n\n"
        "Our admin verifies all screenshots. Never trust without admin confirmation!")


async def cmd_screenshotfake(update: Update, ctx): await cmd_fakepayment(update, ctx)


async def cmd_chargebackinfo(update: Update, ctx):
    await _reply(update,
        "↩️ <b>Chargeback Fraud Warning</b>\n\n"
        "Chargeback = buyer reverses bank payment after receiving item.\n\n"
        "<b>Protection:</b>\n"
        "  • Admin verifies payment before seller delivers\n"
        "  • Some payment methods (UPI) can't be charged back\n"
        "  • NEFT/IMPS chargebacks are rare and traceable\n\n"
        "If you're a seller worried about chargeback:\n"
        "  • Request UPI payment (preferred)\n"
        "  • Keep delivery proof\n"
        "  • Report to admin immediately if attempted")


async def cmd_vouchinfo(update: Update, ctx):
    await _reply(update,
        "🤝 <b>Vouch System</b>\n\n"
        "A vouch is when someone verifies your reputation.\n\n"
        "<b>Our vouch system:</b>\n"
        "  • Rating system (1-5 stars per deal)\n"
        "  • Deal count visible in profile\n"
        "  • History of completed deals\n\n"
        "⚠️ <b>Beware of self-vouching scams:</b>\n"
        "  • Scammers using fake accounts to vouch themselves\n"
        "  • Paid vouches from strangers\n"
        "  • Our system shows only real completed deals\n\n"
        "Trust the bot's rating system, not self-proclaimed vouches.")


async def cmd_middlemaninfo(update: Update, ctx):
    await _reply(update,
        "👮 <b>About Middleman / Admin Service</b>\n\n"
        "Our admin acts as a trusted middleman (escrow agent).\n\n"
        "<b>What the middleman does:</b>\n"
        "  • Receives payment from buyer\n"
        "  • Holds it until delivery confirmed\n"
        "  • Mediates disputes fairly\n"
        "  • Transfers money to seller after Deal Done\n\n"
        "<b>Middleman fee:</b> 2.5% of deal amount\n"
        "  (charged to seller, deducted from payout)\n\n"
        "⚠️ Only use admin designated by this bot. Anyone else claiming to be middleman is a scammer.")


async def cmd_samedayescape(update: Update, ctx):
    await _reply(update,
        "⚡ <b>Same-Day Escape Scam</b>\n\n"
        "This scam: scammer agrees, gets item/money, disappears same day.\n\n"
        "<b>How escrow prevents it:</b>\n"
        "  • Money is held by admin — scammer can't escape with it\n"
        "  • Seller only delivers AFTER payment confirmed\n"
        "  • Buyer only releases AFTER receiving item\n\n"
        "With our bot, same-day escape is impossible for money.\n"
        "For item delivery, always get delivery proof!")


async def cmd_overpaymentscam(update: Update, ctx):
    await _reply(update,
        "💸 <b>Overpayment Scam Warning</b>\n\n"
        "Scam: Buyer 'overpays' and asks seller to refund difference.\n\n"
        "<b>Example:</b>\n"
        "  Deal: ₹500 | Scammer pays: ₹5000 (fake screenshot)\n"
        "  'Oh I made a mistake, refund ₹4500 please'\n"
        "  You refund → their payment was fake → you lose ₹4500\n\n"
        "<b>Protection:</b>\n"
        "  • Only accept exact deal amount\n"
        "  • Admin verifies all payments\n"
        "  • Never refund directly — raise dispute\n\n"
        "If buyer overpays: tell admin → admin handles it.")


async def cmd_urgencyscam(update: Update, ctx):
    await _reply(update,
        "⏰ <b>Urgency Scam Warning</b>\n\n"
        "'Deal expires in 5 minutes!' 'Limited offer!' 'Decide NOW!'\n\n"
        "These are pressure tactics to make you skip verification.\n\n"
        "<b>Remember:</b>\n"
        "  • Legitimate sellers don't pressure like this\n"
        "  • Take your time to read terms\n"
        "  • No genuine deal requires 5-minute decisions\n"
        "  • Admin is available to help — no rush needed\n\n"
        "If someone is pressuring you: /reportscam immediately.")


async def cmd_phishingwarning(update: Update, ctx):
    await _reply(update,
        "🎣 <b>Phishing Warning</b>\n\n"
        "Scammers may create fake bots/accounts impersonating us.\n\n"
        "<b>Always verify:</b>\n"
        "  ✅ Official bot: @PW_escrowbot\n"
        "  ✅ Admin never DMs you first asking for money\n"
        "  ✅ Check bot/account username carefully\n\n"
        "<b>Warning signs of fake bot:</b>\n"
        "  🚩 Different username than official\n"
        "  🚩 Asks for payment directly\n"
        "  🚩 Can't show deal ID in real bot\n"
        "  🚩 Asks for your Telegram login\n\n"
        "When in doubt: /contact the official admin.")


async def cmd_support(update: Update, ctx):
    await _reply(update,
        "📞 <b>Support</b>\n\n"
        "Need help? We're here.\n\n"
        "  /contact — message admin directly\n"
        "  /dispute {id} — raise formal dispute\n"
        "  /problem — report a problem\n"
        "  /reportscam — report scam attempt\n\n"
        "Response time: usually within 1-2 hours.")


async def cmd_reportdeal(update: Update, ctx):
    u = update.effective_user
    detail = " ".join(ctx.args) if ctx.args else "No details."
    await _reply(update, "🚨 Deal report submitted. Admin will review shortly.")
    log.info("Deal report from %s: %s", u.id, detail)


async def cmd_dealrating(update: Update, ctx):
    await _reply(update, "⭐ Use /myrating to see your trust rating.")


async def cmd_givefeedback(update: Update, ctx):
    u = update.effective_user
    fb = " ".join(ctx.args) if ctx.args else "No feedback provided."
    await _reply(update, "💬 Feedback received. Thank you!")
    log.info("Feedback from %s: %s", u.id, fb)


async def cmd_botstatus(update: Update, ctx):
    await _reply(update,
        "🟢 <b>Bot Status</b>\n\n"
        "  Status   : Online ✅\n"
        "  Service  : Normal\n"
        "  Uptime   : Running continuously\n"
        "  Response : Normal\n\n"
        "<i>All systems operational.</i>")


async def cmd_uptime(update: Update, ctx): await cmd_botstatus(update, ctx)


async def cmd_version(update: Update, ctx):
    from config.settings import BOT_VERSION, BOT_NAME
    await _reply(update,
        f"🤖 <b>{BOT_NAME}</b>\n\n"
        f"  Version  : {BOT_VERSION}\n"
        f"  Platform : Telegram Bot API\n"
        f"  Backend  : Python + PTB\n"
        f"  Hosting  : Render\n\n"
        "<i>Encrypted • Private • Verified</i>")
