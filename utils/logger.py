import sys
from loguru import logger

logger.remove()
logger.add(sys.stdout, level="INFO", colorize=True)
logger.add("logs/bot_{time:YYYY-MM-DD}.log", rotation="00:00", retention="30 days", level="INFO")
