#!/bin/bash

# Настройка виртуального аудио устройства для захвата

echo "Setting up virtual audio device..."

# Запускаем PulseAudio если не запущен
pulseaudio --check || pulseaudio --start

# Создаём виртуальный sink для захвата аудио
pactl load-module module-null-sink sink_name=zoom_capture sink_properties=device.description="Zoom_Audio_Capture"

# Создаём loopback для мониторинга
pactl load-module module-loopback source=zoom_capture.monitor sink=zoom_capture latency_msec=1

echo "✓ Virtual audio device 'zoom_capture' created"
echo "Audio will be captured from Zoom and available at: zoom_capture.monitor"

# Показываем список устройств
echo ""
echo "Available audio devices:"
pactl list sinks short
