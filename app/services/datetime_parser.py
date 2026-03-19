import json
import logging
import re
from datetime import datetime, timedelta

from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)

DATETIME_PARSE_PROMPT = """\
以下のユーザーメッセージから予定情報を抽出してJSON形式で返してください。

【重要】日付・時刻の計算は不要です。ユーザーが言った表現をそのまま返してください。
- date_raw: 日付表現をそのまま（「明日」「金曜」「3/20」「23日」等）
- time_raw: 時刻表現をそのまま（「14時」「16:00」「午後3時」等。不明ならnull）
- duration_minutes: 所要時間（分）。不明なら60

【抽出ルール】
- title: 予定のタイトル（人名や「打ち合わせ」「面談」等）
- date_raw: ユーザーが言った日付表現（そのまま）
- time_raw: ユーザーが言った時刻表現（そのまま。不明ならnull）
- duration_minutes: 所要時間（分、不明なら60）
- rrule: 繰り返しルール（繰り返しなければnull）
  例: 毎週月曜 → "FREQ=WEEKLY;BYDAY=MO"
  例: 毎月15日 → "FREQ=MONTHLY;BYMONTHDAY=15"
  例: 毎年4月1日 → "FREQ=YEARLY;BYMONTH=4;BYMONTHDAY=1"
  例: 平日毎日 → "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR"

【出力形式】JSONのみ返す（説明不要）
{{
  "title": "...",
  "date_raw": "...",
  "time_raw": null,
  "duration_minutes": 60,
  "rrule": null
}}

ユーザーメッセージ: {user_message}
"""

# 曜日マッピング
WEEKDAY_MAP = {
    "月": 0, "火": 1, "水": 2, "木": 3, "金": 4, "土": 5, "日": 6,
    "月曜": 0, "火曜": 1, "水曜": 2, "木曜": 3, "金曜": 4, "土曜": 5, "日曜": 6,
    "月曜日": 0, "火曜日": 1, "水曜日": 2, "木曜日": 3, "金曜日": 4, "土曜日": 5, "日曜日": 6,
}


def _resolve_date(raw: str | None) -> datetime | None:
    """相対的な日付表現を正確なdateに変換"""
    if not raw:
        return None

    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if "今日" in raw:
        return today
    if "明後日" in raw:
        return today + timedelta(days=2)
    if "明日" in raw:
        return today + timedelta(days=1)

    # 「来週X曜」
    next_week_match = re.search(r"来週\s*([月火水木金土日])", raw)
    if next_week_match:
        target_weekday = WEEKDAY_MAP.get(next_week_match.group(1))
        if target_weekday is not None:
            days_ahead = (target_weekday - now.weekday()) % 7 + 7
            return today + timedelta(days=days_ahead)

    # 「X曜」「X曜日」（「X日」との誤マッチを防ぐため、数字直後の「日」は除外）
    for label, weekday_num in sorted(WEEKDAY_MAP.items(), key=lambda x: len(x[0]), reverse=True):
        if label in raw and not re.search(r"\d" + re.escape(label), raw):
            days_ahead = (weekday_num - now.weekday()) % 7
            if days_ahead == 0:
                return today
            return today + timedelta(days=days_ahead)

    # 「X月X日」「X/X」
    date_match = re.search(r"(\d{1,2})[/月](\d{1,2})", raw)
    if date_match:
        month = int(date_match.group(1))
        day = int(date_match.group(2))
        year = now.year
        try:
            target = datetime(year, month, day)
            if target.date() < now.date():
                target = datetime(year + 1, month, day)
            return target
        except ValueError:
            pass

    # 「X日」
    day_match = re.search(r"(\d{1,2})日", raw)
    if day_match:
        day = int(day_match.group(1))
        year = now.year
        month = now.month
        try:
            target = datetime(year, month, day)
            if target.date() < now.date():
                month += 1
                if month > 12:
                    month = 1
                    year += 1
                target = datetime(year, month, day)
            return target
        except ValueError:
            pass

    logger.warning(f"日付表現を解釈できませんでした: {raw}")
    return None


def _resolve_time(raw: str | None) -> tuple[int, int] | None:
    """時刻表現を (hour, minute) に変換"""
    if not raw:
        return None

    # 「午後X時」「午前X時」
    ampm_match = re.search(r"(午前|午後)\s*(\d{1,2})\s*時?(?:\s*(\d{1,2})\s*分)?", raw)
    if ampm_match:
        period = ampm_match.group(1)
        hour = int(ampm_match.group(2))
        minute = int(ampm_match.group(3)) if ampm_match.group(3) else 0
        if period == "午後" and hour < 12:
            hour += 12
        return (hour, minute)

    # 「HH:MM」「HH時MM分」「HH時」
    time_match = re.search(r"(\d{1,2})\s*[:時]\s*(\d{1,2})?", raw)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2)) if time_match.group(2) else 0
        return (hour, minute)

    return None


async def parse_schedule_from_message(user_message: str) -> dict | None:
    """ユーザーメッセージから予定情報をLLMで解析"""
    prompt = DATETIME_PARSE_PROMPT.format(user_message=user_message)

    raw = await llm_service.generate(prompt=prompt, temperature=0.1)

    try:
        clean = raw.strip()
        if "```" in clean:
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        parsed = json.loads(clean.strip())
    except (json.JSONDecodeError, IndexError) as e:
        logger.error(f"日時解析失敗: {e} / raw={raw[:100]}")
        return None

    # コード側で日付・時刻を正確に計算
    date = _resolve_date(parsed.get("date_raw"))
    time = _resolve_time(parsed.get("time_raw"))
    duration = parsed.get("duration_minutes", 60)

    if date is None:
        return parsed  # 日付不明でもtitleは返す

    if time:
        start_dt = date.replace(hour=time[0], minute=time[1])
    else:
        start_dt = date.replace(hour=9, minute=0)  # 時刻不明なら9:00

    end_dt = start_dt + timedelta(minutes=duration)

    return {
        "title": parsed.get("title", "無題"),
        "start_datetime": start_dt.isoformat(),
        "end_datetime": end_dt.isoformat(),
        "rrule": parsed.get("rrule"),
    }
