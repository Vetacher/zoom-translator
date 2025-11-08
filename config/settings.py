from pydantic_settings import BaseSettings
from typing import List
from pydantic import Field, ConfigDict

class Settings(BaseSettings):
    model_config = ConfigDict(extra='ignore', env_file='.env', env_file_encoding='utf-8')
    
    telegram_bot_token: str = Field(..., env='TELEGRAM_BOT_TOKEN')
    telegram_admin_ids: str = Field(default='', env='TELEGRAM_ADMIN_IDS')
    azure_speech_key: str = Field(..., env='AZURE_SPEECH_KEY')
    azure_speech_region: str = Field(..., env='AZURE_SPEECH_REGION')
    zoom_account_id: str = Field(..., env='ZOOM_ACCOUNT_ID')
    zoom_client_id: str = Field(..., env='ZOOM_CLIENT_ID')
    zoom_client_secret: str = Field(..., env='ZOOM_CLIENT_SECRET')
    zoom_email: str = Field(default='eventa@landao.vc', env='ZOOM_EMAIL')
    database_url: str = Field(default='sqlite:///./translator_bot.db', env='DATABASE_URL')
    
    @property
    def admin_ids_list(self) -> List[int]:
        if not self.telegram_admin_ids:
            return []
        return [int(id.strip()) for id in self.telegram_admin_ids.split(',') if id.strip()]

settings = Settings()

SUPPORTED_LANGUAGES = {
    'ru-RU': 'Русский',
    'en-US': 'English (US)',
    'de-DE': 'Deutsch',
    'fr-FR': 'Français',
    'es-ES': 'Español',
}
