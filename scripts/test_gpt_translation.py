#!/usr/bin/env python3
from openai import AzureOpenAI
import os
import time
import json
from dotenv import load_dotenv

load_dotenv()

client = AzureOpenAI(
    api_key=os.getenv('AZURE_OPENAI_KEY'),
    api_version="2024-08-01-preview",
    azure_endpoint=os.getenv('AZURE_OPENAI_ENDPOINT')
)

# Загружаем glossary
with open('config/translation_glossary.json', 'r', encoding='utf-8') as f:
    glossary = json.load(f)

def build_glossary_prompt():
    terms = [f"- {ru} → {data['en']}" for ru, data in glossary.items()]
    return "GLOSSARY (use exact translations):\n" + "\n".join(terms[:20])

# Тестовый текст (из вашей транскрипции)
test_text = """
Сейчас мы зайдем в AWS консоль и создадим EC2 инстанс. 
Landao Ventures инвестировала в наш стартап на стадии Seed раунда.
Алерон покажет как использовать n8n и ChatGPT для создания Telegram ботов и mini apps.
"""

glossary_prompt = build_glossary_prompt()

print("=== GPT Translation Comparison ===\n")
print(f"Source text:\n{test_text}\n")
print("="*70)

# Test 1: GPT-4o-mini (fast)
print("\n1. GPT-4o-mini (FAST)")
start = time.time()
response = client.chat.completions.create(
    model=os.getenv('AZURE_OPENAI_DEPLOYMENT_FAST'),
    messages=[
        {
            "role": "system",
            "content": f"""Translate from Russian to English naturally and accurately.

{glossary_prompt}

Rules:
- Use glossary terms exactly as specified
- Keep technical terms consistent
- Maintain natural English flow
- Preserve proper names"""
        },
        {"role": "user", "content": test_text}
    ],
    temperature=0.3,
    max_tokens=500
)
fast_time = time.time() - start
fast_result = response.choices[0].message.content

print(f"Time: {fast_time:.2f}s")
print(f"Result:\n{fast_result}\n")

# Test 2: GPT-4o (quality)
print("="*70)
print("\n2. GPT-4o (QUALITY)")
start = time.time()
response = client.chat.completions.create(
    model=os.getenv('AZURE_OPENAI_DEPLOYMENT_QUALITY'),
    messages=[
        {
            "role": "system",
            "content": f"""Translate from Russian to English with high quality and natural flow.

{glossary_prompt}

Rules:
- Use glossary terms exactly as specified
- Maintain technical accuracy
- Create natural, professional English
- Preserve context and meaning
- Keep proper names unchanged"""
        },
        {"role": "user", "content": test_text}
    ],
    temperature=0.4,
    max_tokens=800
)
quality_time = time.time() - start
quality_result = response.choices[0].message.content

print(f"Time: {quality_time:.2f}s")
print(f"Result:\n{quality_result}\n")

# Summary
print("="*70)
print("\n=== SUMMARY ===\n")
print(f"GPT-4o-mini: {fast_time:.2f}s")
print(f"GPT-4o: {quality_time:.2f}s")
print(f"Speed difference: {quality_time/fast_time:.1f}x slower")
