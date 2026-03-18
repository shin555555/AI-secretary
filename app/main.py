import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.line_webhook import router as line_router
from config.logging_config import setup_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    setup_logging()
    logger.info("凛（AI秘書）を起動しました")
    yield
    logger.info("凛（AI秘書）を停止しました")


app = FastAPI(title="凛 - AI秘書", version="0.1.0", lifespan=lifespan)

app.include_router(health_router)
app.include_router(line_router)
