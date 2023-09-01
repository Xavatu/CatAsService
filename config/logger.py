import os
import sys

from loguru import logger

log_level = os.getenv("LOG_LEVEL", "TRACE")

logger_parameters = {
    "sink": "logs/lp_{time}.log",
    "rotation": "500 MB",
    "retention": "30 days",
    "level": log_level,
}

fmt = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>"
)

logger.remove()
logger.add(sys.stdout, format=fmt)
logger.add(**logger_parameters, format=fmt)
