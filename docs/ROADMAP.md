## Roadmap: Zoom AI Interpreter

### Stage 1 – Recall MVP
- Завершить ingest: Recall.ai бот → WebSocket → Azure edge-сервис
- Поднять faster-whisper на Azure GPU, добавить VAD и частичные гипотезы
- Включить GPT-4o перевод (draft/final) и TTS в Azure с gender matching (через диаризацию + классификатор пола)
- Реализовать веб-страницу для Recall Output Media (WebSocket → AudioContext playback) + UI с черновым/финальным текстом и тезисами
- Измерить end-to-end latency и обкатать на реальных митингах

### Stage 2 – UX & Voice Matching
- Довести визуализацию (progressive refinement текста, блок тезисов)
- Диаризация и определение пола/эмоции → подбор голоса (Azure Neural TTS / кастом)
- Настройки точности: initial prompt для термино-глоссариев, post-processing

### Stage 3 – Interim Zoom Output (без Raw Data)
- Настроить виртуальный микрофон/loopback (VB-Audio/Loopback/ALSA) для аккаунта-переводчика
- Подобрать UX для второго канала: вручную назначать аккаунт Interpreter и подавать туда TTS через виртуальный микрофон
- Настроить мониторинг качества, предусмотреть fallback в общий канал при сбоях

### Stage 4 – Zoom Meeting SDK (Raw Data)
- Получить Business/Enterprise лицензии и запросить включение Raw Data
- Реализовать headless Meeting SDK бота: приём PCM, роль interpreter, отправка sendAudioRawData
- Минимизировать задержку, добавить jitter buffer, метрики и ресинхронизацию

### Stage 5 – Hardening & Scaling
- CI/CD (GitHub → Azure), авто-деплой, скрипты git pull и мониторинг
- Автоскейлинг ASR/TTS контейнеров, логирование, SLA метрики
- Сравнение Azure STT vs Whisper, окончательный выбор, финетюн глоссариев
- Подготовить коммерческие тарифы (монетизация vs 50–100 $/час рынка)

### Stage 6 – Extensions
- Эмоциональный TTS/intonation, мультиязычность, UI для заказчиков
- Исследовать интеграцию с Zoom interpreter каналами по мере развития API или выпуск собственного Meeting SDK клиента
