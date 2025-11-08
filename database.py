from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import json

from app.config import settings

# Создаём базу данных
engine = create_engine(settings.database_url, echo=settings.debug)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class MeetingSession(Base):
    """Модель для хранения сессий встреч"""
    __tablename__ = "meeting_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    telegram_user_id = Column(Integer, index=True)
    zoom_meeting_id = Column(String, index=True)
    zoom_meeting_url = Column(String)
    source_language = Column(String, default="ru-RU")
    target_language = Column(String, default="en-US")
    custom_vocabulary = Column(Text, nullable=True)  # JSON string
    status = Column(String, default="pending")  # pending, active, completed, failed
    scheduled_time = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    error_message = Column(Text, nullable=True)
    
    def set_vocabulary(self, vocab_list):
        """Сохраняет кастомный вокабуляр в JSON"""
        self.custom_vocabulary = json.dumps(vocab_list) if vocab_list else None
    
    def get_vocabulary(self):
        """Получает кастомный вокабуляр из JSON"""
        return json.loads(self.custom_vocabulary) if self.custom_vocabulary else []


class UserSettings(Base):
    """Модель для хранения пользовательских настроек"""
    __tablename__ = "user_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    telegram_user_id = Column(Integer, unique=True, index=True)
    default_source_language = Column(String, default="ru-RU")
    default_target_language = Column(String, default="en-US")
    azure_custom_model = Column(String, nullable=True)
    notifications_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Создаём таблицы в БД
def init_db():
    """Инициализирует базу данных"""
    Base.metadata.create_all(bind=engine)


# Функции для работы с БД
def get_db():
    """Создаёт сессию БД"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_meeting_session(db, telegram_user_id, zoom_meeting_url, source_lang, target_lang, scheduled_time=None):
    """Создаёт новую сессию встречи"""
    # Извлекаем Meeting ID из URL
    meeting_id = extract_meeting_id_from_url(zoom_meeting_url)
    
    session = MeetingSession(
        telegram_user_id=telegram_user_id,
        zoom_meeting_id=meeting_id,
        zoom_meeting_url=zoom_meeting_url,
        source_language=source_lang,
        target_language=target_lang,
        scheduled_time=scheduled_time,
        status="pending"
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def update_session_status(db, session_id, status, error_message=None):
    """Обновляет статус сессии"""
    session = db.query(MeetingSession).filter(MeetingSession.id == session_id).first()
    if session:
        session.status = status
        if error_message:
            session.error_message = error_message
        if status == "active" and not session.started_at:
            session.started_at = datetime.utcnow()
        elif status in ["completed", "failed"] and not session.ended_at:
            session.ended_at = datetime.utcnow()
        db.commit()
        db.refresh(session)
    return session


def get_active_sessions(db, telegram_user_id=None):
    """Получает активные сессии"""
    query = db.query(MeetingSession).filter(MeetingSession.status.in_(["pending", "active"]))
    if telegram_user_id:
        query = query.filter(MeetingSession.telegram_user_id == telegram_user_id)
    return query.all()


def extract_meeting_id_from_url(url):
    """Извлекает Meeting ID из Zoom URL"""
    import re
    # Паттерны для разных форматов Zoom URL
    patterns = [
        r'/j/(\d+)',  # https://zoom.us/j/123456789
        r'meeting_id=(\d+)',  # ?meeting_id=123456789
        r'/(\d{9,11})',  # просто ID в URL
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    # Если не нашли, возвращаем последние цифры из URL
    digits = re.findall(r'\d+', url)
    return digits[-1] if digits else "unknown"


def get_or_create_user_settings(db, telegram_user_id):
    """Получает или создаёт настройки пользователя"""
    user_settings = db.query(UserSettings).filter(
        UserSettings.telegram_user_id == telegram_user_id
    ).first()
    
    if not user_settings:
        user_settings = UserSettings(telegram_user_id=telegram_user_id)
        db.add(user_settings)
        db.commit()
        db.refresh(user_settings)
    
    return user_settings
