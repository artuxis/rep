import os
import sys
import argparse
import time
import re
import requests
import urllib.parse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from bs4 import BeautifulSoup

# --- 1. КОНСТАНТИ ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

URL = "https://www.poe.pl.ua/disconnection/power-outages/"
TARGET_QUEUE = 1
NON_TIME_COLUMNS = 2
STATE_FILE = "last_schedule.txt"

STATUS_MAPPING = {
    'light_3': '- Можливо не буде',
    'light_2': '- Точно не буде',
}

# --- 2. ФУНКЦІЇ РОБОТИ ЗІ СТАНОМ ---

def load_last_schedule():
    """Завантажує останній збережений графік з файлу."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return f.read().strip()
    return ""

def save_new_schedule(schedule_data):
    """Зберігає новий графік у файл."""
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        f.write(schedule_data)

# --- 3. ХЕЛПЕРИ ПАРСИНГУ ---

def time_to_time_string(index: int) -> dict:
    """Обчислює час початку та кінця 30-хвилинного інтервалу за його індексом."""
    minutes_start = index * 30
    minutes_end = (index + 1) * 30

    def format_minutes(total_minutes):
        h = total_minutes // 60
        m = total_minutes % 60
        return f"{h:02d}:{m:02d}"

    return {
        'start': format_minutes(minutes_start),
        'end': format_minutes(minutes_end)
    }

# --- 4. ФУНКЦІЯ ПАРСИНГУ (ПОВЕРТАЄ СИРІ ДАНІ) ---

def parse_poe_schedule_with_date() -> dict:
    """
    Парсить графік відключень, повертаючи дату та сирий текстовий графік.
    """

    chrome_options = Options()

    
    # === ОСНОВНІ ПАРАМЕТРИ ===
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--window-size=1920,1080")
    
    # === КРИТИЧНІ ПАРАМЕТРИ СЕРЕДОВИЩА CI/CD (GitHub) ===
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-software-rasterizer")
    
    # === ВИРІШЕННЯ ПРОБЛЕМИ ТАЙМАУТУ РЕНДЕРА (НОВЕ) ===
    chrome_options.add_argument("--single-process")               # КРИТИЧНО: Зменшує споживання RAM
    chrome_options.add_argument("--disable-setuid-sandbox")      # Додатковий обхід SandBox
    chrome_options.add_argument("--disable-site-per-process")    # Зменшує використання пам'яті
    chrome_options.add_argument("--disable-renderer-backgrounding") # Запобігає "засинанню" рендера
    chrome_options.add_argument("--blink-settings=imagesEnabled=false") # ЗНАЧНЕ ЗМЕНШЕННЯ НАВАНТАЖЕННЯ
    
    # === ДОДАТКОВІ ПАРАМЕТРИ ОПТИМІЗАЦІЇ ===
    chrome_options.add_argument("--disable-blink-features=AutomationControlled") # Анти-виявлення
    chrome_options.add_argument("--disable-logging")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--disable-background-timer-throttling")
    chrome_options.add_argument("--disable-backgrounding-occluded-windows")
    # =======================================================
    

    driver = None
    extracted_date = "Дата не знайдена"
    schedule_text = "Графік не сформовано"

    try:

        service = Service('chromedriver') 
        
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(60) 
        driver.get(URL)
        
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CLASS_NAME, "turnoff-scheduleui-table"))
        )
        time.sleep(1)

        html_content = driver.page_source
        
    except Exception as e:

        return {'extracted_date': extracted_date, 'schedule_text': f"❌ Критична помилка завантаження сторінки: {e}"}
    finally:
        if driver:
            driver.quit()
        
    # --- Парсинг Beautiful Soup ---
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 1. Парсинг дати
    date_info = soup.find('div', id='gpvinfo')
    if date_info:
        match = re.search(r'\d{1,2}\s+[А-Яа-я]+\s+\d{4}\s+року', date_info.text)
        if match:
            extracted_date = match.group(0)

    # 2. Парсинг таблиці
    schedule_table = soup.find('table', class_='turnoff-scheduleui-table') 
    if not schedule_table:
        return {'extracted_date': extracted_date, 'schedule_text': "❌ Таблиця з графіком не знайдена."}

    # 3. Пошук рядка черги
    target_row = None
    rows = schedule_table.find_all('tr')
    for row in rows:
        queue_td = row.find('td', class_='turnoff-scheduleui-table-queue', string=f"{TARGET_QUEUE} черга")
        if queue_td and row.find('td', class_=lambda c: c and 'light_' in c):
            target_row = row
            break
            
    if not target_row:
        return {'extracted_date': extracted_date, 'schedule_text': f"❌ Графік для {TARGET_QUEUE} черги не знайдено."}

    # 4. Форматування виводу
    time_data = []
    time_tds = target_row.find_all('td')[NON_TIME_COLUMNS:]
    
    for i, td in enumerate(time_tds):
        status_classes = td.get('class', ['light_1'])
        status_class = next((c for c in status_classes if c.startswith('light_')), 'light_1')
        time = time_to_time_string(i)
        time_data.append({"start": time['start'], "end": time['end'], "status": status_class})

    grouped_schedule = []
    current_group = None
    for item in time_data:
        status = item['status']
        if status not in ['light_2', 'light_3']: status = 'light_1'
        
        is_new_group = current_group is None or status != current_group['status']
        
        if is_new_group:
            if current_group: grouped_schedule.append(current_group)
            current_group = {"start": item['start'], "end": item['end'], "status": status}
        else:
            current_group['end'] = item['end']
            
    if current_group: grouped_schedule.append(current_group)

    output_parts = []
    for group in grouped_schedule:
        if group['status'] in STATUS_MAPPING:
            status_to_display = STATUS_MAPPING[group['status']]
            output_parts.append(f"{group['start']}-{group['end']} {status_to_display}")
            
    schedule_lines = "\n".join(output_parts)
    schedule_text = f"Вимкнення електрики:\n{schedule_lines}"
    
    return {'extracted_date': extracted_date, 'schedule_text': schedule_text}

# --- 5. ФУНКЦІЯ ВІДПРАВКИ В TELEGRAM ---

def send_telegram_message(message: str):
    """Надсилає повідомлення у вказаний Telegram-чат."""
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ Помилка: BOT_TOKEN або CHAT_ID не налаштовано.")
        return

    encoded_message = urllib.parse.quote_plus(message)
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage?chat_id={CHAT_ID}&text={encoded_message}"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        if response.json().get('ok'):
            print("✅ Повідомлення успішно відправлено у Telegram.")
        else:
            print(f"❌ Помилка відправки Telegram: {response.json().get('description')}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Помилка підключення до Telegram API: {e}")

# --- 6. ГОЛОВНА ТОЧКА ВИКОНАННЯ ---

def main():
    parser = argparse.ArgumentParser(description="Power Outage Schedule Monitor")
    parser.add_argument('--mode', required=True, choices=['initial', 'check'], help="initial: send first, save. check: compare, send if different.")
    args = parser.parse_args()
    
    # 1. ПАРСИНГ НОВИХ ДАНИХ
    result = parse_poe_schedule_with_date()
    
    if "❌" in result['schedule_text']:
        print(result['schedule_text'])
        send_telegram_message(f"🚨 Помилка парсингу: {result['schedule_text']}")
        sys.exit(1)

    new_schedule_string = result['schedule_text']
    extracted_date = result['extracted_date']
    
    if args.mode == 'initial':
        # Режим 1: Первинне щоденне надсилання (о 8:00)
        final_message = f"{extracted_date}\n\n{new_schedule_string}"
        send_telegram_message(final_message)
        save_new_schedule(new_schedule_string)
        print("Initial daily schedule sent and saved.")
        
    elif args.mode == 'check':
        # Режим 2: Моніторинг змін (кожні 15 хвилин)
        last_schedule_string = load_last_schedule()
             
        if new_schedule_string != last_schedule_string:
            # Зміна виявлена! Надсилаємо оновлення.
            update_marker = "(оновлення)"
            final_message = f"{extracted_date} {update_marker}\n\n{new_schedule_string}"
            
            send_telegram_message(final_message)
            save_new_schedule(new_schedule_string)
            print("Change detected. Update sent and new schedule saved.")
        else:
            print("No change detected. No message sent.")

if __name__ == "__main__":

    main()


















