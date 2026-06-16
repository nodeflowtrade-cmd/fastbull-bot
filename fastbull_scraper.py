import requests
from bs4 import BeautifulSoup
import os
import datetime
import sys
import asyncio
from telegram import Bot
from discord_webhook import DiscordWebhook

# ------- YOUR CREDENTIALS (stored as GitHub Secrets) -------
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN_BOTFATHER", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "")

# Validate secrets
if not TELEGRAM_TOKEN:
    print("ERROR: TELEGRAM_TOKEN_BOTFATHER not set", file=sys.stderr)
    sys.exit(1)
if not TELEGRAM_CHAT_ID:
    print("ERROR: TELEGRAM_CHAT_ID not set", file=sys.stderr)
    sys.exit(1)
if not DISCORD_WEBHOOK:
    print("ERROR: DISCORD_WEBHOOK not set", file=sys.stderr)
    sys.exit(1)

print("[DEBUG] All secrets loaded successfully ✓")

# ------- ASSET LIST -------
assets = {
    "EUR/USD": "https://www.fastbull.com/quotation-detail/EURUSD?exchange=8100",
    "GBP/USD": "https://www.fastbull.com/quotation-detail/GBPUSD?exchange=8100",
    "USD/JPY": "https://www.fastbull.com/quotation-detail/USDJPY?exchange=8100",
    "EUR/GBP": "https://www.fastbull.com/quotation-detail/EURGBP?exchange=8200",
    "EUR/JPY": "https://www.fastbull.com/quotation-detail/EURJPY?exchange=8200",
    "GBP/JPY": "https://www.fastbull.com/quotation-detail/GBPJPY?exchange=8200",
    "XAU/USD": "https://www.fastbull.com/quotation-detail/XAUUSD?exchange=8500",
    "S&P 500": "https://www.fastbull.com/quotation-detail/SPX?exchange=9100",
    "NASDAQ": "https://www.fastbull.com/quotation-detail/IXIC?exchange=9100",
    "Dow Jones": "https://www.fastbull.com/quotation-detail/DJI?exchange=9100",
    "FTSE 100": "https://www.fastbull.com/quotation-detail/FTSE100?exchange=9100",
    "Brent Crude": "https://www.fastbull.com/quotation-detail/BRENT?exchange=8600",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

def scrape_fastbull(url):
    """Extract technical indicator data from a FastBull page."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # ----- PLACEHOLDER SELECTORS (you must update after inspecting the page) -----
        # Find the container that holds the "Technical Indicators" or "Oscillators" table.
        # Example: <div class="technical-indicators"> or <table class="signal-table">
        # We'll look for text-based clues first.
        # For now, a generic extraction attempt – you will replace these with real selectors.
        indicators_section = soup.find("div", class_="indicatorContainer")
        if not indicators_section:
            # fallback: try to find a table with 'oscillator' in its class/id
            indicators_section = soup.find("table", {"class": "oscillatorTable"})
        
        # If still None, return raw text snippet
        if not indicators_section:
            # try to get the whole body text and return first 500 chars
            body_text = soup.get_text()
            return f"⚠️ Could not locate indicator table. Page snippet:\n{body_text[:500]}"
        
        # Extract rows – each row might contain indicator name, signal, value.
        rows = indicators_section.find_all("tr")
        lines = []
        for row in rows:
            cols = row.find_all("td")
            if len(cols) >= 3:
                name = cols[0].get_text(strip=True)
                value = cols[1].get_text(strip=True)
                signal = cols[2].get_text(strip=True)
                lines.append(f"  • {name}: {value} → {signal}")
            elif len(cols) == 2:
                name = cols[0].get_text(strip=True)
                signal = cols[1].get_text(strip=True)
                lines.append(f"  • {name}: {signal}")
        
        return "\n".join(lines) if lines else "ℹ️ No indicator rows found."
    
    except Exception as e:
        return f"❌ Scraping error: {e}"

def build_individual_messages():
    """Build individual messages for each asset (for Discord)."""
    today = datetime.date.today().strftime("%Y-%m-%d")
    messages = []
    
    header = f"📊 **FastBull Daily Technicals**\n🗓 {today}\n\n"
    
    for asset_name, url in assets.items():
        data = scrape_fastbull(url)
        msg = header + f"**{asset_name}**\n{data}"
        messages.append(msg)
    
    return messages

def build_full_message():
    """Build the full message (for Telegram)."""
    today = datetime.date.today().strftime("%Y-%m-%d")
    msg = f"📊 **FastBull Daily Technicals**\n🗓 {today}\n\n"
    for asset_name, url in assets.items():
        data = scrape_fastbull(url)
        msg += f"**{asset_name}**\n{data}\n\n"
    return msg

async def send_to_telegram_async(text):
    """Send message to Telegram asynchronously."""
    try:
        print("[DEBUG] Initializing Telegram bot async...")
        async with Bot(token=TELEGRAM_TOKEN) as bot:
            print(f"[DEBUG] Sending to Telegram chat ID: {TELEGRAM_CHAT_ID}")
            await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text, parse_mode="Markdown")
            print("✅ Telegram sent successfully.")
    except Exception as e:
        print(f"❌ Telegram failed: {type(e).__name__}: {e}", file=sys.stderr)
        raise

def send_to_telegram(text):
    """Wrapper to send Telegram message."""
    try:
        asyncio.run(send_to_telegram_async(text))
    except Exception as e:
        print(f"Telegram error: {e}")

def send_to_discord_split(messages):
    """Send messages to Discord in chunks to avoid 2000 char limit."""
    try:
        print("[DEBUG] Initializing Discord webhook...")
        webhook = DiscordWebhook(url=DISCORD_WEBHOOK)
        
        total_sent = 0
        for i, msg in enumerate(messages, 1):
            print(f"[DEBUG] Sending Discord message {i}/{len(messages)} ({len(msg)} chars)...")
            webhook.content = msg
            result = webhook.execute()
            
            if result.status_code == 204 or result.status_code == 200:
                print(f"✅ Discord message {i} sent successfully.")
                total_sent += 1
            else:
                print(f"❌ Discord message {i} failed with status {result.status_code}")
        
        print(f"✅ Discord: {total_sent}/{len(messages)} messages sent successfully.")
    except Exception as e:
        print(f"❌ Discord failed: {type(e).__name__}: {e}", file=sys.stderr)
        raise

if __name__ == "__main__":
    print("=" * 50)
    print("FastBull Scraper Started")
    print("=" * 50)
    
    # Build messages
    individual_messages = build_individual_messages()
    full_message = build_full_message()
    
    print(f"\n[DEBUG] Built {len(individual_messages)} individual asset messages")
    print(f"[DEBUG] Full message size: {len(full_message)} characters")
    
    print("\n--- Sending to Telegram ---")
    send_to_telegram(full_message)
    
    print("\n--- Sending to Discord ---")
    send_to_discord_split(individual_messages)
    
    print("\n" + "=" * 50)
    print("FastBull Scraper Completed")
    print("=" * 50)
