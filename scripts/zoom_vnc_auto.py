#!/usr/bin/env python3
import os
import time

os.environ['DISPLAY'] = ':1'

# Просто открываем Chromium напрямую с URL
os.system('chromium-browser "https://us06web.zoom.us/j/85362759656?pwd=IYWaDfVMGkj2kAhkmeFY8j2PzjSEUk.1" &')

print("Browser should open in VNC!")
print("Manually join the meeting and speak")
print("\nWhen ready to record, press Enter...")
input()

print("Recording 30 seconds...")
os.system('parecord --device=zoom_capture.monitor --format=s16le --rate=16000 --channels=1 /tmp/vnc_audio.raw &')
time.sleep(30)
os.system('killall parecord')

print("Done! Check /tmp/vnc_audio.raw")
