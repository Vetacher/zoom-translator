import asyncio
import logging
import sys
from threading import Thread

from app.config import settings, validate_settings
from app.database import init_db
from app.telegram_bot.bot import bot
from app.web_server import run_web_server

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=getattr(logging, settings.log_level),
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log')
    ]
)

logger = logging.getLogger(__name__)

def start_web_server_thread():
    logger.info("Starting web server in background thread")
    web_thread = Thread(target=run_web_server, daemon=True)
    web_thread.start()
    return web_thread

async def main():
    try:
        logger.info("Validating settings...")
        validate_settings()
        logger.info("✓ Settings validated successfully")
        
        logger.info("Initializing database...")
        init_db()
        logger.info("✓ Database initialized")
        
        logger.info("Starting web server...")
        web_thread = start_web_server_thread()
        logger.info(f"✓ Web server started on port {settings.flask_port}")
        
        logger.info("Setting up Telegram bot...")
        bot.setup()
        logger.info("✓ Telegram bot configured")
        
        logger.info("=" * 50)
        logger.info("🤖 Zoom Translator Bot is starting...")
        logger.info(f"🌐 Web server: http://0.0.0.0:{settings.flask_port}")
        logger.info(f"🔗 OAuth callback: {settings.oauth_redirect_url}")
        logger.info("=" * 50)
        
        await bot.start()
        await asyncio.Event().wait()
    
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        raise
    finally:
        if bot.application:
            await bot.stop()
        logger.info("Bot stopped successfully")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Application crashed: {e}", exc_info=True)
        sys.exit(1)
