import json
import logging
from datetime import datetime

from sqlalchemy import select

from app.models.base import SessionLocal
from app.models.preference import InteractionLog, Preference

logger = logging.getLogger(__name__)


class PreferenceService:
    """ユーザー好み設定の管理"""

    def set_preference(self, key: str, value: str) -> None:
        """設定を保存（既存キーは上書き）"""
        with SessionLocal() as session:
            stmt = select(Preference).where(Preference.key == key)
            pref = session.execute(stmt).scalars().first()
            if pref:
                pref.value = value
            else:
                pref = Preference(key=key, value=value)
                session.add(pref)
            session.commit()
            logger.info(f"設定保存: {key}={value}")

    def get_preference(self, key: str, default: str | None = None) -> str | None:
        """設定を取得"""
        with SessionLocal() as session:
            stmt = select(Preference).where(Preference.key == key)
            pref = session.execute(stmt).scalars().first()
            return pref.value if pref else default

    def get_all_preferences(self) -> dict[str, str]:
        """全設定を取得"""
        with SessionLocal() as session:
            stmt = select(Preference)
            prefs = session.execute(stmt).scalars().all()
            return {p.key: p.value for p in prefs}

    def delete_preference(self, key: str) -> bool:
        """設定を削除"""
        with SessionLocal() as session:
            stmt = select(Preference).where(Preference.key == key)
            pref = session.execute(stmt).scalars().first()
            if not pref:
                return False
            session.delete(pref)
            session.commit()
            logger.info(f"設定削除: {key}")
            return True

    def log_interaction(self, action_type: str, metadata: dict | None = None) -> None:
        """行動ログを記録"""
        with SessionLocal() as session:
            log = InteractionLog(
                action_type=action_type,
                metadata_json=json.dumps(metadata, ensure_ascii=False) if metadata else None,
                timestamp=datetime.now(),
            )
            session.add(log)
            session.commit()

    def format_preferences_for_display(self) -> str:
        """設定一覧を表示用テキストに変換"""
        prefs = self.get_all_preferences()
        if not prefs:
            return "保存されている設定はありません。"

        lines = ["⚙️ 保存済みの設定：\n"]
        for key, value in prefs.items():
            lines.append(f"• {key}: {value}")
        return "\n".join(lines)


preference_service = PreferenceService()
