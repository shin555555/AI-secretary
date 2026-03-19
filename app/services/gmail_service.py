import base64
import logging
import re
from datetime import datetime
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config.settings import settings

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.compose",
]

# ルールベース自動スキップ: 送信元パターン
SKIP_SENDER_PATTERNS = [
    r"noreply@",
    r"no-reply@",
    r"no\.reply@",
    r"notification@",
    r"notifications@",
    r"mailer-daemon@",
    r"auto-confirm@",
    r"donotreply@",
    r"alert@",
    r"alerts@",
]

# ルールベース自動スキップ: ドメイン
SKIP_DOMAINS = [
    "accounts.google.com",
    "script.google.com",
    "amazonorder@",
    "facebookmail.com",
    "twitter.com",
    "linkedin.com",
    "marketing.",
    "newsletter.",
    "promo.",
]

# Gmailカテゴリ: スキップ対象
SKIP_CATEGORIES = {"CATEGORY_PROMOTIONS", "CATEGORY_SOCIAL", "CATEGORY_UPDATES", "CATEGORY_FORUMS"}


class GmailService:
    """Gmail の読み取り・下書き・送信サービス"""

    def __init__(self) -> None:
        self._cached_messages: list[dict] = []

    def _get_credentials(self) -> Credentials | None:
        """OAuth2認証情報を取得"""
        token_path = Path(settings.google_token_path)
        creds_path = Path(settings.google_credentials_path)

        creds = None
        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    token_path.write_text(creds.to_json(), encoding="utf-8")
                except Exception as e:
                    logger.error(f"トークン更新失敗: {e}")
                    return None
            elif creds_path.exists():
                flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
                creds = flow.run_local_server(port=0)
                token_path.write_text(creds.to_json(), encoding="utf-8")
            else:
                logger.error("Google認証情報ファイルが見つかりません")
                return None

        return creds

    def _build_service(self) -> Any | None:
        """Gmail APIサービスを構築"""
        creds = self._get_credentials()
        if not creds:
            return None
        try:
            return build("gmail", "v1", credentials=creds)
        except Exception as e:
            logger.error(f"Gmail APIサービス構築失敗: {e}")
            return None

    # --- メール取得 ---

    async def get_unread_messages(self, max_results: int = 20) -> list[dict] | None:
        """未読メールを取得してトリアージ済みリストを返す"""
        service = self._build_service()
        if not service:
            return None

        try:
            results = (
                service.users()
                .messages()
                .list(userId="me", q="is:unread is:inbox", maxResults=max_results)
                .execute()
            )
            message_ids = results.get("messages", [])
            if not message_ids:
                self._cached_messages = []
                return []

            messages = []
            for msg_info in message_ids:
                msg = (
                    service.users()
                    .messages()
                    .get(userId="me", id=msg_info["id"], format="metadata",
                         metadataHeaders=["From", "Subject", "Date", "List-Unsubscribe"])
                    .execute()
                )
                parsed = self._parse_message_metadata(msg)
                if parsed:
                    messages.append(parsed)

            # ルールベースフィルタ
            filtered = self._apply_rule_filters(messages)
            self._cached_messages = filtered
            return filtered

        except HttpError as e:
            logger.error(f"Gmail取得エラー: {e}")
            return None

    async def get_important_messages(self) -> list[dict] | None:
        """重要メールのみを返す（ルールベース除外済み）"""
        return await self.get_unread_messages()

    def get_cached_message(self, index: int) -> dict | None:
        """キャッシュ済みメッセージを番号で取得（1始まり）"""
        idx = index - 1
        if 0 <= idx < len(self._cached_messages):
            return self._cached_messages[idx]
        return None

    async def get_message_body(self, message_id: str, max_chars: int = 500) -> str | None:
        """メール本文を取得（冒頭のみ）"""
        service = self._build_service()
        if not service:
            return None

        try:
            msg = (
                service.users()
                .messages()
                .get(userId="me", id=message_id, format="full")
                .execute()
            )
            body = self._extract_body(msg.get("payload", {}))
            if body and len(body) > max_chars:
                body = body[:max_chars] + "..."
            return body
        except HttpError as e:
            logger.error(f"メール本文取得エラー: {e}")
            return None

    # --- 下書き・送信 ---

    async def create_draft(self, to: str, subject: str, body: str,
                           thread_id: str | None = None,
                           in_reply_to: str | None = None) -> dict | None:
        """Gmailの下書きフォルダに保存"""
        service = self._build_service()
        if not service:
            return None

        try:
            message = MIMEText(body, "plain", "utf-8")
            message["to"] = to
            message["subject"] = subject
            if in_reply_to:
                message["In-Reply-To"] = in_reply_to
                message["References"] = in_reply_to

            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
            draft_body: dict[str, Any] = {"message": {"raw": raw}}
            if thread_id:
                draft_body["message"]["threadId"] = thread_id

            draft = service.users().drafts().create(userId="me", body=draft_body).execute()
            logger.info(f"下書き作成: {draft['id']}")
            return {"draft_id": draft["id"], "to": to, "subject": subject}

        except HttpError as e:
            logger.error(f"下書き作成エラー: {e}")
            return None

    async def send_reply(self, to: str, subject: str, body: str,
                         thread_id: str | None = None,
                         in_reply_to: str | None = None) -> dict | None:
        """メールを直接送信"""
        service = self._build_service()
        if not service:
            return None

        try:
            message = MIMEText(body, "plain", "utf-8")
            message["to"] = to
            message["subject"] = subject
            if in_reply_to:
                message["In-Reply-To"] = in_reply_to
                message["References"] = in_reply_to

            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
            send_body: dict[str, Any] = {"raw": raw}
            if thread_id:
                send_body["threadId"] = thread_id

            sent = service.users().messages().send(userId="me", body=send_body).execute()
            logger.info(f"メール送信完了: {sent['id']}")
            return {"message_id": sent["id"], "to": to, "subject": subject}

        except HttpError as e:
            logger.error(f"メール送信エラー: {e}")
            return None

    async def get_drafts(self, max_results: int = 10) -> list[dict] | None:
        """下書き一覧を取得"""
        service = self._build_service()
        if not service:
            return None

        try:
            results = service.users().drafts().list(userId="me", maxResults=max_results).execute()
            draft_list = results.get("drafts", [])
            if not draft_list:
                return []

            drafts = []
            for d in draft_list:
                draft = service.users().drafts().get(userId="me", id=d["id"], format="full").execute()
                msg = draft.get("message", {})
                headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
                drafts.append({
                    "draft_id": d["id"],
                    "to": headers.get("to", ""),
                    "subject": headers.get("subject", "（件名なし）"),
                    "date": headers.get("date", ""),
                })
            return drafts

        except HttpError as e:
            logger.error(f"下書き一覧取得エラー: {e}")
            return None

    async def send_draft(self, draft_id: str) -> dict | None:
        """保存済み下書きを送信"""
        service = self._build_service()
        if not service:
            return None

        try:
            sent = service.users().drafts().send(userId="me", body={"id": draft_id}).execute()
            logger.info(f"下書き送信完了: {sent['id']}")
            return {"message_id": sent["id"]}
        except HttpError as e:
            logger.error(f"下書き送信エラー: {e}")
            return None

    # --- 内部ヘルパー ---

    def _parse_message_metadata(self, msg: dict) -> dict | None:
        """APIレスポンスからメタデータを抽出"""
        headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
        labels = set(msg.get("labelIds", []))

        from_raw = headers.get("From", "")
        subject = headers.get("Subject", "（件名なし）")
        date_str = headers.get("Date", "")
        has_unsubscribe = "List-Unsubscribe" in headers
        message_id_header = headers.get("Message-ID", "")

        # 差出人のパース: "名前 <email>" or "email"
        from_name, from_email = self._parse_from(from_raw)

        # 時刻パース
        time_str = ""
        try:
            # "Thu, 20 Mar 2026 14:23:00 +0900" のようなフォーマット
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(date_str)
            time_str = dt.strftime("%H:%M")
        except Exception:
            pass

        return {
            "id": msg["id"],
            "thread_id": msg.get("threadId", ""),
            "from_name": from_name,
            "from_email": from_email,
            "subject": subject,
            "time": time_str,
            "date": date_str,
            "labels": labels,
            "has_unsubscribe": has_unsubscribe,
            "message_id_header": message_id_header,
            "snippet": msg.get("snippet", ""),
        }

    def _parse_from(self, from_raw: str) -> tuple[str, str]:
        """'名前 <email>' → (名前, email)"""
        match = re.match(r"(.+?)\s*<(.+?)>", from_raw)
        if match:
            name = match.group(1).strip().strip('"')
            email = match.group(2).strip()
            return name, email
        return from_raw.strip(), from_raw.strip()

    def _apply_rule_filters(self, messages: list[dict]) -> list[dict]:
        """ルールベースでノイズメールを除外"""
        filtered = []
        for msg in messages:
            if self._should_skip(msg):
                continue
            filtered.append(msg)
        return filtered

    def _should_skip(self, msg: dict) -> bool:
        """メールをスキップすべきか判定"""
        email = msg["from_email"].lower()

        # Gmailカテゴリでスキップ
        if msg["labels"] & SKIP_CATEGORIES:
            return True

        # List-Unsubscribe ヘッダあり（メルマガ）
        if msg["has_unsubscribe"]:
            return True

        # 送信元パターン
        for pattern in SKIP_SENDER_PATTERNS:
            if re.search(pattern, email):
                return True

        # ドメインパターン
        for domain in SKIP_DOMAINS:
            if domain in email:
                return True

        # DBの仕分けルール（MailFilterRule）
        from app.services.mail_filter_service import mail_filter_service
        if mail_filter_service.should_skip(email):
            return True

        return False

    def _extract_body(self, payload: dict) -> str:
        """メール本文をプレーンテキストで抽出"""
        if payload.get("mimeType") == "text/plain":
            data = payload.get("body", {}).get("data", "")
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

        parts = payload.get("parts", [])
        for part in parts:
            if part.get("mimeType") == "text/plain":
                data = part.get("body", {}).get("data", "")
                if data:
                    return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
            # ネストされたパーツ
            if part.get("parts"):
                result = self._extract_body(part)
                if result:
                    return result

        # text/plain がなければ snippet を返す
        return ""

    def format_mail_list(self, messages: list[dict], triage_results: list[dict] | None = None) -> str:
        """メール一覧を表示用テキストに変換"""
        if not messages:
            return "📧 未読の重要メールはありません。"

        lines = [f"📧 重要メール一覧（{len(messages)}件）\n"]
        for i, msg in enumerate(messages, 1):
            triage_label = ""
            if triage_results and i <= len(triage_results):
                level = triage_results[i - 1].get("level", "")
                if level == "reply":
                    triage_label = "【要返信】"
                elif level == "check":
                    triage_label = "【要確認】"

            from_display = msg["from_name"] or msg["from_email"]
            summary = msg.get("triage_summary", msg.get("snippet", "")[:60])
            lines.append(f"{i}.{triage_label}{from_display} ({msg['time']})")
            lines.append(f"   件名: {msg['subject']}")
            if summary:
                lines.append(f"   要約: {summary}")
            lines.append("")

        lines.append("「メール1の詳細」で本文を表示、「メール1に下書き」で返信下書きを作成します。")
        return "\n".join(lines)

    def format_draft_list(self, drafts: list[dict]) -> str:
        """下書き一覧を表示用テキストに変換"""
        if not drafts:
            return "📝 下書きはありません。"

        lines = [f"📝 下書き一覧（{len(drafts)}件）\n"]
        for i, d in enumerate(drafts, 1):
            lines.append(f"{i}. → {d['to']}: {d['subject']}")
        lines.append("\n「下書き1を送信して」で送信できます。")
        return "\n".join(lines)

    def format_for_briefing(self, messages: list[dict], triage_results: list[dict] | None = None) -> str:
        """ブリーフィング用の簡潔なメール要約"""
        if not messages:
            return "📧 未読の重要メールはありません。"

        lines = [f"📧 未読の重要メール（{len(messages)}件）"]
        for msg in messages[:5]:  # ブリーフィングは最大5件
            triage_label = ""
            if triage_results:
                for tr in triage_results:
                    if tr.get("id") == msg["id"]:
                        if tr.get("level") == "reply":
                            triage_label = "【要返信】"
                        elif tr.get("level") == "check":
                            triage_label = "【要確認】"
                        break

            from_display = msg["from_name"] or msg["from_email"]
            lines.append(f"  • {from_display}: {msg['subject']}{triage_label}")

        return "\n".join(lines)


gmail_service = GmailService()
