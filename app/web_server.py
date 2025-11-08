from flask import Flask, request, jsonify
import logging

from app.config import settings

logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/')
def index():
    return jsonify({
        "status": "running",
        "service": "Zoom Translator Bot",
        "version": "1.0.0"
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

@app.route('/oauth/callback')
def oauth_callback():
    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')
    
    if error:
        logger.error(f"OAuth error: {error}")
        return jsonify({"status": "error", "message": error}), 400
    
    if not code:
        logger.error("No authorization code received")
        return jsonify({"status": "error", "message": "No authorization code"}), 400
    
    logger.info(f"OAuth callback received - code: {code[:10]}..., state: {state}")
    
    return """
    <html>
        <head>
            <title>Zoom Authorization</title>
            <style>
                body { font-family: Arial, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
                .container { background: white; padding: 40px; border-radius: 10px; box-shadow: 0 10px 40px rgba(0,0,0,0.1); text-align: center; max-width: 400px; }
                .success { color: #10b981; font-size: 60px; margin-bottom: 20px; }
                h1 { color: #1f2937; margin-bottom: 10px; }
                p { color: #6b7280; line-height: 1.6; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="success">✓</div>
                <h1>Авторизация успешна!</h1>
                <p>Бот теперь подключен к Zoom. Вы можете закрыть это окно и вернуться в Telegram.</p>
            </div>
        </body>
    </html>
    """

def run_web_server():
    logger.info(f"Starting web server on port {settings.flask_port}")
    app.run(host='0.0.0.0', port=settings.flask_port, debug=settings.debug)

if __name__ == '__main__':
    run_web_server()
