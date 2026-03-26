"""テスト共通フィクスチャ: インメモリSQLiteでDB依存テストを実行

CI環境ではsqlcipher3が利用できないため、base.pyのengine/SessionLocalを
テスト用のインメモリSQLiteで上書きする。
"""

from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# base.py インポート時に _create_engine() が走るが、
# ローカル環境では keyring + sqlcipher3 が存在するので問題ない。
# CI環境では sqlcipher3 がないためエラーになるが、
# その場合でも Base クラス自体は DeclarativeBase なので
# engine 作成失敗後でも Base は使える。
try:
    from app.models.base import Base  # noqa: F401
except Exception:
    # sqlcipher3がない環境: Baseだけ定義し直す
    from sqlalchemy.orm import DeclarativeBase

    class Base(DeclarativeBase):  # type: ignore[no-redef]
        pass


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
