# parser.py — Оновлена версія з ротацією UA-проксі
import os
import sys
import argparse
import time
import re
import requests
from bs4 import BeautifulSoup
import random

# --- КОНСТАНТИ ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
URL = "https://www.poe.pl.ua/disconnection/power-outages/"
TARGET_QUEUE = 1
NON_TIME_COLUMNS = 2
STATE_FILE = "last_schedule.txt"

STATUS_MAPPING = {
    'light_3': '- Можливо не буде',
    'light_2': '- <b>Точно не буде</b>',
}

# --- ФУНКЦІЇ СТАНУ ---
def load_last_schedule() -> str:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return f.read().strip()
    return ""

def save_new_schedule(data: str):
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        f.write(data)

# --- ПРОКСІ ---
def get_ua_proxies() -> list:
    sources = [
        "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=5000&country=UA&ssl=yes&anonymity=elite",
        "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=5000&country=UA&ssl=no&anonymity=anonymous"
    ]
    proxies = []
    for src in sources:
        try:
            r = requests.get(src, timeout=8)
            if r.status_code == 200:
                for line in r.text.splitlines():
                    if ':' in line:
                        proxies.append(f"http://{line.strip()}")
                if len(proxies) >= 3:
                    break
        except:
            continue
        time.sleep(1)
    return proxies[:3] if proxies else []

# --- ПАРСИНГ ---
def parse_schedule() -> dict:
    proxies = get_ua_proxies()
    if not proxies:
        return {'error': '❌ Не вдалося отримати UA-проксі'}

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept-Language': 'uk-UA,uk;q=0.9',
        'Referer': 'https://www.google.com.ua/',
    }

    for proxy in proxies:
        print(f"Пробую проксі: {proxy}")
        try:
            resp = requests.get(URL, headers=headers, proxies={'http': proxy, 'https': proxy}, timeout=20)
            if resp.status_code != 200 or len(resp.text) < 5000:
                continue

            soup = BeautifulSoup(resp.text, 'html.parser')
            date_div = soup.find('div', id='gpvinfo')
            date = "Дата не знайдена"
            if date_div:
                m = re.search(r'\d{1,2}\s+[А-Яа-я]+\s+\d{4}\s+року', date_div.text)
                if m: date = m.group(0)

            table = soup.find('table', class_='turnoff-scheduleui-table')
            if not table:
                continue

            target_row = None
            for row in table.find_all('tr'):
                if row.find('td', string=f"{TARGET_QUEUE} черга"):
                    target_row = row
                    break
            if not target_row:
                continue

            # --- Групування ---
            time_data = []
            for i, td in enumerate(target_row.find_all('td')[NON_TIME_COLUMNS:]):
                cls = next((c for c in td.get('class', []) if c.startswith('light_')), 'light_1')
                if cls not in ['light_2', 'light_3']: cls = 'light_1'
                h = i // 2
                m = (i % 2) * 30
                start = f"{h:02d}:{m:02d}"
                end = f"{h + (m + 30)//60:02d}:{(m + 30)%60:02d}"
                time_data.append({'start': start, 'end': end, 'status': cls})

            grouped = []
            curr = None
            for item in time_data:
                if not curr or curr['status'] != item['status']:
                    if curr: grouped.append(curr)
                    curr = item.copy()
                else:
                    curr['end'] = item['end']
            if curr: grouped.append(curr)

            lines = []
            for g in grouped:
                status_text = STATUS_MAPPING.get(g['status'], '')
                if g['status'] == 'light_2':
                    lines.append(f"<b>{g['start']}-{g['end']} - {status_text[4:-4]}</b>")
                else:
                    lines.append(f"{g['start']}-{g['end']} {status_text}")
            schedule = "<i>Вимкнення електрики:</i>\n" + "\n".join(lines)
            return {'date': date, 'schedule': schedule}

        except Exception as e:
            print(f"Помилка з {proxy}: {e}")
            time.sleep(2)

    return {'error': '❌ Геоблок: всі проксі не спрацювали'}

# --- TELEGRAM ---
def send_telegram(msg: str):
    if not BOT_TOKEN or not CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={'chat_id': CHAT_ID, 'text': msg, 'parse_mode': 'HTML'}, timeout=10)
    except:
        pass

# --- MAIN ---
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', required=True, choices=['initial', 'check'])
    args = parser.parse_args()

    result = parse_schedule()
    if 'error' in result:
        print(result['error'])
        sys.exit(1)

    full_msg = f"{result['date']}\n\n{result['schedule']}"
    last = load_last_schedule()

    if args.mode == 'initial':
        send_telegram(full_msg)
        save_new_schedule(full_msg)
    else:
        if full_msg == last:
            print("Без змін")
            return
        date_changed = not last or result['date'] != last.split('\n', 1)[0]
        msg = full_msg if date_changed else f"{result['date']} (оновлено)\n\n{result['schedule']}"
        send_telegram(msg)
        save_new_schedule(full_msg)

if __name__ == "__main__":
    main()
