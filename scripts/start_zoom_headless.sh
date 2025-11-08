#!/bin/bash

# Запуск Zoom в headless режиме с виртуальным дисплеем

DISPLAY_NUM=99
RESOLUTION="1920x1080x24"

echo "Starting virtual display :$DISPLAY_NUM..."

# Останавливаем существующий Xvfb если есть
pkill -f "Xvfb :$DISPLAY_NUM" 2>/dev/null

# Запускаем виртуальный X сервер
Xvfb :$DISPLAY_NUM -screen 0 $RESOLUTION &
XVFB_PID=$!

sleep 2

# Устанавливаем DISPLAY
export DISPLAY=:$DISPLAY_NUM

# Запускаем PulseAudio
pulseaudio --check || pulseaudio --start

echo "✓ Virtual display started on :$DISPLAY_NUM (PID: $XVFB_PID)"
echo "✓ Display resolution: $RESOLUTION"
echo ""
echo "To run Zoom: DISPLAY=:$DISPLAY_NUM zoom"
