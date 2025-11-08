#!/usr/bin/env python3
import requests
import os
import time
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('RECALL_AI_API_KEY')
BASE_URL = 'https://us-west-2.recall.ai/api/v1'

headers = {
    'Authorization': f'Token {API_KEY}',
    'Content-Type': 'application/json'
}

print("=== Recall.ai Bot Test ===\n")

# Создаём бота
meeting_url = "https://us06web.zoom.us/j/83743125107?pwd=TMZwyAMO6cJNZyr5bbyscXVCDWbtEM.1"

bot_data = {
    "meeting_url": meeting_url,
    "bot_name": "AI Translator Bot"
}

print("1. Creating bot...")
response = requests.post(f'{BASE_URL}/bot', json=bot_data, headers=headers)

if response.status_code == 201:
    bot = response.json()
    bot_id = bot['id']
    print(f"   ✓ Bot created: {bot_id}")
    status = bot.get('status_changes', [{}])[-1].get('code', 'unknown') if bot.get('status_changes') else 'created'
    print(f"   Status: {status}")
    
    print("\n2. Waiting for bot to join meeting...")
    print("   (Check your Zoom - bot should appear as 'AI Translator Bot')\n")
    
    # Мониторим статус
    for i in range(30):
        time.sleep(2)
        status_response = requests.get(f'{BASE_URL}/bot/{bot_id}', headers=headers)
        if status_response.status_code == 200:
            bot_status = status_response.json()
            current_status = bot_status.get('status_changes', [{}])[-1].get('code', 'unknown') if bot_status.get('status_changes') else 'unknown'
            print(f"   Status: {current_status}", end='\r')
            
            if current_status == 'in_call':
                print(f"\n\n   ✓ Bot joined meeting!")
                print(f"\n3. Bot is now recording and transcribing...")
                print(f"   Bot will stay in meeting. Press Ctrl+C to leave.\n")
                
                try:
                    while True:
                        time.sleep(5)
                        # Здесь можно получать транскрипцию через webhook
                except KeyboardInterrupt:
                    print("\n\nLeaving meeting...")
                    requests.delete(f'{BASE_URL}/bot/{bot_id}', headers=headers)
                    print("✓ Bot left meeting")
                break
else:
    print(f"   ✗ Error: {response.status_code}")
    print(f"   {response.text}")
