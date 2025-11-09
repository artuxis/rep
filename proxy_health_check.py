import requests
import os
import sys
from datetime import datetime

# --- Налаштування ---
# Цей URL має бути тим самим, що використовується в основному парсері
TARGET_URL = "https://www.poe.pl.ua/customs/newgpv-info.php"
TIMEOUT = 10 # Зменшуємо таймаут для швидшої перевірки

print(f"[{datetime.now()}] Запуск перевірки проксі для {TARGET_URL}")

# --- Конфігурація проксі ---
proxies = {}
# Використовуємо HTTPS_PROXY та HTTP_PROXY (великі літери)
https_proxy_val = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")
http_proxy_val = os.getenv("HTTP_PROXY") or os.getenv("http_proxy")

if https_proxy_val:
    proxies["http"] = https_proxy_val
    proxies["https"] = https_proxy_val
elif http_proxy_val:
    proxies["http"] = http_proxy_val

proxy_info = proxies.get('https', 'немає')
print(f"Використовується проксі: {proxy_info}")

if not proxy_info or proxy_info == 'немає':
    print("❌ ПОМИЛКА: Не знайдено змінних HTTP_PROXY або HTTPS_PROXY.")
    sys.exit(1)

# --- Виконання перевірки ---
try:
    # Виконуємо POST-запит (як основний парсер), але з мінімальним payload
    # Додамо стандартні заголовки, щоб імітувати реальний запит
    headers = {
        "User-Agent": "Mozilla/5.0 (GitHubActions-ProxyCheck)",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
    }
    
    # Використовуємо мінімальний payload, щоб запит був коректним
    minimal_payload = {"seldate": '{"date_in": "01-01-2025"}'} 
    
    response = requests.post(
        TARGET_URL, 
        headers=headers, 
        data=minimal_payload, 
        proxies=proxies, 
        timeout=TIMEOUT
    )
    
    # Перевірка статусу відповіді (200 OK, 3xx, 4xx/5xx)
    response.raise_for_status() 

    # Якщо ми дійшли сюди, проксі працює і сервер повернув успішний код
    print(f"✅ УСПІХ! Проксі працює. Статус відповіді: {response.status_code}.")
    sys.exit(0) # Успішне завершення

except requests.exceptions.HTTPError as errh:
    print(f"❌ ПРОВАЛ! Помилка HTTP (проксі працює, але API повернув помилку): {errh}")
    # Це може означати, що проксі працює, але API не прийняв запит.
    sys.exit(1)
except requests.exceptions.ConnectionError as errc:
    print(f"❌ ПРОВАЛ! Помилка підключення (Проксі НЕ працює або відхилив з'єднання): {errc}")
    sys.exit(1)
except requests.exceptions.Timeout as errt:
    print(f"❌ ПРОВАЛ! Таймаут запиту (Проксі занадто повільний або не відповідає): {errt}")
    sys.exit(1)
except requests.exceptions.RequestException as err:
    print(f"❌ ПРОВАЛ! Загальна помилка запиту: {err}")
    sys.exit(1)
except Exception as e:
    print(f"❌ ПРОВАЛ! Невідома помилка: {e}")
    sys.exit(1)
