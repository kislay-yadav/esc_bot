#!/usr/bin/env python3
"""
Run ONCE locally to get your TELETHON_SESSION string.

  pip install telethon
  python generate_session.py

Paste the output string into Render env var TELETHON_SESSION.
"""
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession

API_ID   = int(input("TG_API_ID   : ").strip())
API_HASH = input("TG_API_HASH : ").strip()

async def main():
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.start()
    me = await client.get_me()
    session_str = client.session.save()
    print(f"\n✅ Logged in as {me.first_name} (id={me.id})")
    print("\n" + "="*60)
    print("PASTE THIS INTO RENDER → TELETHON_SESSION :")
    print("="*60)
    print(session_str)
    print("="*60)
    await client.disconnect()

asyncio.run(main())
