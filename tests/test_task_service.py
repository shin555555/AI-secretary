"""task_service の CRUD・期限計算・完了タスク集計のユニットテスト"""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from app.services.task_service import TaskService


@pytest.fixture()
def svc(db_session):
    """テスト用TaskServiceインスタンス"""
    return TaskService()


# ===== add_task / get_pending_tasks =====


class TestAddAndGetTasks:
    def test_add_returns_task_with_id(self, svc):
        task = svc.add_task("テスト用タスク")
        assert task.id is not None
        assert task.title == "テスト用タスク"
        assert task.status == "pending"
        assert task.priority == 3

    def test_add_with_all_fields(self, svc):
        due = datetime(2026, 4, 1, 9, 0)
        task = svc.add_task(
            title="報告書作成",
            due_date=due,
            priority=1,
            category="admin",
            description="月次報告",
        )
        assert task.priority == 1
        assert task.due_date == due
        assert task.category == "admin"
        assert task.description == "月次報告"

    def test_get_pending_excludes_done(self, svc):
        svc.add_task("タスクA")
        t2 = svc.add_task("タスクB")
        svc.complete_task(t2.id)

        pending = svc.get_pending_tasks()
        titles = [t.title for t in pending]
        assert "タスクA" in titles
        assert "タスクB" not in titles

    def test_get_pending_ordered_by_priority(self, svc):
        svc.add_task("低優先", priority=5)
        svc.add_task("高優先", priority=1)
        svc.add_task("中優先", priority=3)

        pending = svc.get_pending_tasks()
        priorities = [t.priority for t in pending]
        assert priorities == sorted(priorities)


# ===== complete_task =====


class TestCompleteTask:
    def test_complete_by_id(self, svc):
        task = svc.add_task("完了テスト")
        result = svc.complete_task(task.id)
        assert result is not None
        assert result.status == "done"
        assert result.completed_at is not None

    def test_complete_nonexistent_returns_none(self, svc):
        assert svc.complete_task(9999) is None

    def test_complete_by_title(self, svc):
        svc.add_task("書類提出")
        result = svc.complete_task_by_title("書類")
        assert result is not None
        assert result.status == "done"

    def test_complete_by_title_no_match(self, svc):
        svc.add_task("書類提出")
        assert svc.complete_task_by_title("存在しない") is None


# ===== delete_task =====


class TestDeleteTask:
    def test_delete_by_id(self, svc):
        task = svc.add_task("削除テスト")
        deleted = svc.delete_task(task.id)
        assert deleted is not None
        assert deleted.title == "削除テスト"
        # 本当に消えたか確認
        assert svc.get_pending_tasks() == []

    def test_delete_nonexistent(self, svc):
        assert svc.delete_task(9999) is None

    def test_delete_by_title(self, svc):
        svc.add_task("不要タスク")
        deleted = svc.delete_task_by_title("不要")
        assert deleted is not None
        assert svc.get_pending_tasks() == []


# ===== update_task =====


class TestUpdateTask:
    def test_update_title(self, svc):
        task = svc.add_task("旧タイトル")
        updated = svc.update_task(task.id, new_title="新タイトル")
        assert updated.title == "新タイトル"

    def test_update_due_date(self, svc):
        task = svc.add_task("期限変更")
        new_due = datetime(2026, 5, 1, 12, 0)
        updated = svc.update_task(task.id, new_due_date=new_due)
        assert updated.due_date == new_due

    def test_update_priority(self, svc):
        task = svc.add_task("優先度変更", priority=3)
        updated = svc.update_task(task.id, new_priority=1)
        assert updated.priority == 1

    def test_clear_due_date(self, svc):
        task = svc.add_task("期限クリア", due_date=datetime(2026, 4, 1))
        updated = svc.update_task(task.id, clear_due_date=True)
        assert updated.due_date is None

    def test_update_nonexistent(self, svc):
        assert svc.update_task(9999, new_title="x") is None


# ===== find_task_by_keyword =====


class TestFindByKeyword:
    def test_finds_matching(self, svc):
        svc.add_task("面談の準備")
        svc.add_task("書類提出")
        results = svc.find_task_by_keyword("面談")
        assert len(results) == 1
        assert results[0].title == "面談の準備"

    def test_excludes_done(self, svc):
        t = svc.add_task("面談の準備")
        svc.complete_task(t.id)
        assert svc.find_task_by_keyword("面談") == []

    def test_no_match(self, svc):
        svc.add_task("書類提出")
        assert svc.find_task_by_keyword("存在しない") == []


# ===== get_today_due_tasks =====


class TestTodayDueTasks:
    def test_returns_today_tasks(self, svc):
        now = datetime.now()
        today_9am = now.replace(hour=9, minute=0, second=0, microsecond=0)
        tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)

        svc.add_task("今日のタスク", due_date=today_9am)
        svc.add_task("明日のタスク", due_date=tomorrow)

        today_tasks = svc.get_today_due_tasks()
        titles = [t.title for t in today_tasks]
        assert "今日のタスク" in titles
        assert "明日のタスク" not in titles


# ===== get_upcoming_due_tasks =====


class TestUpcomingDueTasks:
    def test_within_range(self, svc):
        now = datetime.now()
        svc.add_task("12時間後", due_date=now + timedelta(hours=12))
        svc.add_task("3日後", due_date=now + timedelta(days=3))

        upcoming = svc.get_upcoming_due_tasks(days=1)
        titles = [t.title for t in upcoming]
        assert "12時間後" in titles
        assert "3日後" not in titles

    def test_excludes_done(self, svc):
        now = datetime.now()
        t = svc.add_task("完了済み", due_date=now + timedelta(hours=6))
        svc.complete_task(t.id)

        assert svc.get_upcoming_due_tasks(days=1) == []


# ===== get_completed_tasks_between =====


class TestCompletedTasksBetween:
    def test_returns_completed_in_range(self, svc):
        t1 = svc.add_task("タスク1")
        t2 = svc.add_task("タスク2")
        t3 = svc.add_task("タスク3")

        # t1, t2を完了にする
        svc.complete_task(t1.id)
        svc.complete_task(t2.id)

        start = datetime.now() - timedelta(minutes=1)
        end = datetime.now() + timedelta(minutes=1)

        completed = svc.get_completed_tasks_between(start, end)
        titles = [t.title for t in completed]
        assert "タスク1" in titles
        assert "タスク2" in titles
        assert "タスク3" not in titles

    def test_empty_range(self, svc):
        t = svc.add_task("タスク")
        svc.complete_task(t.id)

        # 過去の範囲 → 空
        far_past = datetime(2020, 1, 1)
        far_past_end = datetime(2020, 1, 2)
        assert svc.get_completed_tasks_between(far_past, far_past_end) == []


# ===== 繰り返しタスク =====


class TestRecurringTasks:
    def test_add_and_get_recurring(self, svc):
        rt = svc.add_recurring_task(
            title="週次ミーティング",
            rrule="weekly",
            day_of_week=0,
            priority=2,
        )
        assert rt.id is not None
        assert rt.is_active is True

        active = svc.get_active_recurring_tasks()
        assert len(active) == 1
        assert active[0].title == "週次ミーティング"

    def test_deactivate_recurring(self, svc):
        svc.add_recurring_task(title="日報", rrule="daily")
        result = svc.deactivate_recurring_task("日報")
        assert result is not None
        assert result.is_active is False
        assert svc.get_active_recurring_tasks() == []

    def test_deactivate_no_match(self, svc):
        assert svc.deactivate_recurring_task("存在しない") is None


class TestGenerateDailyTasks:
    def test_daily_generates(self, svc):
        svc.add_recurring_task(title="朝礼", rrule="daily")
        generated = svc.generate_daily_tasks()
        assert len(generated) == 1
        assert generated[0].title == "朝礼"
        assert generated[0].recurring_task_id is not None

    def test_weekly_correct_day(self, svc):
        # 明日の曜日を算出
        tomorrow = datetime.now() + timedelta(days=1)
        weekday = tomorrow.weekday()

        svc.add_recurring_task(title="週次", rrule="weekly", day_of_week=weekday)
        svc.add_recurring_task(title="別曜日", rrule="weekly", day_of_week=(weekday + 1) % 7)

        generated = svc.generate_daily_tasks()
        titles = [t.title for t in generated]
        assert "週次" in titles
        assert "別曜日" not in titles

    def test_monthly_correct_day(self, svc):
        tomorrow = datetime.now() + timedelta(days=1)
        day = tomorrow.day

        svc.add_recurring_task(title="月次報告", rrule="monthly", day_of_month=day)
        svc.add_recurring_task(title="別日", rrule="monthly", day_of_month=((day % 28) + 1))

        generated = svc.generate_daily_tasks()
        titles = [t.title for t in generated]
        assert "月次報告" in titles
        assert "別日" not in titles

    def test_inactive_not_generated(self, svc):
        svc.add_recurring_task(title="無効タスク", rrule="daily")
        svc.deactivate_recurring_task("無効")
        generated = svc.generate_daily_tasks()
        assert generated == []


# ===== 表示フォーマット =====


class TestFormatDisplay:
    def test_empty_list(self, svc):
        result = svc.format_tasks_for_display([])
        assert "未完了のタスクはありません" in result

    def test_format_with_tasks(self, svc):
        t1 = svc.add_task("タスクA", priority=1, due_date=datetime(2026, 4, 1))
        t2 = svc.add_task("タスクB", priority=5)
        tasks = [t1, t2]
        result = svc.format_tasks_for_display(tasks)
        assert "タスクA" in result
        assert "04/01" in result
        assert "🔴" in result  # priority 1

    def test_format_recurring_empty(self, svc):
        result = svc.format_recurring_for_display([])
        assert "繰り返しタスクはありません" in result

    def test_format_recurring(self, svc):
        rt = svc.add_recurring_task(title="週次", rrule="weekly", day_of_week=0)
        result = svc.format_recurring_for_display([rt])
        assert "週次" in result
        assert "毎週" in result
        assert "月曜" in result
