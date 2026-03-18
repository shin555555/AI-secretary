import asyncio
import logging

import httpx
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    PushMessageRequest,
    TextMessage,
)

from app.services.calendar_service import calendar_service
from app.services.task_service import task_service
from config.settings import settings

logger = logging.getLogger(__name__)

configuration = Configuration(access_token=settings.line_channel_access_token)


def _send_line_push(message: str) -> None:
    """LINE Push通知を送信"""
    if not settings.line_user_id:
        logger.warning("LINE_USER_IDが未設定のためPush通知をスキップ")
        return

    try:
        with ApiClient(configuration) as api_client:
            messaging_api = MessagingApi(api_client)
            messaging_api.push_message(
                PushMessageRequest(
                    to=settings.line_user_id,
                    messages=[TextMessage(text=message)],
                )
            )
        logger.info("LINE Push通知送信完了")
    except Exception as e:
        logger.error(f"LINE Push通知送信失敗: {e}")


def morning_briefing() -> None:
    """毎朝のブリーフィング（APSchedulerから呼ばれる）"""
    logger.info("朝ブリーフィング生成開始")

    try:
        # カレンダー予定を取得（非同期→同期ブリッジ）
        loop = asyncio.new_event_loop()
        today_events = loop.run_until_complete(calendar_service.get_today_events())
        loop.close()

        # タスクを取得
        today_tasks = task_service.get_today_due_tasks()
        upcoming_tasks = task_service.get_upcoming_due_tasks(days=2)
        # 今日期限を除外して明日期限のみ
        tomorrow_tasks = [t for t in upcoming_tasks if t not in today_tasks]

        # ブリーフィングメッセージ構築
        lines = ["おはようございます。本日のブリーフィングです。\n"]

        # 予定
        if today_events:
            formatted = calendar_service.format_events_for_display(today_events)
            lines.append(f"📅 今日の予定（{len(today_events)}件）")
            lines.append(formatted)
        else:
            lines.append("📅 今日の予定はありません。")

        lines.append("")

        # 今日期限のタスク
        if today_tasks:
            lines.append(f"✅ 今日期限のタスク（{len(today_tasks)}件）")
            for task in today_tasks:
                priority_mark = "【緊急】" if task.priority <= 2 else ""
                lines.append(f"• {task.title}{priority_mark}")
        else:
            lines.append("✅ 今日期限のタスクはありません。")

        lines.append("")

        # 明日期限のタスク
        if tomorrow_tasks:
            lines.append(f"⚠️ 明日期限のタスク（{len(tomorrow_tasks)}件）")
            for task in tomorrow_tasks:
                lines.append(f"• {task.title}")

        lines.append("\n本日もよろしくお願いいたします。")

        message = "\n".join(lines)
        _send_line_push(message)
        logger.info("朝ブリーフィング送信完了")

    except Exception as e:
        logger.error(f"朝ブリーフィング生成失敗: {e}")


def generate_recurring_tasks() -> None:
    """毎日0:00に翌日分の繰り返しタスクを自動生成"""
    logger.info("繰り返しタスク自動生成開始")
    try:
        generated = task_service.generate_daily_tasks()
        logger.info(f"繰り返しタスク {len(generated)}件 を自動生成しました")
    except Exception as e:
        logger.error(f"繰り返しタスク自動生成失敗: {e}")


def deadline_reminder() -> None:
    """期限24時間前のリマインド（毎日18:00に実行）"""
    logger.info("期限リマインドチェック開始")
    try:
        upcoming = task_service.get_upcoming_due_tasks(days=1)
        if not upcoming:
            logger.info("リマインド対象タスクなし")
            return

        lines = ["⏰ 期限が近いタスクのリマインドです。\n"]
        for task in upcoming:
            due_str = task.due_date.strftime("%m/%d") if task.due_date else ""
            lines.append(f"• {task.title}（期限: {due_str}）")

        _send_line_push("\n".join(lines))
        logger.info(f"リマインド送信: {len(upcoming)}件")

    except Exception as e:
        logger.error(f"期限リマインド送信失敗: {e}")
