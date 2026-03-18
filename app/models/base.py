import logging
import secrets
from datetime import datetime
from urllib.parse import quote as urlquote

import keyring
from sqlalchemy import DateTime, create_engine, event, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

logger = logging.getLogger(__name__)

# DB パス
DB_PATH = "data/secretary.db"

KEYRING_SERVICE = "ai-secretary"
KEYRING_KEY_NAME = "db_encryption_key"


def _get_or_create_db_key() -> str:
    """keyringから暗号化キーを取得。なければ生成して保存"""
    key = keyring.get_password(KEYRING_SERVICE, KEYRING_KEY_NAME)
    if key:
        return key

    key = secrets.token_hex(32)
    keyring.set_password(KEYRING_SERVICE, KEYRING_KEY_NAME, key)
    logger.info("DB encryption key generated and stored in OS keyring")
    return key


def _create_engine():
    """SQLCipher暗号化エンジンを作成"""
    db_key = _get_or_create_db_key()
    encoded_key = urlquote(db_key, safe="")
    database_url = f"sqlite+pysqlcipher://:{encoded_key}@/{DB_PATH}"

    eng = create_engine(database_url, echo=False)

    @event.listens_for(eng, "connect")
    def _set_cipher_pragmas(dbapi_conn, _connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA cipher_compatibility = 4")
        cursor.close()

    return eng


engine = _create_engine()
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

    # 全モデルをインポートしてメタデータに登録
    import app.models.conversation  # noqa: F401
    import app.models.preference  # noqa: F401
    import app.models.task  # noqa: F401

    os.makedirs("data", exist_ok=True)
    Base.metadata.create_all(bind=engine)
