import requests
import time
import base64
import logging
from typing import Optional, Dict
from datetime import datetime, timedelta

from app.config import settings

logger = logging.getLogger(__name__)

class ZoomClient:
    def __init__(self):
        self.base_url = "https://api.zoom.us/v2"
        self.oauth_url = "https://zoom.us/oauth"
        self.access_token = None
        self.token_expires_at = None
    
    def _get_access_token(self) -> str:
        if self.access_token and self.token_expires_at:
            if datetime.now() < self.token_expires_at - timedelta(minutes=5):
                return self.access_token
        
        try:
            credentials = f"{settings.zoom_client_id}:{settings.zoom_client_secret}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            
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
            
            expires_in = token_data.get("expires_in", 3600)
            self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
            
            logger.info("Successfully obtained Zoom access token")
            return self.access_token
        
        except Exception as e:
            logger.error(f"Error getting Zoom access token: {e}")
            raise
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict:
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
        return self._make_request("GET", f"/meetings/{meeting_id}")

zoom_client = ZoomClient()
