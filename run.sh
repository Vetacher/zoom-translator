#!/bin/bash

# Скрипт запуска Zoom Translator Bot

echo "🤖 Starting Zoom Translator Bot..."

# Активируем виртуальное окружение
source ~/zoom-bot-env/bin/activate

# Переходим в директорию проекта
cd ~/zoom-translator-bot

# Проверяем наличие .env файла
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo "Please create .env file with required credentials"
    exit 1
fi

# Устанавливаем PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Запускаем приложение
echo "Starting application..."
python3 -m app.main

# Если произошла ошибка
if [ $? -ne 0 ]; then
    echo "❌ Error: Application crashed"
    exit 1
fi
