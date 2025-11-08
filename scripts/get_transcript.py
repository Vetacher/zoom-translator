#!/usr/bin/env python3
import requests
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('RECALL_AI_API_KEY')
BASE_URL = 'https://us-west-2.recall.ai/api/v1'

headers = {
    'Authorization': f'Token {API_KEY}',
    'Content-Type': 'application/json'
}

# ID последнего бота
bot_id = "b4040f9d-89c4-4953-8f56-04192542815d"

print("=== Getting Transcript ===\n")

# Получаем информацию о боте
response = requests.get(f'{BASE_URL}/bot/{bot_id}', headers=headers)

if response.status_code == 200:
    bot = response.json()
    
    print(f"Bot ID: {bot['id']}")
    print(f"Status: {bot.get('status_changes', [{}])[-1].get('code', 'unknown')}")
    print(f"Meeting URL: {bot['meeting_url']}\n")
    
    # Получаем транскрипцию
    if 'transcript' in bot and bot['transcript']:
        print("=== TRANSCRIPT ===\n")
        
        for segment in bot['transcript']:
            speaker = segment.get('speaker', 'Unknown')
            text = segment.get('words', '')
            timestamp = segment.get('start', 0)
            
            print(f"[{timestamp:.1f}s] {speaker}: {text}")
        
        print("\n=== Full Text ===")
        full_text = " ".join([s.get('words', '') for s in bot['transcript']])
        print(full_text)
    else:
        print("⚠️ No transcript available yet. Wait a bit and try again.")
        print("Transcript processing can take 1-2 minutes after recording ends.")
else:
    print(f"Error: {response.status_code}")
    print(response.text)
