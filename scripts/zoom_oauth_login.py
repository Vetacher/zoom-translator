#!/usr/bin/env python3
"""
Скрипт для получения OAuth токенов Zoom для events@landao.vc
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, request, redirect
import requests
import webbrowser
import threading
from app.config import settings

app = Flask(__name__)
oauth_tokens = {}

@app.route('/oauth/callback')
def zoom_oauth_callback():
    """Callback для OAuth авторизации Zoom"""
    code = request.args.get('code')
    
    if not code:
        return "Error: No authorization code received", 400
    
    # Обмениваем код на токены
    token_url = "https://zoom.us/oauth/token"
    
    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': settings.oauth_redirect_url
    }
    
    auth = (settings.zoom_client_id, settings.zoom_client_secret)
    
    try:
        response = requests.post(token_url, data=data, auth=auth)
        response.raise_for_status()
        
        tokens = response.json()
        oauth_tokens['access_token'] = tokens['access_token']
        oauth_tokens['refresh_token'] = tokens['refresh_token']
        
        # Сохраняем токены в файл
        with open('/home/lisa/zoom-translator-bot/.zoom_tokens', 'w') as f:
            f.write(f"ACCESS_TOKEN={tokens['access_token']}\n")
            f.write(f"REFRESH_TOKEN={tokens['refresh_token']}\n")
        
        print("✓ OAuth tokens saved to .zoom_tokens")
        
        return """
        <html>
            <head><title>Success</title></head>
            <body>
                <h1>✓ Authorization Successful!</h1>
                <p>Zoom account has been authorized. You can close this window.</p>
                <p>Tokens saved to .zoom_tokens file</p>
            </body>
        </html>
        """
    
    except Exception as e:
        return f"Error getting tokens: {e}", 500

def get_authorization_url():
    """Генерирует URL для авторизации"""
    auth_url = (
        f"https://zoom.us/oauth/authorize?"
        f"response_type=code&"
        f"client_id={settings.zoom_client_id}&"
        f"redirect_uri={settings.oauth_redirect_url}"
    )
    return auth_url

if __name__ == "__main__":
    print("=" * 60)
    print("Zoom OAuth Authorization")
    print("=" * 60)
    print()
    print("1. Starting local server on https://zoom-bot-vm.westeurope.cloudapp.azure.com")
    print("2. Open this URL in browser to authorize:")
    print()
    
    auth_url = get_authorization_url()
    print(auth_url)
    print()
    print("3. After authorization, tokens will be saved to .zoom_tokens")
    print()
    print("Press Ctrl+C to stop the server")
    print("=" * 60)
    
    # Запускаем Flask сервер
    app.run(host='0.0.0.0', port=5000, debug=False)#!/usr/bin/env python3
"""
Скрипт для получения OAuth токенов Zoom для events@landao.vc
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, request, redirect
import requests
import webbrowser
import threading
from app.config import settings

app = Flask(__name__)
oauth_tokens = {}

@app.route('/oauth/zoom/callback')
def zoom_oauth_callback():
    """Callback для OAuth авторизации Zoom"""
    code = request.args.get('code')
    
    if not code:
        return "Error: No authorization code received", 400
    
    # Обмениваем код на токены
    token_url = "https://zoom.us/oauth/token"
    
    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': settings.oauth_redirect_url
    }
    
    auth = (settings.zoom_client_id, settings.zoom_client_secret)
    
    try:
        response = requests.post(token_url, data=data, auth=auth)
        response.raise_for_status()
        
        tokens = response.json()
        oauth_tokens['access_token'] = tokens['access_token']
        oauth_tokens['refresh_token'] = tokens['refresh_token']
        
        # Сохраняем токены в файл
        with open('/home/lisa/zoom-translator-bot/.zoom_tokens', 'w') as f:
            f.write(f"ACCESS_TOKEN={tokens['access_token']}\n")
            f.write(f"REFRESH_TOKEN={tokens['refresh_token']}\n")
        
        print("✓ OAuth tokens saved to .zoom_tokens")
        
        return """
        <html>
            <head><title>Success</title></head>
            <body>
                <h1>✓ Authorization Successful!</h1>
                <p>Zoom account has been authorized. You can close this window.</p>
                <p>Tokens saved to .zoom_tokens file</p>
            </body>
        </html>
        """
    
    except Exception as e:
        return f"Error getting tokens: {e}", 500

def get_authorization_url():
    """Генерирует URL для авторизации"""
    auth_url = (
        f"https://zoom.us/oauth/authorize?"
        f"response_type=code&"
        f"client_id={settings.zoom_client_id}&"
        f"redirect_uri={settings.oauth_redirect_url}"
    )
    return auth_url

if __name__ == "__main__":
    print("=" * 60)
    print("Zoom OAuth Authorization")
    print("=" * 60)
    print()
    print("1. Starting local server on https://zoom-bot-vm.westeurope.cloudapp.azure.com")
    print("2. Open this URL in browser to authorize:")
    print()
    
    auth_url = get_authorization_url()
    print(auth_url)
    print()
    print("3. After authorization, tokens will be saved to .zoom_tokens")
    print()
    print("Press Ctrl+C to stop the server")
    print("=" * 60)
    
    # Запускаем Flask сервер
    app.run(host='0.0.0.0', port=5000, debug=False)
