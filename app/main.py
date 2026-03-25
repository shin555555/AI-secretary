import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.line_webhook import router as line_router
from app.models.base import init_db
from config.logging_config import setup_logging
from config.settings import settings

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone="Asia/Tokyo")


def _setup_scheduler() -> None:
    """APSchedulerのジョブを登録"""
    from scheduler.jobs import (
        deadline_reminder,
        generate_recurring_tasks,
        mail_notification_check,
        morning_briefing,
        schedule_reminder,
    )

    # 朝ブリーフィング（平日のみ）
    scheduler.add_job(
        morning_briefing,
        "cron",
        day_of_week="mon-fri",
        hour=settings.briefing_hour,
        minute=settings.briefing_minute,
        id="morning_briefing",
    )

    # 繰り返しタスク自動生成（毎日0:00）
    scheduler.add_job(
        generate_recurring_tasks,
        "cron",
        hour=0,
        minute=0,
        id="generate_recurring_tasks",
    )

    # 期限リマインド（毎日18:00）
    scheduler.add_job(
        deadline_reminder,
        "cron",
        hour=18,
        minute=0,
        id="deadline_reminder",
    )

    # 予定リマインド（10分間隔、平日のみ）
    scheduler.add_job(
        schedule_reminder,
        "cron",
        day_of_week="mon-fri",
        minute="*/10",
        id="schedule_reminder",
    )

    # メール着信通知（15分間隔、平日のみ）
    scheduler.add_job(
        mail_notification_check,
        "cron",
        day_of_week="mon-fri",
        minute="*/15",
        id="mail_notification_check",
    )

    scheduler.start()
    logger.info("スケジューラ起動完了（ブリーフィング/タスク生成/期限リマインド/予定リマインド/メール通知）")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    setup_logging()
    init_db()
    _setup_scheduler()
    logger.info("凛（AI秘書）を起動しました")
    yield
    scheduler.shutdown()
    logger.info("凛（AI秘書）を停止しました")


app = FastAPI(title="凛 - AI秘書", version="0.1.0", lifespan=lifespan)

app.include_router(health_router)
app.include_router(line_router)
