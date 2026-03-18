import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config.settings import settings


def setup_logging() -> None:
    log_dir = Path("data/logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # ファイルハンドラ（ローテーション: 5MB x 3ファイル）
    file_handler = RotatingFileHandler(
        log_dir / "secretary.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    # コンソールハンドラ
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level.upper()))
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # 外部ライブラリのログレベルを抑制
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
