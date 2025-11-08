#!/usr/bin/env python3
import requests
import os
import json
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('RECALL_AI_API_KEY')
BASE_URL = 'https://us-west-2.recall.ai/api/v1'

headers = {
    'Authorization': f'Token {API_KEY}',
    'Content-Type': 'application/json'
}

bot_id = "b4040f9d-89c4-4953-8f56-04192542815d"

response = requests.get(f'{BASE_URL}/bot/{bot_id}', headers=headers)

if response.status_code == 200:
    bot = response.json()
    print(json.dumps(bot, indent=2))
else:
    print(f"Error: {response.status_code}")
    print(response.text)
