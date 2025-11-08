from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import logging
from datetime import datetime

from app.database import SessionLocal, create_meeting_session, get_active_sessions, update_session_status, get_or_create_user_settings, MeetingSession
from app.azure_translator.translator import AzureSpeechTranslator
from app.zoom_handler.client import zoom_client

logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    welcome_message = f"""
🤖 Добро пожаловать в AI Переводчик для Zoom!

Привет, {user.first_name}!

Я помогу вам организовать синхронный перевод на ваших Zoom встречах используя Azure AI.

📋 Доступные команды:
/new - Создать новую сессию перевода
/sessions - Посмотреть активные сессии
/settings - Настройки языков и параметров
/help - Помощь

🎯 Как это работает:
1. Вы создаёте встречу в Zoom
2. Добавляете переводчика events@landao.vc в настройках встречи
3. Через бота настраиваете языковую пару и время
4. Бот автоматически подключается и переводит в реальном времени

Начнём? Нажмите /new для создания первой сессии!
    """
    await update.message.reply_text(welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
📚 Подробная инструкция:

1️⃣ Создание встречи в Zoom:
   • Зайдите на zoom.us
   • Создайте встречу
   • В настройках добавьте events@landao.vc как участника

2️⃣ Настройка перевода в боте:
   • Нажмите /new
   • Отправьте ссылку на встречу
   • Выберите языковую пару
   • Укажите время начала (или "сейчас")

3️⃣ Дополнительные возможности:
   • Кастомный вокабуляр для точности
   • Выбор кастомных моделей Azure
   • Автоматические субтитры
   • Статус сессии в реальном времени

❓ Возникли проблемы?
   • /sessions - проверьте статус
   • Кнопка "Переподключиться" если встреча сбросилась

💡 Поддерживаемые языки:
Используйте /settings для выбора из 15+ языков
    """
    await update.message.reply_text(help_text)

async def new_session_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔗 Отправьте ссылку на Zoom встречу:\n\n"
        "Например: https://zoom.us/j/123456789\n"
        "или просто номер встречи: 123 456 789"
    )
    context.user_data['state'] = 'waiting_zoom_url'

async def handle_zoom_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    zoom_url = update.message.text.strip()
    context.user_data['zoom_url'] = zoom_url
    
    languages = AzureSpeechTranslator.get_supported_languages()
    keyboard = []
    for code, name in list(languages.items())[:8]:
        keyboard.append([InlineKeyboardButton(name, callback_data=f"source_{code}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🗣 Выберите исходный язык (на каком говорят на встрече):",
        reply_markup=reply_markup
    )
    context.user_data['state'] = 'waiting_source_language'

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data.startswith('source_'):
        source_lang = data.replace('source_', '')
        context.user_data['source_language'] = source_lang
        
        languages = AzureSpeechTranslator.get_supported_languages()
        keyboard = []
        for code, name in list(languages.items())[:8]:
            if code != source_lang:
                keyboard.append([InlineKeyboardButton(name, callback_data=f"target_{code}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "🎯 Выберите язык перевода:",
            reply_markup=reply_markup
        )
        context.user_data['state'] = 'waiting_target_language'
    
    elif data.startswith('target_'):
        target_lang = data.replace('target_', '')
        context.user_data['target_language'] = target_lang
        
        keyboard = [
            [InlineKeyboardButton("▶️ Начать сейчас", callback_data="time_now")],
            [InlineKeyboardButton("🕐 Запланировать на время", callback_data="time_schedule")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        source_name = AzureSpeechTranslator.get_supported_languages()[context.user_data['source_language']]
        target_name = AzureSpeechTranslator.get_supported_languages()[target_lang]
        
        await query.edit_message_text(
            f"✅ Языковая пара: {source_name} → {target_name}\n\n"
            "⏰ Когда начать перевод?",
            reply_markup=reply_markup
        )
        context.user_data['state'] = 'waiting_time'
    
    elif data.startswith('time_'):
        if data == 'time_now':
            await create_and_start_session(query, context, scheduled_time=None)
        else:
            await query.edit_message_text(
                "🕐 Отправьте время начала в формате:\n"
                "ЧЧ:ММ (например: 15:30)\n"
                "или дата и время: ДД.ММ ЧЧ:ММ (например: 25.10 15:30)"
            )
            context.user_data['state'] = 'waiting_time_input'
    
    elif data.startswith('reconnect_'):
        session_id = int(data.replace('reconnect_', ''))
        await reconnect_session(query, context, session_id)

async def create_and_start_session(query, context, scheduled_time=None):
    user_id = query.from_user.id
    zoom_url = context.user_data.get('zoom_url')
    source_lang = context.user_data.get('source_language')
    target_lang = context.user_data.get('target_language')
    
    db = SessionLocal()
    try:
        session = create_meeting_session(
            db=db,
            telegram_user_id=user_id,
            zoom_meeting_url=zoom_url,
            source_lang=source_lang,
            target_lang=target_lang,
            scheduled_time=scheduled_time
        )
        
        languages = AzureSpeechTranslator.get_supported_languages()
        source_name = languages[source_lang]
        target_name = languages[target_lang]
        
        if scheduled_time:
            status_text = f"📅 Запланирован на {scheduled_time.strftime('%d.%m.%Y %H:%M')}"
            status_emoji = "⏰"
        else:
            status_text = "▶️ Запускается..."
            status_emoji = "🟢"
        
        keyboard = [
            [InlineKeyboardButton("🔄 Переподключиться", callback_data=f"reconnect_{session.id}")],
            [InlineKeyboardButton("❌ Отменить", callback_data=f"cancel_{session.id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"{status_emoji} Сессия создана!\n\n"
            f"🔗 Встреча: {session.zoom_meeting_id}\n"
            f"🗣 Языки: {source_name} → {target_name}\n"
            f"📊 Статус: {status_text}\n\n"
            f"ID сессии: #{session.id}",
            reply_markup=reply_markup
        )
        context.user_data.clear()
    finally:
        db.close()

async def sessions_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db = SessionLocal()
    try:
        sessions = get_active_sessions(db, telegram_user_id=user_id)
        
        if not sessions:
            await update.message.reply_text(
                "📭 У вас нет активных сессий.\n\n"
                "Создайте новую сессию: /new"
            )
            return
        
        languages = AzureSpeechTranslator.get_supported_languages()
        
        for session in sessions:
            status_emoji = {
                'pending': '⏰',
                'active': '🟢',
                'completed': '✅',
                'failed': '❌'
            }.get(session.status, '❓')
            
            source_name = languages.get(session.source_language, session.source_language)
            target_name = languages.get(session.target_language, session.target_language)
            
            keyboard = [
                [InlineKeyboardButton("🔄 Переподключиться", callback_data=f"reconnect_{session.id}")],
                [InlineKeyboardButton("❌ Завершить", callback_data=f"cancel_{session.id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            message = (
                f"{status_emoji} Сессия #{session.id}\n\n"
                f"🔗 Встреча: {session.zoom_meeting_id}\n"
                f"🗣 Языки: {source_name} → {target_name}\n"
                f"📊 Статус: {session.status}\n"
                f"🕐 Создана: {session.created_at.strftime('%d.%m %H:%M')}"
            )
            
            if session.scheduled_time:
                message += f"\n⏰ Запланирована: {session.scheduled_time.strftime('%d.%m %H:%M')}"
            
            await update.message.reply_text(message, reply_markup=reply_markup)
    finally:
        db.close()

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db = SessionLocal()
    try:
        user_settings = get_or_create_user_settings(db, user_id)
        
        languages = AzureSpeechTranslator.get_supported_languages()
        source_name = languages.get(user_settings.default_source_language, 'Не установлен')
        target_name = languages.get(user_settings.default_target_language, 'Не установлен')
        
        keyboard = [
            [InlineKeyboardButton("🗣 Изменить исходный язык", callback_data="settings_source")],
            [InlineKeyboardButton("🎯 Изменить язык перевода", callback_data="settings_target")],
            [InlineKeyboardButton("🔔 Уведомления", callback_data="settings_notifications")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"⚙️ Ваши настройки:\n\n"
            f"🗣 Исходный язык: {source_name}\n"
            f"🎯 Язык перевода: {target_name}\n"
            f"🔔 Уведомления: {'✅ Включены' if user_settings.notifications_enabled else '❌ Выключены'}",
            reply_markup=reply_markup
        )
    finally:
        db.close()

async def reconnect_session(query, context, session_id):
    db = SessionLocal()
    try:
        session = db.query(MeetingSession).filter(MeetingSession.id == session_id).first()
        
        if not session:
            await query.edit_message_text("❌ Сессия не найдена")
            return
        
        update_session_status(db, session_id, "active")
        
        await query.edit_message_text(
            f"🔄 Переподключение к встрече {session.zoom_meeting_id}...\n\n"
            "Это может занять несколько секунд."
        )
    finally:
        db.close()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get('state')
    
    if state == 'waiting_zoom_url':
        await handle_zoom_url(update, context)
    elif state == 'waiting_time_input':
        await update.message.reply_text("⏰ Функция планирования времени в разработке. Используйте 'Начать сейчас'")
    else:
        await update.message.reply_text(
            "Используйте команды:\n"
            "/new - Новая сессия\n"
            "/sessions - Активные сессии\n"
            "/settings - Настройки\n"
            "/help - Помощь"
        )
