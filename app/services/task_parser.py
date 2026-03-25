import json
import logging
import re
from datetime import datetime, timedelta

from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)

# LLMには日付計算をさせず、相対表現をそのまま返させる
TASK_PARSE_PROMPT = """\
以下のユーザーメッセージからタスク情報を抽出してJSON形式で返してください。

【重要】due_date_rawには、ユーザーが言った期限の表現をそのまま入れてください。
日付の計算は不要です。「金曜まで」なら"金曜"、「3月20日」なら"3/20"、「明日」なら"明日"とそのまま入れてください。

【抽出ルール】
- title: タスクのタイトル（「タスク追加：」等のプレフィックスは除く）
- due_date_raw: ユーザーが指定した期限の表現（そのまま。不明ならnull）
- priority: 1=緊急 〜 5=低（未指定なら3）
- category: "admin"（管理業務）| "support"（支援業務）| "personal"（個人）| null
- is_recurring: 繰り返しタスクかどうか（true/false）
- rrule: 繰り返しルール（繰り返しでなければnull）
  "daily" | "weekly" | "monthly" | "bimonthly" | "yearly"
- day_of_week: 曜日（0=月曜〜6=日曜、weekly用、それ以外はnull）
- day_of_month: 日（1〜31、monthly/yearly用、それ以外はnull）
- months: 対象月（カンマ区切り文字列、例: "4,10"、yearly等で使用、それ以外はnull）

【出力形式】JSONのみ返す（説明不要）
{{
  "title": "...",
  "due_date_raw": null,
  "priority": 3,
  "category": null,
  "is_recurring": false,
  "rrule": null,
  "day_of_week": null,
  "day_of_month": null,
  "months": null
}}

ユーザーメッセージ: {user_message}
"""

# 曜日マッピング（Python: 0=月曜〜6=日曜）
WEEKDAY_MAP = {
    "月": 0, "火": 1, "水": 2, "木": 3, "金": 4, "土": 5, "日": 6,
    "月曜": 0, "火曜": 1, "水曜": 2, "木曜": 3, "金曜": 4, "土曜": 5, "日曜": 6,
    "月曜日": 0, "火曜日": 1, "水曜日": 2, "木曜日": 3, "金曜日": 4, "土曜日": 5, "日曜日": 6,
}


def resolve_date(raw: str | None) -> datetime | None:
    """相対的な日付表現を正確なdatetimeに変換（コード側で計算）"""
    if not raw:
        return None

    now = datetime.now()
    today = now.replace(hour=23, minute=59, second=0, microsecond=0)

    # 「今日」
    if "今日" in raw:
        return today

    # 「一昨日」「おととい」
    if "一昨日" in raw or "おととい" in raw:
        return today - timedelta(days=2)

    # 「昨日」
    if "昨日" in raw:
        return today - timedelta(days=1)

    # 「明後日」「あさって」
    if "明後日" in raw or "あさって" in raw:
        return today + timedelta(days=2)

    # 「明日」
    if "明日" in raw:
        return today + timedelta(days=1)

    # 「X日後」「X日前」
    days_offset_match = re.search(r"(\d+)\s*日\s*(後|前|先)", raw)
    if days_offset_match:
        n = int(days_offset_match.group(1))
        direction = days_offset_match.group(2)
        if direction == "後":
            return today + timedelta(days=n)
        else:
            return today - timedelta(days=n)

    # 「X週間後」「X週間前」
    weeks_offset_match = re.search(r"(\d+)\s*週間?\s*(後|前|先)", raw)
    if weeks_offset_match:
        n = int(weeks_offset_match.group(1))
        direction = weeks_offset_match.group(2)
        if direction == "後":
            return today + timedelta(weeks=n)
        else:
            return today - timedelta(weeks=n)

    # 「Xヶ月後」「Xか月後」
    months_offset_match = re.search(r"(\d+)\s*[ヶかケ]?月\s*(後|前|先)", raw)
    if months_offset_match:
        n = int(months_offset_match.group(1))
        direction = months_offset_match.group(2)
        month = now.month + (n if direction == "後" else -n)
        year = now.year
        while month > 12:
            month -= 12
            year += 1
        while month < 1:
            month += 12
            year -= 1
        day = min(now.day, 28)
        return datetime(year, month, day, 23, 59)

    # 「今週末」「週末」
    if "今週末" in raw or "週末" in raw:
        days_to_saturday = (5 - now.weekday()) % 7
        if days_to_saturday == 0 and now.weekday() == 6:
            days_to_saturday = 6
        return today + timedelta(days=days_to_saturday)

    # 「再来週X曜」
    week_after_next_match = re.search(r"再来週\s*の?\s*([月火水木金土日])", raw)
    if week_after_next_match:
        target_weekday = WEEKDAY_MAP.get(week_after_next_match.group(1))
        if target_weekday is not None:
            days_ahead = (target_weekday - now.weekday()) % 7 + 14
            return today + timedelta(days=days_ahead)

    # 「来週X曜」
    next_week_match = re.search(r"来週\s*の?\s*([月火水木金土日])", raw)
    if next_week_match:
        target_weekday = WEEKDAY_MAP.get(next_week_match.group(1))
        if target_weekday is not None:
            days_ahead = (target_weekday - now.weekday()) % 7 + 7
            return today + timedelta(days=days_ahead)

    # 「今週X曜」
    this_week_match = re.search(r"今週\s*の?\s*([月火水木金土日])", raw)
    if this_week_match:
        target_weekday = WEEKDAY_MAP.get(this_week_match.group(1))
        if target_weekday is not None:
            days_ahead = (target_weekday - now.weekday()) % 7
            return today + timedelta(days=days_ahead)

    # 「X曜」「X曜日」（今週の、過ぎていたら来週）
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
            target = datetime(year, month, day, 23, 59)
            if target < now:
                target = datetime(year + 1, month, day, 23, 59)
            return target
        except ValueError:
            pass

    # 「X日」（日だけ指定）
    day_match = re.search(r"(\d{1,2})日", raw)
    if day_match:
        day = int(day_match.group(1))
        year = now.year
        month = now.month
        try:
            target = datetime(year, month, day, 23, 59)
            if target < now:
                # 来月
                month += 1
                if month > 12:
                    month = 1
                    year += 1
                target = datetime(year, month, day, 23, 59)
            return target
        except ValueError:
            pass

    logger.warning(f"日付表現を解釈できませんでした: {raw}")
    return None


async def parse_task_from_message(user_message: str) -> dict | None:
    """ユーザーメッセージからタスク情報をLLMで解析"""
    prompt = TASK_PARSE_PROMPT.format(user_message=user_message)

    raw = await llm_service.generate(prompt=prompt, temperature=0.1)

    try:
        clean = raw.strip()
        if "```" in clean:
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        parsed = json.loads(clean.strip())
    except (json.JSONDecodeError, IndexError) as e:
        logger.error(f"タスク解析失敗: {e} / raw={raw[:100]}")
        return None

    # コード側で日付を正確に計算
    due_date_raw = parsed.get("due_date_raw")
    resolved = resolve_date(due_date_raw)
    if resolved:
        parsed["due_date"] = resolved.isoformat()
    else:
        parsed["due_date"] = None

    return parsed
