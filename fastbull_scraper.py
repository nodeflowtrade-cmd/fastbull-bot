201
202
203
204
205
206
207
208
209
210
211
212
213
214
215
216
217
218
219
220
221
222
223
224
225
226
227
228
229
230
231
232
233
234
235
236
237
238
239
240
241
242
243
244
245
246
247
248
249
250
251
252
253
254
255
256
257
258
259
260
261
262
263
264
265
266
267
268
269
270
from bs4 import BeautifulSoup
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
