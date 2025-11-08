import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    def __init__(self):
        # Telegram
        self.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        admin_ids_str = os.getenv("TELEGRAM_ADMIN_IDS", "")
        self.telegram_admin_ids = [int(id.strip()) for id in admin_ids_str.split(",") if admin_ids_str and id.strip()]
        
        # Azure Speech
        self.azure_speech_key = os.getenv("AZURE_SPEECH_KEY", "")
        self.azure_speech_region = os.getenv("AZURE_SPEECH_REGION", "westeurope")
        
        # Zoom
        self.zoom_account_id = os.getenv("ZOOM_ACCOUNT_ID", "")
        self.zoom_client_id = os.getenv("ZOOM_CLIENT_ID", "")
        self.zoom_client_secret = os.getenv("ZOOM_CLIENT_SECRET", "")
        self.zoom_sdk_key = os.getenv("ZOOM_SDK_KEY", "")
        self.zoom_sdk_secret = os.getenv("ZOOM_SDK_SECRET", "")
        self.zoom_bot_jid = os.getenv("ZOOM_BOT_JID", "")
        self.zoom_email = os.getenv("ZOOM_EMAIL", "events@landao.vc")
        
        # Database
        self.database_url = os.getenv("DATABASE_URL", "sqlite:///./translator_bot.db")
        
        # Settings
        self.debug = os.getenv("DEBUG", "False").lower() == "true"
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.timezone = os.getenv("TIMEZONE", "Europe/Amsterdam")
        self.default_source_language = os.getenv("DEFAULT_SOURCE_LANGUAGE", "ru-RU")
        self.default_target_language = os.getenv("DEFAULT_TARGET_LANGUAGE", "en-US")
        self.enable_auto_subtitles = os.getenv("ENABLE_AUTO_SUBTITLES", "True").lower() == "true"
        self.enable_custom_vocabulary = os.getenv("ENABLE_CUSTOM_VOCABULARY", "True").lower() == "true"
        self.enable_scheduler = os.getenv("ENABLE_SCHEDULER", "True").lower() == "true"
        
        self.oauth_redirect_url = os.getenv("OAUTH_REDIRECT_URL", "https://zoom-bot-vm.westeurope.cloudapp.azure.com/oauth/callback")
        self.flask_port = int(os.getenv("FLASK_PORT", "5000"))

settings = Settings()

def validate_settings():
    required_fields = [
        ("telegram_bot_token", settings.telegram_bot_token),
        ("azure_speech_key", settings.azure_speech_key),
        ("zoom_client_id", settings.zoom_client_id),
        ("zoom_client_secret", settings.zoom_client_secret),
    ]
    
    missing = [field for field, value in required_fields if not value]
    
    if missing:
        raise ValueError(f"Missing required settings: {', '.join(missing)}")
    
    return True
