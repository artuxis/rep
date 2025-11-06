import os
import sys
import argparse
import time
import re
import requests
import urllib.parse
from bs4 import BeautifulSoup

# --- 1. КОНСТАНТИ ---
# Параметри для проксі та Telegram беруться з Secrets GitHub Actions
PROXY_URL = os.environ.get('PROXY_URL')
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

URL = "https://www.poe.pl.ua/disconnection/power-outages/"
TARGET_QUEUE = 1
NON_TIME_COLUMNS = 2
STATE_FILE = "last_schedule.txt" # Файл тепер зберігає повне повідомлення (Дата + Графік)

# Статуси з HTML-форматуванням для Telegram (HTML-теги)
STATUS_MAPPING = {
    'light_3': '- Можливо не буде',
    'light_2': '- <b>Точно не буде</b>', # Жирний шрифт <b> для "Точно не буде"
}

# --- 2. ФУНКЦІЇ РОБОТИ ЗІ СТАНОМ ---

def load_last_schedule() -> str:
    """Завантажує повний останній збережений графік (Дата + Вміст) з файлу."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return f.read().strip()
    return ""

def save_new_schedule(full_schedule_data: str):
    """Зберігає повний новий графік (Дата + Вміст) у файл."""
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        f.write(full_schedule_data)

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
    Парсить графік з датою і форматує його, використовуючи HTML-теги для Telegram.
    """
    extracted_date = "Дата не знайдена"
    schedule_text_content = "Графік не сформовано"
    
    # --- HTTP-ЗАПИТ ---
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        proxies = None
        if PROXY_URL:
            proxies = { 'http': PROXY_URL, 'https': PROXY_URL }
            
        response = requests.get(URL, headers=headers, proxies=proxies, timeout=30)
        response.raise_for_status()
        html_content = response.text
        
    except requests.exceptions.RequestException as e:
        return {'extracted_date': extracted_date, 'schedule_text_content': f"❌ Критична помилка HTTP-запиту: {e}"}
        
    # --- Парсинг Beautiful Soup ---
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 1. Парсинг дати
    date_info = soup.find('div', id='gpvinfo')
    if date_info:
        match = re.search(r'\d{1,2}\s+[А-Яа-я]+\s+\d{4}\s+року', date_info.text)
        if match:
            extracted_date = match.group(0)

    # 2. Пошук рядка черги
    schedule_table = soup.find('table', class_='turnoff-scheduleui-table')
    if not schedule_table:
        return {'extracted_date': extracted_date, 'schedule_text_content': "❌ Таблиця з графіком не знайдена."}

    target_row = None
    rows = schedule_table.find_all('tr')
    for row in rows:
        queue_td = row.find('td', class_='turnoff-scheduleui-table-queue', string=f"{TARGET_QUEUE} черга")
        if queue_td and row.find('td', class_=lambda c: c and 'light_' in c):
            target_row = row
            break
            
    if not target_row:
        return {'extracted_date': extracted_date, 'schedule_text_content': f"❌ Графік для {TARGET_QUEUE} черги не знайдено."}

    # 3. Форматування виводу (згрупування)
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

    # 4. Форматування рядків з HTML
    output_parts = []
    for group in grouped_schedule:
        if group['status'] in STATUS_MAPPING:
            # STATUS_MAPPING вже містить HTML-теги <b>
            status_to_display = STATUS_MAPPING[group['status']]
            
            # Щоб час завжди був частиною жирного тексту, якщо статус 'light_2':
            if group['status'] == 'light_2':
                # Якщо "Точно не буде", додаємо <b> перед часом і закриваємо після статусу
                # [4:-4] обрізає теги <b></b> навколо статусу, щоб обгорнути все разом.
                formatted_line = f"<b>{group['start']}-{group['end']} - {status_to_display[4:-4]}</b>"
            else:
                # Якщо "Можливо не буде", залишаємо без <b>
                formatted_line = f"{group['start']}-{group['end']} {status_to_display}"
                
            output_parts.append(formatted_line)
            
    schedule_lines = "\n".join(output_parts)
    
    # Заголовок у курсиві <i>
    schedule_text_content = f"<i>Вимкнення електрики:</i>\n{schedule_lines}"
    
    return {'extracted_date': extracted_date, 'schedule_text_content': schedule_text_content}

# --- 5. ФУНКЦІЯ ВІДПРАВКИ В TELEGRAM ---

def send_telegram_message(message: str):
    """
    Надсилає повідомлення у вказаний Telegram-чат з parse_mode='HTML'.
    Використовує requests.post з JSON-payload замість GET.
    """
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ Помилка: BOT_TOKEN або CHAT_ID не налаштовано.")
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    payload = {
        'chat_id': CHAT_ID,
        'text': message,
        'parse_mode': 'HTML' # ✅ Вмикаємо HTML-форматування
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        if response.json().get('ok'):
            print("✅ Повідомлення успішно відправлено у Telegram.")
        else:
            description = response.json().get('description')
            print(f"❌ Помилка відправки Telegram: {description}")
            if 'can\'t parse message' in description.lower():
                 print("   ℹ️ Перевірте HTML-синтаксис у повідомленні.")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Помилка підключення до Telegram API: {e}")

# --- 6. ГОЛОВНА ТОЧКА ВИКОНАННЯ ---

def main():
    parser = argparse.ArgumentParser(description="Power Outage Schedule Monitor")
    parser.add_argument('--mode', required=True, choices=['initial', 'check'], help="initial: send first, save. check: compare, send if different.")
    args = parser.parse_args()
    
    # 1. ПАРСИНГ НОВИХ ДАНИХ
    result = parse_poe_schedule_with_date()
    
    # Обробка критичних помилок парсингу
    if "❌" in result['schedule_text_content']:
        print(f"❌ Критична помилка парсингу. Завершую роботу. Деталі: {result['schedule_text_content']}")
        # 🛑 ВИДАЛЕНО: send_telegram_message(...) - тепер помилка не йде користувачу в ТГ
        sys.exit(1)

    new_schedule_content = result['schedule_text_content']
    extracted_date = result['extracted_date']
    
    # Повне повідомлення, яке має бути надіслано/збережено
    new_full_message = f"{extracted_date}\n\n{new_schedule_content}"
    
    if args.mode == 'initial':
        # Режим 1: Первинний запуск (зберегти і надіслати)
        send_telegram_message(new_full_message)
        save_new_schedule(new_full_message)
        print("Initial daily schedule sent and saved.")
        
    elif args.mode == 'check':
        # Режим 2: Моніторинг змін (кожні 15 хвилин)
        last_full_message = load_last_schedule()
        
        # 2. Перевірка на повну відсутність змін
        if new_full_message == last_full_message:
            print("No change detected. No message sent.")
            return

        # 3. Аналіз, що саме змінилося (дата чи лише графік)
        
        # Повна зміна (змінилася дата, або змінилася дата і графік)
        is_total_change = True
        
        if last_full_message:
            try:
                # Розділяємо старе повідомлення на дату та вміст (дата - перший рядок)
                last_date = last_full_message.split('\n', 1)[0].strip()
                
                # Якщо дати збігаються, але повний вміст різний, то це зміна лише графіка
                if extracted_date == last_date:
                    is_total_change = False
                    
            except IndexError:
                # Старий файл кешу був пошкоджений або порожній, розцінюємо як повну зміну
                pass

        if is_total_change:
            # Кейс: Змінилася дата, або це перший запуск після очищення кешу.
            final_message = new_full_message
            print("Total change (new date or first run). Update sent and new schedule saved.")
        else:
            # Кейс: Дата залишилася, але графік змінився (schedule_only_change)
            update_marker = "(оновлено)"
            final_message = f"{extracted_date} {update_marker}\n\n{new_schedule_content}"
            print("Schedule only change detected. Adding (оновлено) and saving.")

        send_telegram_message(final_message)
        save_new_schedule(new_full_message)

if __name__ == "__main__":
    main()
