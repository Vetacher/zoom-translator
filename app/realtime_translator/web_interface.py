import asyncio
import json
from typing import Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import logging

logger = logging.getLogger(__name__)

class WebInterface:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.app = FastAPI()
        self.setup_routes()
    
    def setup_routes(self):
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await self.connect(websocket)
            try:
                while True:
                    await websocket.receive_text()
            except WebSocketDisconnect:
                await self.disconnect(websocket)
        
        @self.app.get("/")
        async def get_index():
            return HTMLResponse(content=self.get_html())
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"Client connected. Total: {len(self.active_connections)}")
        await websocket.send_json({"type": "system", "message": "Connected"})
    
    async def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info(f"Client disconnected. Total: {len(self.active_connections)}")
    
    async def broadcast(self, message: dict):
        if not self.active_connections:
            return
        
        disconnected = set()
        for conn in self.active_connections:
            try:
                await conn.send_json(message)
            except:
                disconnected.add(conn)
        
        self.active_connections -= disconnected
    
    def get_html(self):
        return """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Zoom Real-Time Translation</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            width: 100%;
            max-width: 1200px;
            height: 90vh;
            display: flex;
            flex-direction: column;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px 30px;
            border-radius: 20px 20px 0 0;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header h1 { font-size: 24px; font-weight: 600; }
        .status {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .status-dot {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: #4ade80;
            animation: pulse 2s infinite;
        }
        .status-dot.disconnected {
            background: #ef4444;
            animation: none;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .content {
            flex: 1;
            overflow-y: auto;
            padding: 30px;
            background: #f8fafc;
        }
        .message {
            background: white;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
            animation: slideIn 0.3s;
        }
        @keyframes slideIn {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .message-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 12px;
        }
        .speaker {
            font-weight: 600;
            color: #667eea;
            font-size: 16px;
        }
        .timestamp {
            color: #94a3b8;
            font-size: 12px;
        }
        .original {
            color: #475569;
            padding: 12px;
            background: #f1f5f9;
            border-radius: 8px;
            border-left: 3px solid #cbd5e1;
            margin-bottom: 12px;
            font-size: 14px;
        }
        .translation {
            color: #1e293b;
            font-size: 16px;
            padding: 12px;
            background: #dbeafe;
            border-radius: 8px;
            border-left: 3px solid #3b82f6;
            line-height: 1.5;
        }
        .controls {
            background: white;
            border-top: 1px solid #e2e8f0;
            padding: 20px 30px;
            display: flex;
            gap: 15px;
            align-items: center;
            border-radius: 0 0 20px 20px;
        }
        button {
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
        }
        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }
        .btn-secondary {
            background: #f1f5f9;
            color: #475569;
        }
        .btn-secondary:hover {
            background: #e2e8f0;
        }
        .volume-control {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-left: auto;
        }
        input[type="range"] {
            width: 120px;
        }
        .empty {
            text-align: center;
            padding: 60px 20px;
            color: #94a3b8;
        }
        .system-msg {
            text-align: center;
            padding: 12px;
            background: #f1f5f9;
            border-radius: 8px;
            color: #64748b;
            font-size: 14px;
            margin-bottom: 15px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🌐 Real-Time Translation</h1>
            <div class="status">
                <div class="status-dot" id="status"></div>
                <span id="statusText">Connecting...</span>
            </div>
        </div>
        <div class="content" id="content">
            <div class="empty">
                <h3>⏳ Waiting for translations...</h3>
                <p>Translations will appear here in real-time</p>
            </div>
        </div>
        <div class="controls">
            <button class="btn-primary" id="audioBtn" disabled>🔊 Enable Audio</button>
            <button class="btn-secondary" id="clearBtn">🗑️ Clear</button>
            <div class="volume-control">
                <span>🔊</span>
                <input type="range" id="volume" min="0" max="100" value="80" disabled>
                <span id="volumeText">80%</span>
            </div>
        </div>
    </div>
    <script>
        let ws, audioEnabled = false;
        const content = document.getElementById('content');
        const status = document.getElementById('status');
        const statusText = document.getElementById('statusText');
        const audioBtn = document.getElementById('audioBtn');
        const clearBtn = document.getElementById('clearBtn');
        const volume = document.getElementById('volume');
        const volumeText = document.getElementById('volumeText');
        
        function connect() {
            const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${location.host}/ws`);
            
            ws.onopen = () => {
                status.classList.remove('disconnected');
                statusText.textContent = 'Connected';
                audioBtn.disabled = false;
            };
            
            ws.onclose = () => {
                status.classList.add('disconnected');
                statusText.textContent = 'Disconnected';
                audioBtn.disabled = true;
                setTimeout(connect, 3000);
            };
            
            ws.onmessage = (e) => {
                const data = JSON.parse(e.data);
                if (data.type === 'translation') addTranslation(data);
                else if (data.type === 'system') addSystem(data.message);
            };
        }
        
        function addTranslation(data) {
            const empty = content.querySelector('.empty');
            if (empty) empty.remove();
            
            const div = document.createElement('div');
            div.className = 'message';
            div.innerHTML = `
                <div class="message-header">
                    <span class="speaker">${esc(data.speaker)}</span>
                    <span class="timestamp">${new Date().toLocaleTimeString()}</span>
                </div>
                <div class="original">🇷🇺 ${esc(data.original)}</div>
                <div class="translation">🇬🇧 ${esc(data.translation)}</div>
            `;
            content.appendChild(div);
            content.scrollTop = content.scrollHeight;
            
            if (audioEnabled && 'speechSynthesis' in window) {
                const utterance = new SpeechSynthesisUtterance(data.translation);
                utterance.lang = 'en-US';
                utterance.volume = volume.value / 100;
                speechSynthesis.speak(utterance);
            }
        }
        
        function addSystem(msg) {
            const empty = content.querySelector('.empty');
            if (empty) empty.remove();
            
            const div = document.createElement('div');
            div.className = 'system-msg';
            div.textContent = msg;
            content.appendChild(div);
            content.scrollTop = content.scrollHeight;
        }
        
        function esc(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        audioBtn.onclick = () => {
            audioEnabled = !audioEnabled;
            audioBtn.textContent = audioEnabled ? '🔇 Disable Audio' : '🔊 Enable Audio';
            volume.disabled = !audioEnabled;
        };
        
        clearBtn.onclick = () => {
            content.innerHTML = '<div class="empty"><h3>⏳ Waiting for translations...</h3></div>';
        };
        
        volume.oninput = (e) => {
            volumeText.textContent = e.target.value + '%';
        };
        
        connect();
    </script>
</body>
</html>"""

_instance = None

def get_web_interface():
    global _instance
    if _instance is None:
        _instance = WebInterface()
    return _instance
