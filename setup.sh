#!/bin/bash
echo "Устанавливаем зависимости..."
pip install python-telegram-bot==20.7
pip install azure-cognitiveservices-speech==1.34.0
pip install requests==2.31.0
pip install SQLAlchemy==2.0.23
pip install aiohttp==3.9.1
pip install python-dotenv==1.0.0
pip install pydantic==2.5.2
pip install pydantic-settings==2.1.0
pip install APScheduler==3.10.4
pip install pytz==2023.3
pip install loguru==0.7.2
pip install python-dateutil==2.8.2
pip install PyJWT==2.8.0

echo "Создаём структуру проекта..."
mkdir -p bot config models services utils logs

echo "Готово! Теперь нужно создать файлы проекта."
