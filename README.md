# 🔐 Escrower Bot — Ultra Edition

A full-featured Telegram escrow bot with private deal groups, rich visual cards,
OCR payment verification, and Render-ready deployment with auto-ping keep-alive.

---

## ✨ What's New (vs original)

| Feature | Original | Ultra Edition |
|---|---|---|
| Private escrow groups | ❌ | ✅ Auto-created per deal |
| Group auto-delete on close/cancel | ❌ | ✅ |
| `/myprofile` with visual card | ❌ | ✅ |
| `/mytransactions` `/myhistory` `/mydeals` | ❌ | ✅ |
| `/mystats` `/myrating` | ❌ | ✅ |
| User rating & reputation system | ❌ | ✅ |
| Deal image cards (visual) | ❌ | ✅ |
| Welcome image on `/start` | basic | ✅ Rich |
| Render deployment config | ❌ | ✅ |
| Auto self-ping keep-alive | ❌ | ✅ |
| HTTP health endpoint | ❌ | ✅ |
| Telegram command menu | ❌ | ✅ Full list |
| User profiles DB table | ❌ | ✅ |
| Rating after deal closes | ❌ | ✅ DM prompt |

---

## 📁 Files

```
escrower/
├── main.py          ← the entire bot (single file)
├── requirements.txt ← Python dependencies
├── render.yaml      ← Render deployment config
├── Procfile         ← for Render / Heroku
├── qr.jpg           ← your UPI QR image (place here)
└── README.md        ← this file
```

---

## 🚀 Deploy on Render (Free Tier)

### Step 1 — Push to GitHub

```bash
git init
git add .
git commit -m "Escrower Bot Ultra"
git remote add origin https://github.com/YOUR_USER/escrower-bot.git
git push -u origin main
```

### Step 2 — Create Render Service

1. Go to https://render.com → **New** → **Web Service**
2. Connect your GitHub repo
3. Render auto-detects `render.yaml` — just confirm settings
4. Set these **Environment Variables** in the Render dashboard:

| Variable | Value |
|---|---|
| `BOT_TOKEN` | your bot token from @BotFather |
| `ADMIN_IDS` | your Telegram user ID (e.g. `8156053366`) |
| `LOG_GROUP_ID` | your log group chat ID |
| `MAIN_GROUP_INVITE` | your main group invite link |
| `UPI_ID` | your UPI ID |
| `ADMIN_PASSWORD` | a strong password |
| `RENDER_URL` | *(leave empty for now — fill in after first deploy)* |

5. Click **Deploy** and wait for the build to finish.

### Step 3 — Set RENDER_URL for auto-ping

After your first deploy succeeds, Render gives you a URL like:
```
https://escrower-bot.onrender.com
```

Go back to **Environment Variables** and set:
```
RENDER_URL = https://escrower-bot.onrender.com
```

Redeploy. The bot will now ping itself every 10 minutes to stay awake on the free tier.

---

## ⚙️ Local Development

```bash
pip install -r requirements.txt
BOT_TOKEN=xxx ADMIN_IDS=123 python main.py
```

---

## 🤖 Bot Commands

### For Everyone
| Command | Description |
|---|---|
| `/start` | Welcome screen & profile shortcuts |
| `/help` | Full command list |
| `/form` or `/escrow` | Start a new escrow deal (seller) |
| `/deals` | List active deals in this group |
| `/stopdeal <id>` | Cancel a deal (seller/buyer/admin) |
| `/myprofile` | Your visual profile card |
| `/mytransactions` | All your deals |
| `/myhistory` | Completed & cancelled deals |
| `/mydeals` | Active deals you're in |
| `/mystats` | Your deal statistics |
| `/myrating` | Your trust score |
| `/id` | Get user/chat IDs |

### Admin Only
| Command | Description |
|---|---|
| `/confirm <id>` | Mark payment confirmed, close deal |
| `/kick` `/ban` `/unban <id>` | User management |
| `/mute` `/unmute` | Silence a user |
| `/warn <reason>` `/warnings` `/clearwarn` | Warning system |
| `/promote` `/demote` | Admin rights |
| `/pin` `/unpin` | Message pinning |
| `/lock` `/unlock` | Group message permissions |
| `/purge [n]` `/del` | Message deletion |
| `/slowmode <sec>` | Set slowmode |
| `/announce <text>` | Send announcement |
| `/poll Q\|opt1\|opt2` | Create a poll |
| `/stats` | Group statistics |
| `/auth <password>` | Session admin login |

---

## 🔐 How a Deal Works

1. **Seller** types `/form` — bot sends a template
2. **Seller** fills in buyer, amount, details and sends it back
3. Bot posts a **deal card** with AGREE/CANCEL buttons
4. **Both** seller and buyer press AGREE ✅
5. Bot creates a **private group** (buyer + seller only) or sends deal DM
6. **Buyer** pays via UPI QR shown by bot
7. **Buyer** uploads the payment screenshot in the group
8. Bot OCR-reads the screenshot, extracts TX ID + amount
9. **Admin** runs `/confirm <id>` to close the deal
10. Both parties get a **rating prompt** via DM
11. Private group auto-deletes after 2 minutes

---

## 📝 Notes

- Telegram Bot API does **not** allow bots to create groups via API.
  When the private group feature triggers, the bot sends deal details via DM
  to both parties as a fallback. To enable true private groups, you would need
  a user-bot (Telethon/Pyrogram) alongside the bot token.
- `easyocr` downloads ~200 MB of model files on first run — this is normal.
- The SQLite database (`escrower.db`) is stored on Render's ephemeral disk.
  For persistence across deploys, attach a **Render Disk** or switch to PostgreSQL.

---

*Built with ❤️ — Escrower Ultra Edition*
