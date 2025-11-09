import requests
import json
from datetime import datetime
import os
import sys # Додано для коректного виходу в разі помилки

# --- Налаштування ---
current_date = datetime.now().strftime("%d-%m-%Y")  # 09-11-2025 (приклад)
url = "https://www.poe.pl.ua/customs/newgpv-info.php"

headers = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "uk,en-US;q=0.9,en;q=0.8,ru;q=0.7",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://www.poe.pl.ua",
    "Referer": "https://www.poe.pl.ua/disconnection/power-outages/",
    # Оновлення User-Agent: краще використовувати більш актуальний, або просто "Power-Outage-Checker"
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest"
}

payload = {
    "seldate": json.dumps({"date_in": current_date})
}

# --- Проксі (автоматично береться з env, використовуємо великі літери для кращої сумісності) ---
proxies = {}
# Використовуємо HTTPS_PROXY та HTTP_PROXY
https_proxy_val = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")
http_proxy_val = os.getenv("HTTP_PROXY") or os.getenv("http_proxy")

if https_proxy_val:
    proxies["http"] = https_proxy_val
    proxies["https"] = https_proxy_val
elif http_proxy_val:
    proxies["http"] = http_proxy_val


print(f"[{datetime.now()}] Запит на графік за дату: {current_date}")
print(f"Використовується проксі: {proxies.get('https', 'немає')}")

try:
    response = requests.post(url, headers=headers, data=payload, proxies=proxies, timeout=20)
    response.raise_for_status() # Викличе HTTPError для кодів 4xx/5xx

    # --- Обробка відповіді та збереження ---
    
    # 1. Зберігаємо повну відповідь як артефакт (як ви і зробили)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"result_{timestamp}.txt"

    response_content = ""
    is_json = response.headers.get("content-type", "").startswith("application/json")

    with open(filename, "w", encoding="utf-8") as f:
        if is_json:
            try:
                data = response.json()
                pretty_json = json.dumps(data, ensure_ascii=False, indent=2)
                f.write(pretty_json)
                response_content = pretty_json
                print("Отримана JSON-відповідь. Перші 500 символів:")
                print(response_content[:500] + "..." if len(response_content) > 500 else response_content)
                
                # --- Ваш аналіз даних тут ---
                # Наприклад, перевірка чи є в графіку вимкнення для вашої групи.
                # Якщо потрібно сповіщення:
                # if "Ваша_Група_Вимкнена" in response_content:
                #     message_text = "Увага! Встановлено графік відключень на сьогодні."
                #     with open("message.txt", "w", encoding="utf-8") as msg_file:
                #         msg_file.write(message_text + "\n\n" + response_content[:1000])

            except json.JSONDecodeError:
                f.write(response.text)
                response_content = response.text
                print("Отримано текст, який не є коректним JSON:")
                print(response_content[:500] + "...")
        else:
            f.write(response.text)
            response_content = response.text
            print("Отримана не-JSON відповідь (HTML/Text). Перші 500 символів:")
            print(response_content[:500] + "...")

    print("--- Завершення роботи ---")

except requests.exceptions.HTTPError as errh:
    print(f"Помилка HTTP: {errh}")
    # Викидаємо помилку, щоб GitHub Actions позначив крок як провальний
    sys.exit(1)
except requests.exceptions.ConnectionError as errc:
    print(f"Помилка підключення (можливо, проксі): {errc}")
    sys.exit(1)
except requests.exceptions.Timeout as errt:
    print(f"Таймаут запиту: {errt}")
    sys.exit(1)
except requests.exceptions.RequestException as err:
    print(f"Загальна помилка запиту: {err}")
    sys.exit(1)
except Exception as e:
    print(f"Невідома помилка: {e}")
    sys.exit(1)
