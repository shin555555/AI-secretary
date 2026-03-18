import logging
from datetime import datetime

from sqlalchemy import select

from app.models.base import SessionLocal
from app.models.conversation import Conversation

logger = logging.getLogger(__name__)

# コンテキストに含める直近の会話ターン数
CONTEXT_TURNS = 10


class MemoryService:
    """会話履歴の保存・取得"""

    def save_message(
        self,
        role: str,
        content: str,
        intent: str | None = None,
    ) -> None:
        """会話メッセージをDBに保存"""
        with SessionLocal() as session:
            msg = Conversation(
                role=role,
                content=content,
                intent=intent,
                timestamp=datetime.now(),
            )
            session.add(msg)
            session.commit()

    def get_recent_context(self) -> list[dict[str, str]]:
        """直近の会話履歴をLLM用フォーマットで取得"""
        with SessionLocal() as session:
            stmt = (
                select(Conversation)
                .order_by(Conversation.id.desc())
                .limit(CONTEXT_TURNS * 2)  # user + assistant で2レコード/ターン
            )
            rows = session.execute(stmt).scalars().all()

        # 古い順に並び替え
        rows = list(reversed(rows))

        context: list[dict[str, str]] = []
        for row in rows:
            context.append({"role": row.role, "content": row.content})

        return context

    def format_context_for_prompt(self) -> str:
        """会話履歴をプロンプト用テキストに変換"""
        context = self.get_recent_context()
        if not context:
            return ""

        lines: list[str] = ["【直近の会話履歴】"]
        for msg in context:
            prefix = "ユーザー" if msg["role"] == "user" else "凛"
            lines.append(f"{prefix}: {msg['content']}")

        return "\n".join(lines)


# シングルトンインスタンス
memory_service = MemoryService()
