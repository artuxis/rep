import requests
import json
from datetime import datetime
import os

# --- Налаштування ---
current_date = datetime.now().strftime("%d-%m-%Y")  # 09-11-2025
url = "https://www.poe.pl.ua/customs/newgpv-info.php"

headers = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "uk,en-US;q=0.9,en;q=0.8,ru;q=0.7",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://www.poe.pl.ua",
    "Referer": "https://www.poe.pl.ua/disconnection/power-outages/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest"
}

payload = {
    "seldate": json.dumps({"date_in": current_date})
}

# --- Проксі (автоматично береться з env) ---
proxies = {}
if os.getenv("https_proxy"):
    proxies = {
        "http": os.getenv("https_proxy"),
        "https": os.getenv("https_proxy")
    }

print(f"[{datetime.now()}] Запит на графік за дату: {current_date}")
print(f"Використовується проксі: {proxies.get('https', 'немає')}")

try:
    response = requests.post(url, headers=headers, data=payload, proxies=proxies, timeout=20)
    response.raise_for_status()

    # Зберігаємо відповідь
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"result_{timestamp}.txt"

    with open(filename, "w", encoding="utf-8") as f:
        if response.headers.get("content-type", "").startswith("application/json"):
            pretty_json = json.dumps(response.json(), ensure_ascii=False, indent=2)
            f.write(pretty_json)
            print("Отримана JSON-відповідь:")
            print(pretty_json[:500] + "..." if len(pretty_json) > 500 else pretty_json)
        else:
            f.write(response.text)
            print("Отримана HTML-відповідь:")
            print(response.text[:500] + "...")
