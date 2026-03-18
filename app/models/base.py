from datetime import datetime

from sqlalchemy import DateTime, create_engine, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from config.settings import settings

# DB パス
DB_PATH = "data/secretary.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

# エンジン作成（SQLite、将来SQLCipherに置き換え予定）
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    """全モデルの基底クラス"""

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


def init_db() -> None:
    """テーブル作成（存在しなければ）"""
    import os

    os.makedirs("data", exist_ok=True)
    Base.metadata.create_all(bind=engine)
