"""datetime_parser の _resolve_date / _resolve_time ユニットテスト"""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from app.services.datetime_parser import _resolve_date, _resolve_time

# テスト基準日: 2026-03-26 木曜日 10:00
FIXED_NOW = datetime(2026, 3, 26, 10, 0, 0)
FIXED_TODAY = datetime(2026, 3, 26, 0, 0, 0)


@pytest.fixture(autouse=True)
def _freeze_now():
    with patch("app.services.datetime_parser.datetime") as mock_dt:
        mock_dt.now.return_value = FIXED_NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        yield


# ===== _resolve_date =====


class TestResolveDateBasic:
    def test_none(self):
        assert _resolve_date(None) is None

    def test_empty(self):
        assert _resolve_date("") is None

    def test_today(self):
        assert _resolve_date("今日") == FIXED_TODAY

    def test_yesterday(self):
        assert _resolve_date("昨日") == FIXED_TODAY - timedelta(days=1)

    def test_tomorrow(self):
        assert _resolve_date("明日") == FIXED_TODAY + timedelta(days=1)

    def test_day_before_yesterday(self):
        assert _resolve_date("一昨日") == FIXED_TODAY - timedelta(days=2)

    def test_ototoi(self):
        assert _resolve_date("おととい") == FIXED_TODAY - timedelta(days=2)

    def test_day_after_tomorrow(self):
        assert _resolve_date("明後日") == FIXED_TODAY + timedelta(days=2)

    def test_asatte(self):
        assert _resolve_date("あさって") == FIXED_TODAY + timedelta(days=2)


class TestResolveDateDaysOffset:
    def test_3days_later(self):
        assert _resolve_date("3日後") == FIXED_TODAY + timedelta(days=3)

    def test_5days_ago(self):
        assert _resolve_date("5日前") == FIXED_TODAY - timedelta(days=5)

    def test_1day_later(self):
        assert _resolve_date("1日後") == FIXED_TODAY + timedelta(days=1)

    def test_days_prior(self):
        assert _resolve_date("2日先") == FIXED_TODAY - timedelta(days=2)


class TestResolveDateWeeksOffset:
    def test_1week_later(self):
        assert _resolve_date("1週間後") == FIXED_TODAY + timedelta(weeks=1)

    def test_2weeks_ago(self):
        assert _resolve_date("2週間前") == FIXED_TODAY - timedelta(weeks=2)

    def test_1week_no_kan(self):
        # 「1週後」（「間」なし）
        assert _resolve_date("1週後") == FIXED_TODAY + timedelta(weeks=1)


class TestResolveDateMonthsOffset:
    def test_1month_later(self):
        result = _resolve_date("1ヶ月後")
        assert result == datetime(2026, 4, 26)

    def test_2months_ago(self):
        result = _resolve_date("2ヶ月前")
        assert result == datetime(2026, 1, 26)

    def test_kagetsu_variant(self):
        result = _resolve_date("3か月後")
        assert result == datetime(2026, 6, 26)

    def test_month_overflow(self):
        # 10ヶ月後 → 2027-01
        result = _resolve_date("10ヶ月後")
        assert result.year == 2027
        assert result.month == 1


class TestResolveDateWeekend:
    def test_weekend(self):
        # 木曜 → 土曜 = +2日
        result = _resolve_date("今週末")
        assert result == FIXED_TODAY + timedelta(days=2)
        assert result.weekday() == 5  # 土曜

    def test_shumatsu(self):
        result = _resolve_date("週末")
        assert result == FIXED_TODAY + timedelta(days=2)


class TestResolveDateNextWeek:
    def test_next_monday(self):
        # 木曜 → 来週月曜 = +4日 (月-木=-3, %7=4, +7=11? no: +7)
        result = _resolve_date("来週の月曜")
        # (0 - 3) % 7 = 4, +7 = 11
        assert result == FIXED_TODAY + timedelta(days=11)
        assert result.weekday() == 0

    def test_next_friday(self):
        result = _resolve_date("来週金曜")
        # (4 - 3) % 7 = 1, +7 = 8
        assert result == FIXED_TODAY + timedelta(days=8)
        assert result.weekday() == 4


class TestResolveDateWeekAfterNext:
    def test_week_after_next_wednesday(self):
        result = _resolve_date("再来週の水曜")
        # (2 - 3) % 7 = 6, +14 = 20
        assert result == FIXED_TODAY + timedelta(days=20)
        assert result.weekday() == 2

    def test_week_after_next_monday(self):
        result = _resolve_date("再来週月曜")
        # (0 - 3) % 7 = 4, +14 = 18
        assert result == FIXED_TODAY + timedelta(days=18)
        assert result.weekday() == 0


class TestResolveDateThisWeek:
    def test_this_friday(self):
        result = _resolve_date("今週の金曜")
        # (4 - 3) % 7 = 1
        assert result == FIXED_TODAY + timedelta(days=1)
        assert result.weekday() == 4

    def test_this_thursday(self):
        # 今日が木曜 → 今週の木曜 = 今日
        result = _resolve_date("今週木曜")
        assert result == FIXED_TODAY


class TestResolveDateWeekday:
    def test_friday(self):
        result = _resolve_date("金曜日")
        # (4 - 3) % 7 = 1
        assert result == FIXED_TODAY + timedelta(days=1)
        assert result.weekday() == 4

    def test_monday(self):
        result = _resolve_date("月曜")
        # (0 - 3) % 7 = 4
        assert result == FIXED_TODAY + timedelta(days=4)
        assert result.weekday() == 0

    def test_same_weekday(self):
        # 木曜 → 木 = 今日
        result = _resolve_date("木")
        assert result == FIXED_TODAY


class TestResolveDateAbsolute:
    def test_month_day_slash(self):
        result = _resolve_date("4/10")
        assert result == datetime(2026, 4, 10)

    def test_month_day_kanji(self):
        result = _resolve_date("4月10日")
        assert result == datetime(2026, 4, 10)

    def test_past_date_wraps_to_next_year(self):
        # 1月1日は過去 → 2027年
        result = _resolve_date("1/1")
        assert result == datetime(2027, 1, 1)

    def test_day_only(self):
        result = _resolve_date("28日")
        assert result == datetime(2026, 3, 28)

    def test_day_only_past_wraps_to_next_month(self):
        # 25日は昨日 → 来月
        result = _resolve_date("25日")
        assert result == datetime(2026, 4, 25)


class TestResolveDateEdgeCases:
    def test_23nichi_not_weekday(self):
        """「23日」が日曜の「日」にマッチしないことを確認"""
        result = _resolve_date("23日")
        assert result is not None
        assert result.day == 23

    def test_raigetsu_returns_none(self):
        assert _resolve_date("来月") is None

    def test_kongetsu_returns_none(self):
        assert _resolve_date("今月") is None

    def test_unrecognized(self):
        assert _resolve_date("そのうち") is None


# ===== _resolve_time =====


class TestResolveTime:
    def test_none(self):
        assert _resolve_time(None) is None

    def test_empty(self):
        assert _resolve_time("") is None

    def test_14ji(self):
        assert _resolve_time("14時") == (14, 0)

    def test_hhmm_colon(self):
        assert _resolve_time("16:30") == (16, 30)

    def test_hh_ji_mm_fun(self):
        assert _resolve_time("10時30分") == (10, 30)

    def test_gozen(self):
        assert _resolve_time("午前9時") == (9, 0)

    def test_gogo(self):
        assert _resolve_time("午後3時") == (15, 0)

    def test_gogo_12(self):
        # 午後12時 → 12（+12しない）
        assert _resolve_time("午後12時") == (12, 0)

    def test_gogo_with_minutes(self):
        assert _resolve_time("午後2時30分") == (14, 30)

    def test_gozen_with_minutes(self):
        assert _resolve_time("午前10時15分") == (10, 15)


class TestResolveTimeBusinessHour:
    """業務時間推定: 1〜6時 → 13〜18時"""

    def test_3ji_becomes_15(self):
        assert _resolve_time("3時") == (15, 0)

    def test_1ji_becomes_13(self):
        assert _resolve_time("1時") == (13, 0)

    def test_6ji_becomes_18(self):
        assert _resolve_time("6時") == (18, 0)

    def test_7ji_stays_7(self):
        assert _resolve_time("7時") == (7, 0)

    def test_0ji_stays_0(self):
        assert _resolve_time("0時") == (0, 0)

    def test_gogo_3ji_is_15(self):
        """午後3時は明示的なので15時"""
        assert _resolve_time("午後3時") == (15, 0)

    def test_gozen_3ji_is_3(self):
        """午前3時は明示的なので3時（業務時間推定より優先）"""
        assert _resolve_time("午前3時") == (3, 0)
