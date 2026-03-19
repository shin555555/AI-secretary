import logging
from datetime import datetime, timedelta
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


class CalendarService:
    """Google Calendar の読み書きサービス"""

    def _get_credentials(self) -> Credentials | None:
        """OAuth2認証情報を取得（トークン自動更新付き）"""
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
                    logger.info("Google認証トークンを更新しました")
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
        """Calendar APIサービスを構築"""
        creds = self._get_credentials()
        if not creds:
            return None
        try:
            return build("calendar", "v3", credentials=creds)
        except Exception as e:
            logger.error(f"Calendar APIサービス構築失敗: {e}")
            return None

    async def get_today_events(self) -> list[dict]:
        """今日の予定を取得"""
        return await self._get_events_for_range(days=0)

    async def get_week_events(self, weeks_offset: int = 0) -> list[dict]:
        """今週または来週の予定を取得（月曜起点）"""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        start_of_week = today - timedelta(days=today.weekday()) + timedelta(weeks=weeks_offset)
        end_of_week = start_of_week + timedelta(days=7)
        return await self._get_events_between(start_of_week, end_of_week)

    async def get_upcoming_events(self, days: int = 7) -> list[dict]:
        """今日から指定日数分の予定を取得"""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        end = today + timedelta(days=days)
        return await self._get_events_between(today, end)

    async def _get_events_between(self, start: datetime, end: datetime) -> list[dict]:
        """指定期間の予定を取得"""
        service = self._build_service()
        if not service:
            return []

        try:
            result = (
                service.events()
                .list(
                    calendarId="primary",
                    timeMin=start.isoformat() + "+09:00",
                    timeMax=end.isoformat() + "+09:00",
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
            return self._parse_events(result.get("items", []))
        except HttpError as e:
            logger.error(f"カレンダー取得エラー: {e}")
            return []

    async def _get_events_for_range(self, days: int = 0) -> list[dict]:
        """指定日数のイベントを取得（days=0: 今日, days=1: 明日）"""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        target = today + timedelta(days=days)
        next_day = target + timedelta(days=1)

        service = self._build_service()
        if not service:
            return []

        try:
            result = (
                service.events()
                .list(
                    calendarId="primary",
                    timeMin=target.isoformat() + "+09:00",
                    timeMax=next_day.isoformat() + "+09:00",
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
            return self._parse_events(result.get("items", []))
        except HttpError as e:
            logger.error(f"カレンダー取得エラー: {e}")
            return []

    async def create_event(
        self,
        title: str,
        start_datetime: str | datetime,
        end_datetime: str | datetime | None = None,
        rrule: str | None = None,
    ) -> dict | None:
        """カレンダーにイベントを作成（繰り返しRRULE対応）"""
        service = self._build_service()
        if not service:
            return None

        # 文字列ならdatetimeに変換
        if isinstance(start_datetime, str):
            start_datetime = datetime.fromisoformat(start_datetime)
        if isinstance(end_datetime, str):
            end_datetime = datetime.fromisoformat(end_datetime)
        if end_datetime is None:
            end_datetime = start_datetime + timedelta(hours=1)

        event_body: dict = {
            "summary": title,
            "start": {"dateTime": start_datetime.isoformat(), "timeZone": "Asia/Tokyo"},
            "end": {"dateTime": end_datetime.isoformat(), "timeZone": "Asia/Tokyo"},
        }

        if rrule:
            event_body["recurrence"] = [f"RRULE:{rrule}"]

        # 重複チェック
        conflicts = await self._check_conflicts(start_datetime, end_datetime)
        if conflicts:
            logger.info(f"予定の重複検出: {[c['title'] for c in conflicts]}")
            conflict_names = "、".join(c["title"] for c in conflicts)
            return {"conflict": conflict_names, "conflicts": conflicts, "event": event_body}

        try:
            created = (
                service.events().insert(calendarId="primary", body=event_body).execute()
            )
            logger.info(f"予定を作成: {title}")
            return {
                "conflict": False,
                "event_id": created["id"],
                "title": title,
                "start": start_datetime.strftime("%Y/%m/%d %H:%M"),
            }
        except HttpError as e:
            logger.error(f"予定作成エラー: {e}")
            return None

    async def search_events(self, query: str) -> list[dict]:
        """キーワードで予定を検索（過去半年〜未来半年）"""
        service = self._build_service()
        if not service:
            return []

        now = datetime.now()
        time_min = (now - timedelta(days=180)).replace(hour=0, minute=0, second=0, microsecond=0)
        time_max = (now + timedelta(days=180)).replace(hour=23, minute=59, second=59, microsecond=0)

        try:
            result = (
                service.events()
                .list(
                    calendarId="primary",
                    q=query,
                    timeMin=time_min.isoformat() + "+09:00",
                    timeMax=time_max.isoformat() + "+09:00",
                    singleEvents=True,
                    orderBy="startTime",
                    maxResults=20,
                )
                .execute()
            )
            return self._parse_events(result.get("items", []))
        except HttpError as e:
            logger.error(f"予定検索エラー: {e}")
            return []

    async def _check_conflicts(
        self, start: datetime, end: datetime
    ) -> list[dict]:
        """指定時間帯の重複予定を確認"""
        service = self._build_service()
        if not service:
            return []

        try:
            result = (
                service.events()
                .list(
                    calendarId="primary",
                    timeMin=start.isoformat() + "+09:00",
                    timeMax=end.isoformat() + "+09:00",
                    singleEvents=True,
                )
                .execute()
            )
            return self._parse_events(result.get("items", []))
        except HttpError:
            return []

    def _parse_events(self, items: list) -> list[dict]:
        """APIレスポンスから必要な情報のみ抽出"""
        events = []
        for item in items:
            start = item.get("start", {})
            end = item.get("end", {})

            # 終日イベントと時刻指定イベントを統一
            start_str = start.get("dateTime") or start.get("date", "")
            end_str = end.get("dateTime") or end.get("date", "")

            events.append(
                {
                    "id": item.get("id", ""),
                    "title": item.get("summary", "（タイトルなし）"),
                    "start": start_str,
                    "end": end_str,
                    "all_day": "date" in start and "dateTime" not in start,
                }
            )
        return events

    def format_events_for_display(self, events: list[dict], show_date: bool = False) -> str:
        """イベントリストを表示用テキストに変換

        Args:
            show_date: Trueなら日付も表示（複数日にまたがる場合に使用）
        """
        if not events:
            return "予定はありません。"

        weekday_names = ["月", "火", "水", "木", "金", "土", "日"]
        lines = []
        current_date_str = ""

        for event in events:
            if event["all_day"]:
                if show_date:
                    try:
                        d = datetime.fromisoformat(event["start"])
                        date_label = f"{d.month}/{d.day}({weekday_names[d.weekday()]})"
                        if date_label != current_date_str:
                            current_date_str = date_label
                            lines.append(f"\n📆 {date_label}")
                    except ValueError:
                        pass
                lines.append(f"  • {event['title']}（終日）")
            else:
                try:
                    start_dt = datetime.fromisoformat(event["start"])
                    end_dt = datetime.fromisoformat(event["end"])

                    if show_date:
                        date_label = f"{start_dt.month}/{start_dt.day}({weekday_names[start_dt.weekday()]})"
                        if date_label != current_date_str:
                            current_date_str = date_label
                            lines.append(f"\n📆 {date_label}")

                    lines.append(
                        f"  • {start_dt.strftime('%H:%M')}-{end_dt.strftime('%H:%M')} {event['title']}"
                    )
                except ValueError:
                    lines.append(f"  • {event['title']}")

        return "\n".join(lines).strip()


calendar_service = CalendarService()
