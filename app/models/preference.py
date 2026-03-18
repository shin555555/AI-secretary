from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Preference(Base):
    """ユーザー好み設定テーブル"""

    __tablename__ = "preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)


class InteractionLog(Base):
    """行動ログテーブル（パーソナライズ用）"""

    __tablename__ = "interaction_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
