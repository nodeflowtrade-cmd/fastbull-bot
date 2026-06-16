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

def scrape_technicals(url):
    """Extract technical indicator data from the page."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Try multiple selectors to find technical indicators
        indicators = {}
        
        # Look for any table or div containing technical data
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all(["td", "th"])
                if len(cells) >= 2:
                    # Try to extract indicator name and value/signal
                    cell_text = [cell.get_text(strip=True) for cell in cells]
                    if cell_text[0] and cell_text[1]:
                        # Look for key technical indicators
                        indicator_name = cell_text[0].lower()
                        if any(x in indicator_name for x in ["rsi", "macd", "ma", "sma", "ema", "bollinger", "stoch", "atr", "adx", "signal"]):
                            indicators[cell_text[0]] = cell_text[1] if len(cell_text) > 1 else "N/A"
        
        # Look for price data
        price_data = {}
        price_elements = soup.find_all("span", class_=lambda x: x and ("price" in x.lower() or "bid" in x.lower() or "ask" in x.lower()))
        
        # Extract current price/bid/ask
        texts = soup.get_text()
        lines = texts.split('\n')
        
        # Look for common technical indicator patterns
        for i, line in enumerate(lines):
            line_clean = line.strip()
            if line_clean and len(line_clean) < 100:
                # RSI
                if "RSI" in line_clean or "rsi" in line_clean.lower():
                    if any(char.isdigit() for char in line_clean):
                        indicators["RSI"] = line_clean
                # MACD
                elif "MACD" in line_clean or "macd" in line_clean.lower():
                    if any(char.isdigit() for char in line_clean):
                        indicators["MACD"] = line_clean
                # Moving Averages
                elif "MA" in line_clean or "SMA" in line_clean or "EMA" in line_clean:
                    if any(char.isdigit() for char in line_clean):
                        indicators[line_clean.split()[0]] = line_clean
        
        if indicators:
            lines = [f"{k}: {v}" for k, v in list(indicators.items())[:6]]
            return "\n".join(lines) if lines else "No technical data available"
        else:
            return "⚠️ Could not locate technical indicators on page"
    
    except Exception as e:
        return f"❌ Error: {str(e)[:50]}"

def build_individual_messages():
    """Build individual messages for each asset (for Discord)."""
    today = datetime.date.today().strftime("%Y-%m-%d")
    messages = []
    
    for asset_name, url in assets.items():
        data = scrape_technicals(url)
        msg = f"📊 **{asset_name}**\n🗓 {today}\n\n{data}"
        messages.append(msg)
    
    return messages

def build_full_message():
    """Build the full message (for Telegram)."""
    today = datetime.date.today().strftime("%Y-%m-%d")
    msg = f"📊 **Daily Technical Analysis**\n🗓 {today}\n{'='*40}\n\n"
    
    for asset_name, url in assets.items():
        data = scrape_technicals(url)
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

if __name__ == "__main__":
    print("=" * 50)
    print("Technical Analysis Scraper Started")
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
    print("Technical Analysis Scraper Completed")
    print("=" * 50)
