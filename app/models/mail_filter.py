from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class MailFilterRule(Base):
    """メール仕分けルール（ユーザーフィードバックで蓄積）"""

    __tablename__ = "mail_filter_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # 'skip_sender', 'skip_domain', 'important_sender'
    pattern: Mapped[str] = mapped_column(String(200), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
