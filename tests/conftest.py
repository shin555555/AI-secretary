"""テスト共通フィクスチャ: インメモリSQLiteでDB依存テストを実行"""

from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base


@pytest.fixture()
def db_session():
    """インメモリSQLiteでテスト用セッションを提供"""
    engine = create_engine("sqlite:///:memory:", echo=False)

    # 全モデルをインポートしてメタデータに登録
    import app.models.task  # noqa: F401

    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine)

    with patch("app.models.base.SessionLocal", TestSession):
        with patch("app.services.task_service.SessionLocal", TestSession):
            yield TestSession

    Base.metadata.drop_all(bind=engine)
