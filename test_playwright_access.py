import logging
import sys
import time
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

URL = "https://www.poe.pl.ua/disconnection/power-outages/"

logger.info("=" * 70)
logger.info("Testing different wait strategies...")
logger.info("=" * 70)

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=['--disable-blink-features=AutomationControlled', '--disable-dev-shm-usage']
    )
    page = browser.new_page()
    
    # Test strategies from fastest to slowest
    strategies = [
        ('commit', 15000, 'HTML loading started'),
        ('domcontentloaded', 30000, 'HTML parsed, scripts loaded'),
        ('load', 60000, 'All resources loaded'),
    ]
    
    success = False
    for strategy, timeout, description in strategies:
        logger.info(f"\n🔄 Trying: {strategy} (timeout {timeout}ms)")
        logger.info(f"   Description: {description}")
        
        try:
            start_time = time.time()
            response = page.goto(URL, wait_until=strategy, timeout=timeout)
            elapsed = time.time() - start_time
            
            if response:
                status = response.status
                content_len = len(page.content())
                
                logger.info(f"✅ SUCCESS")
                logger.info(f"   Status: {status}")
                logger.info(f"   Time: {elapsed:.2f}s")
                logger.info(f"   Content: {content_len} bytes")
                
                if status == 200:
                    success = True
                    break
            else:
                logger.warning(f"No response")
                
        except PlaywrightTimeoutError as e:
            elapsed = time.time() - start_time
            logger.warning(f"⏱️  TIMEOUT after {elapsed:.2f}s")
        except Exception as e:
            logger.error(f"❌ ERROR: {e}")
    
    browser.close()

if success:
    logger.info("\n" + "=" * 70)
    logger.info("✅ SUCCESS! Website is accessible")
    logger.info("=" * 70)
    sys.exit(0)
else:
    logger.error("\n" + "=" * 70)
    logger.error("❌ FAILED - Website is not accessible")
    logger.error("=" * 70)
    logger.error("\nPossible causes:")
    logger.error("1. GitHub Actions IP is blocked (most likely)")
    logger.error("2. Website is very slow")
    logger.error("3. JavaScript prevents page load event")
    logger.error("\nSolutions:")
    logger.error("- Use proxy (SmartProxy, GoProxy)")
    logger.error("- Use VPN from Ukraine")
    logger.error("- Contact poe.pl.ua for API access")
    sys.exit(1)
