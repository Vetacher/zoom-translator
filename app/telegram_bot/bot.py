import logging
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters

from app.config import settings
from app.telegram_bot import handlers

logger = logging.getLogger(__name__)

class TranslatorBot:
    def __init__(self):
        self.application = None
    
    def setup(self):
        self.application = Application.builder().token(settings.telegram_bot_token).build()
        
        self.application.add_handler(CommandHandler("start", handlers.start_command))
        self.application.add_handler(CommandHandler("help", handlers.help_command))
        self.application.add_handler(CommandHandler("new", handlers.new_session_command))
        self.application.add_handler(CommandHandler("sessions", handlers.sessions_command))
        self.application.add_handler(CommandHandler("settings", handlers.settings_command))
        
        self.application.add_handler(CallbackQueryHandler(handlers.button_callback))
        
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_message)
        )
        
        logger.info("Telegram bot handlers registered")
    
    async def start(self):
        logger.info("Starting Telegram bot...")
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        logger.info("Telegram bot started successfully")
    
    async def stop(self):
        logger.info("Stopping Telegram bot...")
        await self.application.updater.stop()
        await self.application.stop()
        await self.application.shutdown()
        logger.info("Telegram bot stopped")

bot = TranslatorBot()

