import logging

from app.models.base import SessionLocal
from app.models.mail_filter import MailFilterRule

logger = logging.getLogger(__name__)


class MailFilterService:
    """メール仕分けルールの管理サービス"""

    def should_skip(self, email: str) -> bool:
        """DBのルールに基づいてスキップ判定"""
        email_lower = email.lower()
        try:
            with SessionLocal() as session:
                rules = session.query(MailFilterRule).filter(
                    MailFilterRule.rule_type.in_(["skip_sender", "skip_domain"])
                ).all()
                for rule in rules:
                    if rule.pattern.lower() in email_lower:
                        return True
        except Exception as e:
            logger.error(f"仕分けルール取得エラー: {e}")
        return False

    def is_important_sender(self, email: str) -> bool:
        """重要な送信者かチェック"""
        email_lower = email.lower()
        try:
            with SessionLocal() as session:
                rules = session.query(MailFilterRule).filter(
                    MailFilterRule.rule_type == "important_sender"
                ).all()
                for rule in rules:
                    if rule.pattern.lower() in email_lower:
                        return True
        except Exception as e:
            logger.error(f"重要送信者チェックエラー: {e}")
        return False

    def add_skip_rule(self, pattern: str, reason: str | None = None) -> MailFilterRule:
        """スキップルールを追加"""
        # ドメインかアドレスか判定
        rule_type = "skip_domain" if "@" not in pattern and "." in pattern else "skip_sender"
        with SessionLocal() as session:
            rule = MailFilterRule(rule_type=rule_type, pattern=pattern, reason=reason)
            session.add(rule)
            session.commit()
            session.refresh(rule)
            logger.info(f"仕分けルール追加: {rule_type} = {pattern}")
            return rule

    def add_important_sender(self, pattern: str) -> MailFilterRule:
        """重要送信者ルールを追加"""
        with SessionLocal() as session:
            rule = MailFilterRule(rule_type="important_sender", pattern=pattern)
            session.add(rule)
            session.commit()
            session.refresh(rule)
            logger.info(f"重要送信者追加: {pattern}")
            return rule


mail_filter_service = MailFilterService()
