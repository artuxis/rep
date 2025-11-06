import logging
import sys
import time
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

URL = "https://www.poe.pl.ua/disconnection/power-outages/"

UKRAINIAN_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

UKRAINIAN_HEADERS = {
    'Accept-Language': 'uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Cache-Control': 'no-cache',
    'Pragma': 'no-cache',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Upgrade-Insecure-Requests': '1',
}

def get_proxy_config():
    import os
    proxy_user = os.environ.get('PROXY_AUTH_USER')
    proxy_pass = os.environ.get('PROXY_AUTH_PASS')
    
    if proxy_user and proxy_pass:
        return {
            'server': 'http://gate.smartproxy.com:7000',
            'username': proxy_user,
            'password': proxy_pass,
        }
    return None

def test_access():
    logger.info("=" * 70)
    logger.info("Testing poe.pl.ua access with Ukrainian masking")
    logger.info("=" * 70)
    
    try:
        import requests
        ip_response = requests.get('https://api.ipify.org?format=json', timeout=5)
        ip = ip_response.json().get('ip')
        logger.info(f"Public IP: {ip}")
    except:
        logger.warning("Could not get public IP")
    
    with sync_playwright() as p:
        try:
            proxy_config = get_proxy_config()
            
            browser = p.chromium.launch(
                headless=True,
                proxy=proxy_config,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                ]
            )
            
            import random
            user_agent = random.choice(UKRAINIAN_USER_AGENTS)
            
            page = browser.new_page(
                user_agent=user_agent,
                extra_http_headers=UKRAINIAN_HEADERS,
                locale='uk-UA',
                timezone_id='Europe/Kyiv',
                viewport={'width': 1920, 'height': 1080}
            )
            
            strategies = [
                ('commit', 15000),
                ('domcontentloaded', 30000),
                ('load', 60000),
            ]
            
            success = False
            for strategy, timeout in strategies:
                try:
                    logger.info(f"Attempt: {strategy} ({timeout}ms)")
                    response = page.goto(URL, wait_until=strategy, timeout=timeout)
                    
                    if response and response.status == 200:
                        content_len = len(page.content())
                        logger.info(f"✅ SUCCESS - Status: {response.status}, Size: {content_len} bytes")
                        
                        try:
                            title = page.title()
                            logger.info(f"Page title: {title}")
                        except:
                            pass
                        
                        success = True
                        break
                except PlaywrightTimeoutError:
                    logger.warning(f"Timeout with {strategy}")
                except Exception as e:
                    logger.error(f"Error with {strategy}: {e}")
            
            browser.close()
            
            if success:
                logger.info("=" * 70)
                logger.info("✅ Website is accessible!")
                logger.info("=" * 70)
                return 0
            else:
                logger.error("=" * 70)
                logger.error("❌ Website is not accessible")
                logger.error("=" * 70)
                return 1
                
        except Exception as e:
            logger.error(f"Fatal error: {e}")
            return 1

if __name__ == "__main__":
    sys.exit(test_access())
