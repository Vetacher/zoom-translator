import requests
import time
import base64
import logging
from typing import Optional, Dict
from datetime import datetime, timedelta

from app.config import settings

logger = logging.getLogger(__name__)


class ZoomClient:
    """Клиент для работы с Zoom API"""
    
    def __init__(self):
        self.base_url = "https://api.zoom.us/v2"
        self.oauth_url = "https://zoom.us/oauth"
        self.access_token = None
        self.token_expires_at = None
    
    def _get_access_token(self) -> str:
        """
        Получает access token через Server-to-Server OAuth
        """
        # Проверяем, нужно ли обновить токен
        if self.access_token and self.token_expires_at:
            if datetime.now() < self.token_expires_at - timedelta(minutes=5):
                return self.access_token
        
        try:
            # Создаём базовую авторизацию
            credentials = f"{settings.zoom_client_id}:{settings.zoom_client_secret}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            
            # Запрашиваем токен
            url = f"{self.oauth_url}/token"
            headers = {
                "Authorization": f"Basic {encoded_credentials}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            data = {
                "grant_type": "account_credentials",
                "account_id": settings.zoom_account_id
            }
            
            response = requests.post(url, headers=headers, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data["access_token"]
            
            # Устанавливаем время истечения токена
            expires_in = token_data.get("expires_in", 3600)
            self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
            
            logger.info("Successfully obtained Zoom access token")
            return self.access_token
        
        except Exception as e:
            logger.error(f"Error getting Zoom access token: {e}")
            raise
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """
        Выполняет запрос к Zoom API
        
        Args:
            method: HTTP метод (GET, POST, PUT, DELETE)
            endpoint: API endpoint (без base_url)
            **kwargs: Дополнительные параметры для requests
        
        Returns:
            JSON ответ от API
        """
        token = self._get_access_token()
        url = f"{self.base_url}{endpoint}"
        
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        headers["Content-Type"] = "application/json"
        
        try:
            response = requests.request(method, url, headers=headers, **kwargs)
            response.raise_for_status()
            return response.json() if response.content else {}
        
        except requests.exceptions.HTTPError as e:
            logger.error(f"Zoom API error: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error making Zoom API request: {e}")
            raise
    
    def get_meeting_info(self, meeting_id: str) -> Dict:
        """
        Получает информацию о встрече
        
        Args:
            meeting_id: ID встречи
        
        Returns:
            Информация о встрече
        """
        return self._make_request("GET", f"/meetings/{meeting_id}")
    
    def list_user_meetings(self, user_id: str = "me", meeting_type: str = "scheduled") -> Dict:
        """
        Получает список встреч пользователя
        
        Args:
            user_id: ID пользователя (по умолчанию "me" - текущий)
            meeting_type: Тип встреч (scheduled, live, upcoming)
        
        Returns:
            Список встреч
        """
        params = {"type": meeting_type}
        return self._make_request("GET", f"/users/{user_id}/meetings", params=params)
    
    def add_meeting_registrant(self, meeting_id: str, email: str, first_name: str, last_name: str = "") -> Dict:
        """
        Добавляет участника во встречу
        
        Args:
            meeting_id: ID встречи
            email: Email участника
            first_name: Имя
            last_name: Фамилия
        
        Returns:
            Информация о регистрации
        """
        data = {
            "email": email,
            "first_name": first_name,
            "last_name": last_name
        }
        return self._make_request("POST", f"/meetings/{meeting_id}/registrants", json=data)
    
    def get_meeting_participants(self, meeting_id: str) -> Dict:
        """
        Получает список участников встречи (для прошедших встреч)
        
        Args:
            meeting_id: ID встречи
        
        Returns:
            Список участников
        """
        return self._make_request("GET", f"/past_meetings/{meeting_id}/participants")
    
    def update_meeting_settings(self, meeting_id: str, settings: Dict) -> Dict:
        """
        Обновляет настройки встречи
        
        Args:
            meeting_id: ID встречи
            settings: Словарь с настройками
        
        Returns:
            Обновлённая информация о встрече
        """
        data = {"settings": settings}
        return self._make_request("PATCH", f"/meetings/{meeting_id}", json=data)
    
    def enable_live_transcription(self, meeting_id: str) -> bool:
        """
        Включает live transcription для встречи
        
        Args:
            meeting_id: ID встречи
        
        Returns:
            True если успешно
        """
        try:
            settings = {
                "auto_recording": "cloud",
                "audio_transcription": True
            }
            self.update_meeting_settings(meeting_id, settings)
            logger.info(f"Live transcription enabled for meeting {meeting_id}")
            return True
        except Exception as e:
            logger.error(f"Error enabling live transcription: {e}")
            return False
    
    def get_meeting_token(self, meeting_number: str, role: int = 0) -> Optional[str]:
        """
        Генерирует токен для подключения к встрече через SDK
        
        Args:
            meeting_number: Номер встречи
            role: Роль (0 - participant, 1 - host)
        
        Returns:
            JWT токен для SDK
        """
        # Для Meeting SDK нужен специальный JWT токен
        # Это упрощённая версия, в реальности нужна библиотека PyJWT
        try:
            import jwt
            
            payload = {
                "appKey": settings.zoom_sdk_key,
                "sdkKey": settings.zoom_sdk_key,
                "mn": meeting_number,
                "role": role,
                "iat": int(time.time()),
                "exp": int(time.time()) + 7200,  # 2 часа
                "tokenExp": int(time.time()) + 7200
            }
            
            token = jwt.encode(payload, settings.zoom_sdk_secret, algorithm="HS256")
            return token
        
        except ImportError:
            logger.warning("PyJWT not installed, cannot generate SDK token")
            return None
        except Exception as e:
            logger.error(f"Error generating SDK token: {e}")
            return None


# Глобальный экземпляр клиента
zoom_client = ZoomClient()
