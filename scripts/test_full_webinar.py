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
    terms = [f"- {ru} → {data['en']}" for ru, data in list(glossary.items())[:30]]
    return "GLOSSARY:\n" + "\n".join(terms)

# Читаем полную транскрипцию
with open('/tmp/azure_result.txt', 'r', encoding='utf-8') as f:
    content = f.read()
    # Извлекаем только русский текст
    russian_text = content.split("RUSSIAN TRANSLATION:")[0].replace("ENGLISH TRANSCRIPT:", "").strip()

glossary_prompt = build_glossary_prompt()

print("=== Full Webinar Translation Test ===\n")
print(f"Source length: {len(russian_text)} characters")
print(f"Words: {len(russian_text.split())}")
print(f"\nFirst 200 chars:\n{russian_text[:200]}...\n")
print("="*70)

# Test 1: GPT-4o-mini
print("\n1. GPT-4o-mini (FAST)\n")
start = time.time()
response = client.chat.completions.create(
    model=os.getenv('AZURE_OPENAI_DEPLOYMENT_FAST'),
    messages=[
        {
            "role": "system",
            "content": f"""Translate from Russian to English naturally and accurately.

{glossary_prompt}

Rules:
- Use glossary terms exactly
- Maintain natural flow
- Preserve technical accuracy
- Keep proper names unchanged
- Remove filler words (So, Well, Like, You know, I mean, etc.)
- Make text clean and professional"""
        },
        {"role": "user", "content": russian_text}
    ],
    temperature=0.3,
    max_tokens=4000
)
mini_time = time.time() - start
mini_result = response.choices[0].message.content

print(f"Time: {mini_time:.2f}s")
print(f"Output length: {len(mini_result)} characters")
print(f"\nFirst 300 chars:\n{mini_result[:300]}...\n")

# Сохраняем
with open('/tmp/translation_4o_mini.txt', 'w', encoding='utf-8') as f:
    f.write(mini_result)

# Test 2: GPT-4o
print("="*70)
print("\n2. GPT-4o (QUALITY)\n")
start = time.time()
response = client.chat.completions.create(
    model=os.getenv('AZURE_OPENAI_DEPLOYMENT_QUALITY'),
    messages=[
        {
            "role": "system",
            "content": f"""Translate from Russian to English with high quality.

{glossary_prompt}

Rules:
- Use glossary terms exactly
- Maintain natural flow
- Preserve technical accuracy
- Keep proper names unchanged
- Remove filler words (So, Well, Like, You know, I mean, etc.)
- Make text clean and professional"""
        },
        {"role": "user", "content": russian_text}
    ],
    temperature=0.4,
    max_tokens=4000
)
quality_time = time.time() - start
quality_result = response.choices[0].message.content

print(f"Time: {quality_time:.2f}s")
print(f"Output length: {len(quality_result)} characters")
print(f"\nFirst 300 chars:\n{quality_result[:300]}...\n")

# Сохраняем
with open('/tmp/translation_4o.txt', 'w', encoding='utf-8') as f:
    f.write(quality_result)

# Summary
print("="*70)
print("\n=== SUMMARY ===\n")
print(f"Source: {len(russian_text.split())} words")
print(f"\nGPT-4o-mini:")
print(f"  Time: {mini_time:.2f}s")
print(f"  Words: {len(mini_result.split())}")
print(f"\nGPT-4o:")
print(f"  Time: {quality_time:.2f}s") 
print(f"  Words: {len(quality_result.split())}")
print(f"\nSpeed difference: {quality_time/mini_time:.2f}x")
print(f"\nTranslations saved:")
print(f"  /tmp/translation_4o_mini.txt")
print(f"  /tmp/translation_4o.txt")
print(f"\nCompare them manually to see quality difference!")
