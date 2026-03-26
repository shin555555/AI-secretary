"""summary_report のカテゴリ別集計・期間判定のユニットテスト

_handle_summary_report は calendar_service / task_service に依存するため、
両方をモックし、集計ロジック・期間判定・出力フォーマットをテストする。
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from app.services.secretary import Secretary


@pytest.fixture()
def secretary():
    return Secretary()


def _make_event(title: str) -> dict:
    return {"title": title, "start": "2026-03-23T10:00:00+09:00"}


@pytest.fixture()
def _mock_services():
    """calendar_service と task_service をモック"""
    with patch("app.services.secretary.calendar_service") as cal, \
         patch("app.services.secretary.task_service") as ts:
        cal._get_events_between = AsyncMock(return_value=[])
        ts.get_completed_tasks_between.return_value = []
        ts.get_pending_tasks.return_value = []
        yield cal, ts


# ===== カテゴリ分類テスト =====


@pytest.mark.asyncio
class TestCategorization:
    async def test_mendan_category(self, secretary, _mock_services):
        cal, ts = _mock_services
        cal._get_events_between.return_value = [
            _make_event("Aさん面談"),
            _make_event("相談対応"),
            _make_event("面接"),
        ]
        result = await secretary._handle_summary_report("今週の振り返り")
        assert "面談・相談: 3件" in result

    async def test_meeting_category(self, secretary, _mock_services):
        cal, ts = _mock_services
        cal._get_events_between.return_value = [
            _make_event("チーム会議"),
            _make_event("打ち合わせ"),
            _make_event("定例ミーティング"),
            _make_event("週次MTG"),
        ]
        result = await secretary._handle_summary_report("今週の振り返り")
        assert "会議・打ち合わせ: 4件" in result

    async def test_training_category(self, secretary, _mock_services):
        cal, ts = _mock_services
        cal._get_events_between.return_value = [
            _make_event("新人研修"),
            _make_event("安全セミナー"),
            _make_event("勉強会"),
        ]
        result = await secretary._handle_summary_report("週報")
        assert "研修・セミナー: 3件" in result

    async def test_other_category(self, secretary, _mock_services):
        cal, ts = _mock_services
        cal._get_events_between.return_value = [
            _make_event("ランチ"),
            _make_event("移動"),
        ]
        result = await secretary._handle_summary_report("週報")
        assert "その他: 2件" in result

    async def test_mixed_categories(self, secretary, _mock_services):
        cal, ts = _mock_services
        cal._get_events_between.return_value = [
            _make_event("面談"),
            _make_event("会議"),
            _make_event("ランチ"),
        ]
        result = await secretary._handle_summary_report("週報")
        assert "面談・相談: 1件" in result
        assert "会議・打ち合わせ: 1件" in result
        assert "その他: 1件" in result
        assert "予定: 3件" in result


# ===== 期間判定テスト =====


@pytest.mark.asyncio
class TestPeriodDetection:
    async def test_this_week_default(self, secretary, _mock_services):
        cal, _ = _mock_services
        result = await secretary._handle_summary_report("振り返り")
        assert "今週" in result

    async def test_last_week(self, secretary, _mock_services):
        cal, _ = _mock_services
        result = await secretary._handle_summary_report("先週の振り返り")
        assert "先週" in result

    async def test_this_month(self, secretary, _mock_services):
        cal, _ = _mock_services
        result = await secretary._handle_summary_report("今月の実績")
        assert "今月" in result

    async def test_geppo_triggers_this_month(self, secretary, _mock_services):
        cal, _ = _mock_services
        result = await secretary._handle_summary_report("月報")
        assert "今月" in result

    async def test_last_month(self, secretary, _mock_services):
        cal, _ = _mock_services
        result = await secretary._handle_summary_report("先月の振り返り")
        assert "先月" in result


# ===== 完了タスク表示テスト =====


@pytest.mark.asyncio
class TestCompletedTasksDisplay:
    async def test_completed_tasks_shown(self, secretary, _mock_services):
        cal, ts = _mock_services

        class FakeTask:
            def __init__(self, title, completed_at):
                self.title = title
                self.completed_at = completed_at

        ts.get_completed_tasks_between.return_value = [
            FakeTask("報告書作成", datetime(2026, 3, 23)),
            FakeTask("メール返信", datetime(2026, 3, 24)),
        ]
        result = await secretary._handle_summary_report("週報")
        assert "完了タスク: 2件" in result
        assert "報告書作成" in result
        assert "メール返信" in result

    async def test_more_than_10_truncated(self, secretary, _mock_services):
        cal, ts = _mock_services

        class FakeTask:
            def __init__(self, title, completed_at):
                self.title = title
                self.completed_at = completed_at

        tasks = [FakeTask(f"タスク{i}", datetime(2026, 3, 20 + (i % 5))) for i in range(15)]
        ts.get_completed_tasks_between.return_value = tasks
        result = await secretary._handle_summary_report("週報")
        assert "完了タスク: 15件" in result
        assert "他 5件" in result

    async def test_no_events_no_tasks(self, secretary, _mock_services):
        result = await secretary._handle_summary_report("週報")
        assert "予定: 0件" in result
        assert "完了タスク: 0件" in result


# ===== 期限超過タスク表示テスト =====


@pytest.mark.asyncio
class TestOverdueTasks:
    async def test_overdue_shown(self, secretary, _mock_services):
        cal, ts = _mock_services

        class FakeTask:
            def __init__(self, title, due_date):
                self.title = title
                self.due_date = due_date
                self.priority = 3

        ts.get_pending_tasks.return_value = [
            FakeTask("遅延タスク", datetime.now() - timedelta(days=3)),
        ]
        result = await secretary._handle_summary_report("週報")
        assert "期限超過タスク: 1件" in result
        assert "遅延タスク" in result

    async def test_no_overdue(self, secretary, _mock_services):
        cal, ts = _mock_services

        class FakeTask:
            def __init__(self, title, due_date):
                self.title = title
                self.due_date = due_date
                self.priority = 3

        ts.get_pending_tasks.return_value = [
            FakeTask("未来タスク", datetime.now() + timedelta(days=5)),
        ]
        result = await secretary._handle_summary_report("週報")
        assert "期限超過" not in result
