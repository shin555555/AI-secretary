from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Task(Base):
    """タスクテーブル"""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=3)  # 1=緊急 〜 5=低
    due_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending | in_progress | done
    category: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # admin | support | personal
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    recurring_task_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class RecurringTask(Base):
    """繰り返しタスク定義テーブル"""

    __tablename__ = "recurring_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=3)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    rrule: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # daily | weekly | monthly | bimonthly | yearly
    day_of_week: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0=月〜6=日
    day_of_month: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1〜31
    months: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # "4,10" カンマ区切り
    remind_days_before: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
