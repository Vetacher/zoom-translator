#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
import jwt
import time

# Генерируем SDK JWT токен
def generate_sdk_token(meeting_number, role=0):
    payload = {
        'appKey': settings.zoom_sdk_key,
        'sdkKey': settings.zoom_sdk_key,
        'mn': meeting_number,
        'role': role,
        'iat': int(time.time()),
        'exp': int(time.time()) + 7200,
        'tokenExp': int(time.time()) + 7200
    }
    
    token = jwt.encode(payload, settings.zoom_sdk_secret, algorithm='HS256')
    return token

if __name__ == "__main__":
    print("Testing Zoom Meeting SDK credentials...")
    print(f"SDK Key: {settings.zoom_sdk_key[:20]}...")
    print(f"SDK Secret: {settings.zoom_sdk_secret[:20]}...")
    
    # Тестовый номер встречи
    test_meeting = "1234567890"
    
    try:
        token = generate_sdk_token(test_meeting)
        print(f"\n✓ Successfully generated SDK token!")
        print(f"Token: {token[:50]}...")
    except Exception as e:
        print(f"\n✗ Failed to generate SDK token: {e}")
