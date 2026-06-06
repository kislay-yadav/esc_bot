"""
╔══════════════════════════════════════════════════════╗
║         ESCROWER BOT — MASTER CONFIG                 ║
║  Change ANYTHING here. Never touch main.py.          ║
╚══════════════════════════════════════════════════════╝

HOW TO USE:
  - Edit values below
  - Push to GitHub / redeploy on Render
  - Bot picks up all changes automatically
  - main.py is NEVER modified
"""

import os

# ── Bot Identity ─────────────────────────────────────
BOT_NAME         = os.getenv("BOT_NAME",   "OTC Escrow By PAGAL Bot")
BOT_VERSION      = "v9.1"
BOT_SUPPORT_USER = os.getenv("SUPPORT_USER", "@PW_support")   # shown in /contact

# ── Credentials (set as Render env vars) ─────────────
BOT_TOKEN        = os.getenv("BOT_TOKEN", "")
ADMIN_IDS        = [int(x) for x in os.getenv("ADMIN_IDS","0").split(",") if x.strip() and x!="0"]
ADMIN_PASSWORD   = os.getenv("ADMIN_PASSWORD", "admin123")
LOG_CHANNEL      = int(os.getenv("LOG_GROUP_ID", "0"))

# ── Payment ───────────────────────────────────────────
UPI_ID           = os.getenv("UPI_ID", "sahil8896@airtel")
QR_PATH          = os.getenv("QR_PATH", "qr.png")
ESCROW_FEE_PCT   = float(os.getenv("ESCROW_FEE", "2.5"))
MIN_DEAL_AMOUNT  = float(os.getenv("MIN_DEAL", "10"))      # ₹ minimum
MAX_DEAL_AMOUNT  = float(os.getenv("MAX_DEAL", "500000"))  # ₹ maximum
CURRENCY_SYMBOL  = "₹"
CURRENCY_CODE    = "INR"

# ── Telethon Userbot ──────────────────────────────────
TG_API_ID        = int(os.getenv("TG_API_ID",   "0"))
TG_API_HASH      = os.getenv("TG_API_HASH",     "")
TELETHON_SESSION = os.getenv("TELETHON_SESSION","")
USERBOT_ENABLED  = bool(TG_API_ID and TG_API_HASH)

# ── Render / Server ───────────────────────────────────
RENDER_URL       = os.getenv("RENDER_URL", "")
PORT             = int(os.getenv("PORT", "8080"))
PING_INTERVAL    = 540     # seconds between self-pings
DB_PATH          = os.getenv("DB_PATH", "escrow.db")

# ── Deal Group Settings ───────────────────────────────
GROUP_AUTO_DELETE_DELAY = 300   # seconds (5 min) before group deleted after close
DEAL_ID_MIN      = 100000       # random deal ID range
DEAL_ID_MAX      = 999999
MAX_ACTIVE_DEALS = 5            # max active deals per user

# ── OCR Settings ──────────────────────────────────────
OCR_ENABLED      = True
# Patterns to extract transaction ID from payment screenshots
TX_PATTERNS = [
    r"(?:Transaction\s*ID|TXN\s*ID|Txn\s*ID)[:\s#]*([A-Z0-9]{8,30})",
    r"(?:UTR|UPI\s*Ref|Ref\s*No)[:\s#.]*([A-Z0-9]{8,20})",
    r"(?:PhonePe|GPay|Paytm)\s*(?:Transaction\s*ID)?[:\s#]*([A-Z0-9]{10,30})",
    r"T\d{20,30}",                          # PhonePe format
    r"\b([A-Z]{2}\d{10,20})\b",             # UTR format
    r"(?:Order\s*ID|Ref\s*ID)[:\s]*([A-Z0-9\-]{6,20})",
]
# Patterns to extract amount
AMOUNT_PATTERNS = [
    r"₹\s*([0-9,]+(?:\.\d{1,2})?)",
    r"Rs\.?\s*([0-9,]+(?:\.\d{1,2})?)",
    r"INR\s*([0-9,]+(?:\.\d{1,2})?)",
    r"(?:Amount|Amt|Paid|Total)[:\s₹]*([0-9,]+(?:\.\d{1,2})?)",
    r"([0-9,]+(?:\.\d{2})?)\s*(?:paid|debited|transferred|sent)",
]

# ── Referral System ───────────────────────────────────
REFERRAL_ENABLED         = True
REFERRAL_DISCOUNT_PER_INVITE = 0.5    # % fee discount per successful invite
REFERRAL_MAX_DISCOUNT    = 50.0       # max total discount %

# ── Feature Flags — turn on/off without code change ──
FEATURE_REFERRAL        = True
FEATURE_RATINGS         = True
FEATURE_DISPUTES        = True
FEATURE_OCR             = True
FEATURE_AUTO_REMIND     = True   # remind parties if no action in 24h
FEATURE_BROADCAST       = True   # allow admin broadcast
FEATURE_VOUCHERS        = False  # future feature
FEATURE_MULTI_CURRENCY  = False  # future feature

# ── Auto-reminder (hours of inactivity before reminder) ─
REMIND_AFTER_HOURS = 24

# ── Messages — edit without code change ──────────────
MSG_WELCOME_FOOTER = "🔒 End-to-End Encrypted  •  Private  •  Verified"
MSG_FEE_WARNING    = "⚠️ Escrow fee is non-refundable even if cancelled."
MSG_TERMS_SHORT    = "Standard escrow terms apply. Admin decision is final."

# ── Themes for deal images ────────────────────────────
THEMES = [
    {"bg":(10,12,30),  "a":(0,200,255),  "b":(0,100,200)},
    {"bg":(8,25,15),   "a":(0,220,100),  "b":(0,150,60)},
    {"bg":(30,8,50),   "a":(180,60,255), "b":(120,0,200)},
    {"bg":(40,20,5),   "a":(255,150,0),  "b":(200,80,0)},
    {"bg":(5,20,40),   "a":(60,200,255), "b":(0,120,200)},
    {"bg":(25,5,5),    "a":(255,80,80),  "b":(180,0,0)},
]
