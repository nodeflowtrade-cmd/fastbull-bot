import requests
from bs4 import BeautifulSoup
import os
import datetime
import sys
import asyncio
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
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

def get_selenium_driver():
    """Initialize Selenium WebDriver with headless Chrome."""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument(f"user-agent={HEADERS['User-Agent']}")
    
    driver = webdriver.Chrome(options=chrome_options)
    return driver

def scrape_overview(driver, url):
    """Extract price data from Overview tab."""
    try:
        driver.get(url)
        time.sleep(2)  # Wait for page load
        
        overview_data = {}
        
        # Get current price
        try:
            price_elem = driver.find_element(By.CSS_SELECTOR, "[class*='price'], [class*='current']")
            overview_data['price'] = price_elem.text
        except:
            overview_data['price'] = "N/A"
        
        # Get price change
        try:
            change_elem = driver.find_element(By.CSS_SELECTOR, "[class*='change'], [class*='percent']")
            overview_data['change'] = change_elem.text
        except:
            overview_data['change'] = "N/A"
        
        return overview_data
    except Exception as e:
        return {"error": f"Overview error: {str(e)[:50]}"}

def scrape_technicals(driver):
    """Extract technical analysis and pivot points from Technicals tab."""
    try:
        # Click on Technicals tab
        tech_tab = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//div[contains(text(), 'Technicals')] | //button[contains(text(), 'Technicals')]"))
        )
        tech_tab.click()
        time.sleep(2)  # Wait for content to load
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        technicals = {}
        
        # Look for Technical Analysis section
        tech_sections = soup.find_all("div", class_=lambda x: x and "technical" in x.lower())
        
        indicators = []
        for section in tech_sections:
            rows = section.find_all(["tr", "div"])
            for row in rows[:10]:  # Limit to first 10 items
                text = row.get_text(strip=True)
                if text and len(text) < 100:
                    indicators.append(text)
        
        technicals['indicators'] = indicators[:8] if indicators else ["No technical data found"]
        
        # Look for Pivot Points
        pivot_section = soup.find("div", string=lambda x: x and "Pivot" in x if x else False)
        if pivot_section:
            pivot_text = pivot_section.get_text()
            technicals['pivot_points'] = pivot_text
        else:
            technicals['pivot_points'] = "No pivot point data found"
        
        return technicals
    except Exception as e:
        return {"error": f"Technicals error: {str(e)[:50]}"}

def scrape_asset(url):
    """Scrape both overview and technical data for an asset."""
    driver = None
    try:
        driver = get_selenium_driver()
        
        overview = scrape_overview(driver, url)
        time.sleep(1)
        technicals = scrape_technicals(driver)
        
        return {
            "overview": overview,
            "technicals": technicals
        }
    except Exception as e:
        return {"error": str(e)[:50]}
    finally:
        if driver:
            driver.quit()

def format_asset_message(asset_name, data):
    """Format asset data into a clean message."""
    if "error" in data:
        return f"**{asset_name}**\n❌ {data['error']}"
    
    msg = f"**{asset_name}**\n"
    msg += "=" * 30 + "\n\n"
    
    # Overview section
    overview = data.get("overview", {})
    if "price" in overview:
        msg += f"💰 **Price:** {overview['price']}\n"
    if "change" in overview:
        msg += f"📊 **Change:** {overview['change']}\n"
    
    msg += "\n"
    
    # Technicals section
    technicals = data.get("technicals", {})
    if "indicators" in technicals:
        msg += "**Technical Indicators (15m, 1H):**\n"
        for indicator in technicals['indicators'][:6]:
            if indicator and not indicator.startswith("error"):
                msg += f"  • {indicator}\n"
    
    # Pivot Points section
    if "pivot_points" in technicals and technicals['pivot_points'] != "No pivot point data found":
        msg += f"\n**Pivot Points:**\n{technicals['pivot_points'][:200]}\n"
    
    return msg

def build_individual_messages():
    """Build individual messages for each asset (for Discord)."""
    today = datetime.date.today().strftime("%Y-%m-%d")
    messages = []
    
    for asset_name, url in assets.items():
        print(f"[DEBUG] Scraping {asset_name}...")
        data = scrape_asset(url)
        msg = f"📊 **{asset_name}**\n🗓 {today}\n\n" + format_asset_message(asset_name, data)
        messages.append(msg)
    
    return messages

def build_full_message():
    """Build the full message (for Telegram)."""
    today = datetime.date.today().strftime("%Y-%m-%d")
    msg = f"📊 **Daily Technical Analysis**\n🗓 {today}\n{'='*40}\n\n"
    
    for asset_name, url in assets.items():
        print(f"[DEBUG] Scraping {asset_name} for Telegram...")
        data = scrape_asset(url)
        msg += format_asset_message(asset_name, data) + "\n\n"
    
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
    print("Technical Analysis Scraper Started (Selenium)")
    print("=" * 50)
    
    # Build messages
    print("\n[DEBUG] Building Discord messages...")
    individual_messages = build_individual_messages()
    
    print("\n[DEBUG] Building Telegram message...")
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
