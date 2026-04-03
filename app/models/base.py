import logging
import os
import secrets
from datetime import datetime
from pathlib import Path
from urllib.parse import quote as urlquote

import keyring
from sqlalchemy import DateTime, create_engine, event, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

logger = logging.getLogger(__name__)

# DB パス
DB_PATH = "data/secretary.db"
DB_KEY_BACKUP_PATH = Path("data/db_key_backup.bin")

KEYRING_SERVICE = "ai-secretary"
KEYRING_KEY_NAME = "db_encryption_key"


def _save_key_backup(key: str) -> None:
    """暗号化キーをバックアップファイルに保存"""
    try:
        DB_KEY_BACKUP_PATH.parent.mkdir(parents=True, exist_ok=True)
        DB_KEY_BACKUP_PATH.write_text(key, encoding="utf-8")
        logger.info("DB encryption key backed up to %s", DB_KEY_BACKUP_PATH)
    except OSError as e:
        logger.warning("キーのバックアップ保存に失敗: %s", e)


def _load_key_backup() -> str | None:
    """バックアップファイルから暗号化キーを復元"""
    try:
        if DB_KEY_BACKUP_PATH.exists():
            key = DB_KEY_BACKUP_PATH.read_text(encoding="utf-8").strip()
            if key:
                return key
    except OSError as e:
        logger.warning("キーのバックアップ読み込みに失敗: %s", e)
    return None


def _get_or_create_db_key() -> str:
    """keyringから暗号化キーを取得。なければバックアップ→新規生成の順で試行"""
    # 1. OS keyring から取得
    key = keyring.get_password(KEYRING_SERVICE, KEYRING_KEY_NAME)
    if key:
        # keyring にあればバックアップも最新化
        _save_key_backup(key)
        return key

    # 2. バックアップファイルから復元
    key = _load_key_backup()
    if key:
        keyring.set_password(KEYRING_SERVICE, KEYRING_KEY_NAME, key)
        logger.info("DB encryption key restored from backup to OS keyring")
        return key

    # 3. 新規生成
    key = secrets.token_hex(32)
    keyring.set_password(KEYRING_SERVICE, KEYRING_KEY_NAME, key)
    _save_key_backup(key)
    logger.info("DB encryption key generated and stored in OS keyring + backup")
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
    import app.models.mail_filter  # noqa: F401
    import app.models.preference  # noqa: F401
    import app.models.task  # noqa: F401

    os.makedirs("data", exist_ok=True)
    Base.metadata.create_all(bind=engine)
