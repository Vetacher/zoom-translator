#!/usr/bin/env python3
"""
Zoom Web SDK Bot - подключается к встрече через браузер и захватывает аудио
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.async_api import async_playwright
import logging
import time
from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ZoomWebSDKBot:
    """
    Бот для подключения к Zoom через Web SDK
    """
    
    def __init__(self, meeting_url, display_name="AI Translator"):
        self.meeting_url = meeting_url
        self.display_name = display_name
        self.browser = None
        self.page = None
        self.playwright = None
    
    async def start_browser(self):
        """Запускает браузер"""
        logger.info("Starting browser...")
        
        self.playwright = await async_playwright().start()
        
        # Запускаем Chromium с настройками для аудио
        self.browser = await self.playwright.chromium.launch(
            headless=True,  # Без GUI
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled',
                '--use-fake-ui-for-media-stream',  # Разрешаем доступ к медиа
                '--use-fake-device-for-media-stream',  # Используем виртуальное устройство
                '--autoplay-policy=no-user-gesture-required'
            ]
        )
        
        # Создаём контекст с разрешениями
        context = await self.browser.new_context(
            permissions=['microphone', 'camera'],
            viewport={'width': 1920, 'height': 1080}
        )
        
        self.page = await context.new_page()
        
        logger.info("✓ Browser started")
    
    async def join_meeting(self):
        """Подключается к Zoom встрече"""
        logger.info(f"Joining meeting: {self.meeting_url}")
        
        try:
            # Извлекаем meeting ID из URL
            import re
            meeting_match = re.search(r'/j/(\d+)', self.meeting_url)
            pwd_match = re.search(r'pwd=([^&]+)', self.meeting_url)
            
            if not meeting_match:
                logger.error("Could not extract meeting ID from URL")
                return False
            
            meeting_id = meeting_match.group(1)
            pwd = pwd_match.group(1) if pwd_match else None
            
            logger.info(f"Meeting ID: {meeting_id}, Password: {pwd}")
            
            # Формируем URL для web client напрямую
            web_client_url = f"https://app.zoom.us/wc/join/{meeting_id}"
            if pwd:
                web_client_url += f"?pwd={pwd}"
            
            logger.info(f"Loading web client: {web_client_url}")
            
            # Загружаем страницу
            response = await self.page.goto(web_client_url, timeout=30000)
            logger.info(f"Page loaded, status: {response.status}")
            
            await asyncio.sleep(5)
            
            # Шаг 1: Кликаем "Use microphone and camera"
            logger.info("Looking for 'Use microphone' button...")
            
            use_mic_clicked = await self.page.evaluate("""
                () => {
                    const buttons = document.querySelectorAll('button');
                    for (const btn of buttons) {
                        const text = btn.textContent || btn.innerText || '';
                        if (text.includes('Use microphone') || 
                            text.includes('Использование микрофонов') ||
                            text.includes('microphone and camera')) {
                            btn.click();
                            return true;
                        }
                    }
                    return false;
                }
            """)
            
            if use_mic_clicked:
                logger.info("✓ Clicked 'Use microphone'")
            else:
                logger.warning("Could not find 'Use microphone' button, trying without...")
            
            await asyncio.sleep(5)
            
            # Шаг 2: Ждём форму имени
            logger.info("Waiting for name input form...")
            
            # Пробуем разные селекторы
            name_input = None
            name_selectors = [
                'input[placeholder*="имя" i]',
                'input[placeholder*="name" i]',
                'input[type="text"]',
                '#input-for-name'
            ]
            
            for selector in name_selectors:
                try:
                    name_input = await self.page.wait_for_selector(selector, timeout=5000, state='visible')
                    if name_input:
                        logger.info(f"✓ Found name input: {selector}")
                        break
                except:
                    continue
            
            if not name_input:
                logger.error("Could not find name input field")
                await self.page.screenshot(path='/tmp/zoom_no_name_input.png')
                return False
            
            # Вводим имя
            await name_input.click()
            await asyncio.sleep(0.5)
            await name_input.fill(self.display_name)
            logger.info(f"✓ Entered name: {self.display_name}")
            
            await asyncio.sleep(2)
            
            # Шаг 3: Кликаем "Войти" / "Join"
            logger.info("Looking for Join button...")
            
            join_clicked = await self.page.evaluate("""
                () => {
                    const buttons = document.querySelectorAll('button');
                    for (const btn of buttons) {
                        const text = btn.textContent || btn.innerText || '';
                        if (text.includes('Войти') || 
                            text.includes('Join')) {
                            btn.click();
                            return true;
                        }
                    }
                    return false;
                }
            """)
            
            if join_clicked:
                logger.info("✓ Clicked Join button")
            else:
                logger.error("Could not find Join button")
                return False
            
            # Ждём подключения
            await asyncio.sleep(10)
            
            logger.info("✓ Successfully joined meeting!")
            await self.page.screenshot(path='/tmp/zoom_in_meeting.png')
            return True
        
        except Exception as e:
            logger.error(f"Error joining meeting: {e}", exc_info=True)
            await self.page.screenshot(path='/tmp/zoom_error.png')
            return False
    
    async def setup_audio_capture(self):
        """Настраивает захват аудио из встречи"""
        logger.info("Setting up audio capture...")
        
        # Выполняем JavaScript для захвата аудио
        audio_script = """
        (async () => {
            // Получаем MediaStream из Zoom
            const audioContext = new AudioContext();
            const destination = audioContext.createMediaStreamDestination();
            
            // Пытаемся найти аудио элемент Zoom
            const audioElements = document.querySelectorAll('audio');
            
            for (const audio of audioElements) {
                if (audio.srcObject) {
                    const source = audioContext.createMediaStreamSource(audio.srcObject);
                    source.connect(destination);
                    console.log('Audio source connected!');
                }
            }
            
            return 'Audio capture setup complete';
        })();
        """
        
        try:
            result = await self.page.evaluate(audio_script)
            logger.info(f"✓ {result}")
            return True
        except Exception as e:
            logger.error(f"Error setting up audio capture: {e}")
            return False
    
    async def capture_audio_stream(self, duration=60):
        """
        Захватывает аудио поток
        
        Args:
            duration: Длительность захвата в секундах
        """
        logger.info(f"Capturing audio for {duration} seconds...")
        
        # TODO: Реализовать захват аудио через WebRTC
        # Нужно:
        # 1. Получить MediaStream через CDP (Chrome DevTools Protocol)
        # 2. Декодировать аудио
        # 3. Отправить в Azure Speech Translator
        
        # Пока просто ждём
        await asyncio.sleep(duration)
        
        logger.info("Audio capture completed")
    
    async def leave_meeting(self):
        """Выходит из встречи"""
        logger.info("Leaving meeting...")
        
        try:
            # Ищем кнопку "Leave"
            leave_button = await self.page.query_selector('button:has-text("Leave")')
            if leave_button:
                await leave_button.click()
                logger.info("✓ Left meeting")
        except:
            pass
    
    async def close(self):
        """Закрывает браузер"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        logger.info("✓ Browser closed")

async def main():
    """Главная функция"""
    if len(sys.argv) < 2:
        print("Usage: python3 zoom_web_sdk_bot.py <meeting_url>")
        print("Example: python3 zoom_web_sdk_bot.py https://zoom.us/j/1234567890")
        sys.exit(1)
    
    meeting_url = sys.argv[1]
    
    bot = ZoomWebSDKBot(meeting_url, display_name="AI Translator Bot")
    
    try:
        # Запускаем браузер
        await bot.start_browser()
        
        # Подключаемся к встрече
        if await bot.join_meeting():
            # Настраиваем захват аудио
            await bot.setup_audio_capture()
            
            # Захватываем аудио (60 секунд для теста)
            await bot.capture_audio_stream(duration=60)
            
            # Выходим
            await bot.leave_meeting()
        else:
            logger.error("Failed to join meeting")
    
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
    
    finally:
        await bot.close()

if __name__ == "__main__":
    asyncio.run(main())
