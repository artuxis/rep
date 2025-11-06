import logging
from playwright.sync_api import sync_playwright
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

URL = "https://www.poe.pl.ua/disconnection/power-outages/"

logger.info("=" * 70)
logger.info("🔍 Testing poe.pl.ua access with Playwright")
logger.info("=" * 70)

with sync_playwright() as p:
    try:
        logger.info("🚀 Launching Chromium...")
        browser = p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled']
        )
        
        page = browser.new_page()
        logger.info(f"🌍 Navigating to {URL}")
        
        response = page.goto(URL, wait_until='domcontentloaded', timeout=30000)
        status = response.status
        
        logger.info(f"✅ Status Code: {status}")
        
        if status == 200:
            logger.info("✅ SUCCESS! Website is accessible")
            logger.info("You can use Playwright for scraping!")
            sys.exit(0)
        elif status == 403:
            logger.error("❌ ERROR 403 - IP is blocked")
            logger.error("You need to use a proxy or VPN")
            sys.exit(1)
        else:
            logger.warning(f"⚠️  Unexpected status: {status}")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        sys.exit(1)
    finally:
        browser.close()
