# 🌍 Real-Time Zoom Translator with Voice Synthesis

Полнофункциональный переводчик в реальном времени с озвучкой и отправкой обратно в Zoom.

## ✨ Возможности

1. ✅ **WebSocket Audio от Recall** → получение raw PCM audio в реальном времени
2. ✅ **Azure Speech Services** → транскрипция с определением спикеров (speaker diarization)
3. ✅ **Определение пола голоса** → автоматическое определение мужской/женский голос
4. ✅ **GPT-4o перевод** → с использованием glossary и фильтрацией мусорных слов
5. ✅ **Azure TTS синтез** → озвучка перевода соответствующим голосом (мужским или женским)
6. ✅ **Bot Output Media** → отправка озвученного перевода обратно в Zoom через Recall
7. ✅ **Web интерфейс** → отображение результатов на https://zoom-bot-vm.westeurope.cloudapp.azure.com/

## 📋 Что было добавлено

### 1. Glossary интеграция
```python
class GlossaryManager:
    """Загружает translation_glossary.json и добавляет в prompt GPT-4o"""
```

Автоматически использует термины из `config/translation_glossary.json`:
- Лиза Чернягина → Liza Cherniagina
- Telegram Mini Apps → Telegram Mini Apps
- ChatGPT → ChatGPT
- n8n → n8n
- И все остальные...

### 2. Фильтрация мусорных слов
```python
Rules:
- Remove filler words (So, Well, Like, You know, I mean, Actually, Basically, etc.)
- Make text clean and professional
```

### 3. Speaker Diarization
```python
class AzureSpeechTranscriber:
    """Использует ConversationTranscriber для определения спикеров"""
    
    def get_or_infer_gender(self, speaker_id: str) -> str:
        """Определяет пол спикера"""
```

Автоматически:
- Определяет разных спикеров (Speaker 1, Speaker 2, ...)
- Присваивает пол (male/female)
- Можно задать вручную через `set_speaker_gender()`

### 4. Azure TTS с выбором голоса
```python
class AzureTTSSynthesizer:
    VOICES = {
        "male": {"en-US": "en-US-GuyNeural"},
        "female": {"en-US": "en-US-JennyNeural"}
    }
```

Использует нейронные голоса Azure:
- **Мужской**: en-US-GuyNeural
- **Женский**: en-US-JennyNeural

### 5. Bot Output Media
```python
async def send_audio_to_zoom(self, audio_data: bytes):
    """Отправляет озвученный перевод обратно в Zoom"""
```

Конфигурация бота:
```python
"bot_media_output": {
    "enabled": True,
    "audio_enabled": True,
    "video_enabled": False
}
```

## 🚀 Установка

### 1. Скачайте файл на сервер:
```bash
scp realtime_azure_translator_websocket_final.py lisa@172.205.192.158:~/zoom-translator-bot/scripts/
```

### 2. Убедитесь что все зависимости установлены:
```bash
pip install --break-system-packages \
    websockets \
    azure-cognitiveservices-speech \
    openai \
    python-dotenv \
    fastapi \
    uvicorn \
    requests
```

### 3. Проверьте .env файл:
Все необходимые переменные уже настроены:
```bash
RECALL_API_KEY=ebc680954c84509706ae03f11937d3a97098e8b3
AZURE_SPEECH_KEY=6bzkZ6HGA9wNG9VlUoDD3vtC3lnJ7v4UU4T6uL5KdCblTuPPZFuaJQQJ99BJAC5...
AZURE_SPEECH_REGION=westeurope
AZURE_OPENAI_KEY=2tfFyQD2MSMxGr1ZrYCUtsFhsobeDLQ77YgB42AUkjfHgLXY4ljqJQQJ99BJACf...
AZURE_OPENAI_ENDPOINT=https://gpt-zoom-translator.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_QUALITY=translator-quality
WEBHOOK_URL=https://zoom-bot-vm.westeurope.cloudapp.azure.com
```

### 4. Убедитесь что glossary на месте:
```bash
ls -la ~/zoom-translator-bot/config/translation_glossary.json
```

## 🎯 Запуск

```bash
cd ~/zoom-translator-bot
python scripts/realtime_azure_translator_websocket_final.py "https://zoom.us/j/YOUR_MEETING_ID"
```

## 📊 Что происходит при запуске:

1. **Создание бота Recall** с включенными:
   - WebSocket audio input (получение audio)
   - Bot Output Media (отправка audio)

2. **Запуск Azure Speech** с:
   - Speaker diarization (определение спикеров)
   - Continuous recognition

3. **Подключение к WebSocket Recall**:
   - Получение raw PCM audio chunks
   - Отправка в Azure Speech

4. **Обработка каждого предложения**:
   ```
   Audio → Azure Speech → Transcription (RU) → GPT-4o + Glossary → Translation (EN) → Azure TTS → Audio → Recall → Zoom
   ```

5. **Веб-интерфейс**:
   - Доступен на: http://zoom-bot-vm.westeurope.cloudapp.azure.com:8000
   - Показывает real-time транскрипцию и переводы

## 🔧 Настройка голосов

### Автоматическое определение:
По умолчанию первый спикер = female, второй = male, и так далее попеременно.

### Ручная настройка:
Если нужно задать конкретный пол для спикера:

```python
# В коде добавьте после создания bot:
translator.azure_speech.set_speaker_gender("Guest", "male")
translator.azure_speech.set_speaker_gender("Speaker_1", "female")
```

### Доступные голоса:
Можно изменить в классе `AzureTTSSynthesizer`:

```python
VOICES = {
    "male": {
        "en-US": "en-US-GuyNeural",      # Изменить здесь
        "ru-RU": "ru-RU-DmitryNeural"
    },
    "female": {
        "en-US": "en-US-JennyNeural",    # Изменить здесь
        "ru-RU": "ru-RU-SvetlanaNeural"
    }
}
```

[Список всех голосов Azure](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=tts)

## 📝 Glossary

Для добавления новых терминов отредактируйте:
```bash
nano ~/zoom-translator-bot/config/translation_glossary.json
```

Формат:
```json
{
  "Русский термин": {
    "en": "English Translation",
    "description": "описание",
    "alternatives": ["альтернативы", "варианты"]
  }
}
```

## 🐛 Отладка

### Логи:
Все логи выводятся в консоль с префиксами:
- 🎤 Azure Speech
- 🌍 Translation
- 🔊 TTS Synthesis
- 📡 WebSocket
- 🤖 Bot events

### Проверка работы по шагам:

1. **Bot создан?**
   ```
   ✅ Bot created: <bot_id>
   📡 WebSocket audio streaming enabled
   🔊 Bot audio output enabled
   ```

2. **WebSocket подключен?**
   ```
   ✅ Connected to Recall WebSocket
   📡 Subscribed to audio stream
   ```

3. **Azure Speech работает?**
   ```
   ✅ Azure Speech recognition with diarization started
   ✅ Speaker Guest_1 (female): Привет всем!
   ```

4. **Перевод работает?**
   ```
   🌍 Translation: Hello everyone!
   ```

5. **TTS синтез работает?**
   ```
   🔊 Synthesized audio: 24576 bytes (female voice)
   ```

6. **Audio отправлен в Zoom?**
   ```
   ✅ Audio sent to Zoom successfully
   ```

## ⚠️ Возможные проблемы

### 1. "Bot Output Media not enabled"
Убедитесь что в конфигурации бота:
```python
"bot_media_output": {
    "enabled": True,
    "audio_enabled": True
}
```

### 2. Нет звука в Zoom
- Проверьте что бот не замьючен в Zoom
- Проверьте sample rate audio (должен быть 16000 Hz)

### 3. Glossary не работает
- Проверьте путь: `~/zoom-translator-bot/config/translation_glossary.json`
- Проверьте JSON формат (используйте `jq`)

### 4. TTS голос неправильный
- Проверьте логи: какой голос используется
- Измените в `VOICES` словаре класса `AzureTTSSynthesizer`

## 📚 API Reference

### Recall Bot Output Media
```bash
POST /bot/{bot_id}/output_media/audio
{
  "audio": "base64_encoded_audio",
  "sample_rate": 16000,
  "channels": 1
}
```

### Azure Speech Diarization
- Использует `ConversationTranscriber`
- Возвращает `speaker_id` для каждого utterance
- Поддерживает до 10 спикеров

### Azure TTS
- Формат: PCM 16kHz mono
- Голоса: Neural (лучшее качество)
- Latency: ~100-300ms

## 🎓 Дополнительная информация

- [Recall.ai Docs - Bot Output Media](https://www.recall.ai/blog/zoom-sdk-receiving-video-streams)
- [Azure Speech - Speaker Diarization](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/speaker-recognition-overview)
- [Azure TTS - Neural Voices](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=tts)

## 📞 Support

Если что-то не работает:
1. Проверьте логи
2. Проверьте .env файлы
3. Проверьте что все API ключи валидны
4. Убедитесь что glossary.json существует

---

**Версия**: 1.0.0 (Final)  
**Автор**: AI Assistant  
**Дата**: October 29, 2025
