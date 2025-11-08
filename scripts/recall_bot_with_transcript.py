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

meeting_url = "https://us06web.zoom.us/j/83743125107?pwd=TMZwyAMO6cJNZyr5bbyscXVCDWbtEM.1"

bot_data = {
    "meeting_url": meeting_url,
    "bot_name": "AI Translator Bot",
    "recording_config": {
        "transcript": {
            "provider": {
                "type": "default"
            }
        }
    }
}

print("Creating bot with transcription enabled...\n")
response = requests.post(f'{BASE_URL}/bot', json=bot_data, headers=headers)

if response.status_code == 201:
    bot = response.json()
    bot_id = bot['id']
    print(f"✓ Bot created: {bot_id}\n")
    print("Waiting for bot to join...")
    
    for i in range(60):
        time.sleep(2)
        status_response = requests.get(f'{BASE_URL}/bot/{bot_id}', headers=headers)
        if status_response.status_code == 200:
            bot_status = status_response.json()
            current_status = bot_status.get('status_changes', [{}])[-1].get('code', 'unknown')
            print(f"Status: {current_status}", end='\r')
            
            if current_status == 'in_call_recording':
                print(f"\n\n✓ Bot joined and recording with transcription!")
                print(f"\nSpeak in English now!")
                print("Press Ctrl+C when done...\n")
                
                try:
                    while True:
                        time.sleep(5)
                except KeyboardInterrupt:
                    print("\n\nStopping bot...")
                    requests.delete(f'{BASE_URL}/bot/{bot_id}', headers=headers)
                    print(f"✓ Bot stopped")
                    print(f"\nBot ID: {bot_id}")
                    print("Wait 2 minutes then run: python3 scripts/get_transcript.py")
                break
else:
    print(f"Error: {response.status_code}")
    print(response.text)
