import logging
import sys
import time
from playwright.sync_api import sync_playwright, TimeoutError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

URL = "https://www.poe.pl.ua/disconnection/power-outages/"

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=['--disable-blink-features=AutomationControlled']
    )
    page = browser.new_page()
    response = page.goto(
    "https://www.poe.pl.ua/disconnection/power-outages/",
    wait_until='commit',
    timeout=15000
)
    # Try different strategies
    for strategy, timeout in [
        ('commit', 15000),
        ('domcontentloaded', 30000),
        ('load', 60000),
    ]:
        try:
            logger.info(f"Trying: {strategy} ({timeout}ms)")
            response = page.goto(URL, wait_until=strategy, timeout=timeout)
            
            if response and response.status == 200:
                logger.info(f"SUCCESS - Status {response.status}")
                sys.exit(0)
        except TimeoutError:
            logger.warning(f"Timeout")
    
    logger.error("FAILED - All strategies timed out")
    sys.exit(1)
EOF
          python test.py
