import logging
from datetime import datetime, timedelta

from sqlalchemy import select, update

from app.models.base import SessionLocal
from app.models.task import RecurringTask, Task

logger = logging.getLogger(__name__)


class TaskService:
    """タスクCRUD + 繰り返しタスク管理"""

    # --- 単発タスク ---

    def add_task(
        self,
        title: str,
        due_date: datetime | None = None,
        priority: int = 3,
        category: str | None = None,
        description: str | None = None,
        recurring_task_id: int | None = None,
    ) -> Task:
        """タスクを追加"""
        with SessionLocal() as session:
            task = Task(
                title=title,
                description=description,
                priority=priority,
                due_date=due_date,
                category=category,
                recurring_task_id=recurring_task_id,
            )
            session.add(task)
            session.commit()
            session.refresh(task)
            logger.info(f"タスク追加: {title} (id={task.id})")
            return task

    def get_pending_tasks(self) -> list[Task]:
        """未完了タスクを優先度→期限順で取得"""
        with SessionLocal() as session:
            stmt = (
                select(Task)
                .where(Task.status != "done")
                .order_by(Task.priority, Task.due_date.nulls_last())
            )
            return list(session.execute(stmt).scalars().all())

    def get_today_due_tasks(self) -> list[Task]:
        """今日期限のタスクを取得"""
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)

        with SessionLocal() as session:
            stmt = (
                select(Task)
                .where(
                    Task.status != "done",
                    Task.due_date >= today_start,
                    Task.due_date < today_end,
                )
                .order_by(Task.priority)
            )
            return list(session.execute(stmt).scalars().all())

    def get_upcoming_due_tasks(self, days: int = 1) -> list[Task]:
        """指定日数以内に期限が来るタスクを取得"""
        now = datetime.now()
        deadline = now + timedelta(days=days)

        with SessionLocal() as session:
            stmt = (
                select(Task)
                .where(
                    Task.status != "done",
                    Task.due_date >= now,
                    Task.due_date <= deadline,
                )
                .order_by(Task.due_date)
            )
            return list(session.execute(stmt).scalars().all())

    def get_completed_tasks_between(self, start: datetime, end: datetime) -> list[Task]:
        """指定期間内に完了したタスクを取得"""
        with SessionLocal() as session:
            stmt = (
                select(Task)
                .where(
                    Task.status == "done",
                    Task.completed_at >= start,
                    Task.completed_at < end,
                )
                .order_by(Task.completed_at)
            )
            return list(session.execute(stmt).scalars().all())

    def complete_task(self, task_id: int) -> Task | None:
        """タスクを完了にする"""
        with SessionLocal() as session:
            task = session.get(Task, task_id)
            if not task:
                return None
            task.status = "done"
            task.completed_at = datetime.now()
            session.commit()
            session.refresh(task)
            logger.info(f"タスク完了: {task.title} (id={task_id})")
            return task

    def complete_task_by_title(self, title_keyword: str) -> Task | None:
        """タイトルの部分一致でタスクを完了にする"""
        with SessionLocal() as session:
            stmt = (
                select(Task)
                .where(Task.status != "done", Task.title.contains(title_keyword))
                .order_by(Task.priority)
            )
            task = session.execute(stmt).scalars().first()
            if not task:
                return None
            task.status = "done"
            task.completed_at = datetime.now()
            session.commit()
            session.refresh(task)
            logger.info(f"タスク完了: {task.title} (id={task.id})")
            return task

    def delete_task(self, task_id: int) -> Task | None:
        """タスクをIDで削除"""
        with SessionLocal() as session:
            task = session.get(Task, task_id)
            if not task:
                return None
            title = task.title
            session.delete(task)
            session.commit()
            logger.info(f"タスク削除: {title} (id={task_id})")
            # 削除後はdetachedなのでtitleだけ返す用に仮オブジェクト作成
            deleted = Task(id=task_id, title=title)
            return deleted

    def update_task(
        self,
        task_id: int,
        new_title: str | None = None,
        new_due_date: datetime | None = None,
        new_priority: int | None = None,
        clear_due_date: bool = False,
    ) -> Task | None:
        """タスクを更新（タイトル・期限・優先度の部分更新）"""
        with SessionLocal() as session:
            task = session.get(Task, task_id)
            if not task:
                return None
            if new_title:
                task.title = new_title
            if new_due_date:
                task.due_date = new_due_date
            elif clear_due_date:
                task.due_date = None
            if new_priority is not None:
                task.priority = new_priority
            session.commit()
            session.refresh(task)
            logger.info(f"タスク更新: {task.title} (id={task_id})")
            return task

    def find_task_by_keyword(self, keyword: str) -> list[Task]:
        """キーワードでタスクを検索（未完了のみ）"""
        with SessionLocal() as session:
            stmt = (
                select(Task)
                .where(Task.status != "done", Task.title.contains(keyword))
                .order_by(Task.priority, Task.due_date.nulls_last())
            )
            return list(session.execute(stmt).scalars().all())

    def delete_task_by_title(self, title_keyword: str) -> Task | None:
        """タイトルの部分一致でタスクを削除"""
        with SessionLocal() as session:
            stmt = (
                select(Task)
                .where(Task.status != "done", Task.title.contains(title_keyword))
                .order_by(Task.priority)
            )
            task = session.execute(stmt).scalars().first()
            if not task:
                return None
            task_id = task.id
            title = task.title
            session.delete(task)
            session.commit()
            logger.info(f"タスク削除: {title} (id={task_id})")
            deleted = Task(id=task_id, title=title)
            return deleted

    # --- 繰り返しタスク ---

    def add_recurring_task(
        self,
        title: str,
        rrule: str,
        day_of_week: int | None = None,
        day_of_month: int | None = None,
        months: str | None = None,
        priority: int = 3,
        category: str | None = None,
        description: str | None = None,
        remind_days_before: int = 1,
    ) -> RecurringTask:
        """繰り返しタスクを登録"""
        with SessionLocal() as session:
            rt = RecurringTask(
                title=title,
                description=description,
                priority=priority,
                category=category,
                rrule=rrule,
                day_of_week=day_of_week,
                day_of_month=day_of_month,
                months=months,
                remind_days_before=remind_days_before,
            )
            session.add(rt)
            session.commit()
            session.refresh(rt)
            logger.info(f"繰り返しタスク登録: {title} ({rrule})")
            return rt

    def get_active_recurring_tasks(self) -> list[RecurringTask]:
        """有効な繰り返しタスクを取得"""
        with SessionLocal() as session:
            stmt = select(RecurringTask).where(RecurringTask.is_active == True)
            return list(session.execute(stmt).scalars().all())

    def deactivate_recurring_task(self, title_keyword: str) -> RecurringTask | None:
        """繰り返しタスクを無効化"""
        with SessionLocal() as session:
            stmt = select(RecurringTask).where(
                RecurringTask.is_active == True,
                RecurringTask.title.contains(title_keyword),
            )
            rt = session.execute(stmt).scalars().first()
            if not rt:
                return None
            rt.is_active = False
            session.commit()
            session.refresh(rt)
            logger.info(f"繰り返しタスク無効化: {rt.title}")
            return rt

    def generate_daily_tasks(self) -> list[Task]:
        """翌日分の繰り返しタスクを自動生成"""
        tomorrow = datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)
        weekday = tomorrow.weekday()  # 0=月〜6=日
        day = tomorrow.day
        month = tomorrow.month

        recurring = self.get_active_recurring_tasks()
        generated: list[Task] = []

        for rt in recurring:
            should_generate = False

            if rt.rrule == "daily":
                should_generate = True
            elif rt.rrule == "weekly" and rt.day_of_week == weekday:
                should_generate = True
            elif rt.rrule == "monthly" and rt.day_of_month == day:
                should_generate = True
            elif rt.rrule == "bimonthly" and rt.day_of_month == day and month % 2 == 0:
                should_generate = True
            elif rt.rrule == "yearly" and rt.day_of_month == day:
                if rt.months:
                    target_months = [int(m) for m in rt.months.split(",")]
                    if month in target_months:
                        should_generate = True
                elif month == tomorrow.month:
                    should_generate = True

            if should_generate:
                task = self.add_task(
                    title=rt.title,
                    due_date=tomorrow,
                    priority=rt.priority,
                    category=rt.category,
                    description=rt.description,
                    recurring_task_id=rt.id,
                )
                generated.append(task)
                logger.info(f"繰り返しタスク自動生成: {rt.title}")

        return generated

    # --- 表示フォーマット ---

    def format_tasks_for_display(self, tasks: list[Task]) -> str:
        """タスクリストを表示用テキストに変換"""
        if not tasks:
            return "未完了のタスクはありません。"

        priority_emoji = {1: "🔴", 2: "🟠", 3: "🟡", 4: "🟢", 5: "⚪"}
        lines = [f"📋 未完了タスク（{len(tasks)}件）\n"]

        for i, task in enumerate(tasks, 1):
            emoji = priority_emoji.get(task.priority, "🟡")
            due = ""
            if task.due_date:
                due = f"（期限: {task.due_date.strftime('%m/%d')}）"
            lines.append(f"{emoji} {i}. {task.title}{due}")

        lines.append("\n完了にするには「タスク1完了」のように送信してください。")
        return "\n".join(lines)

    def format_recurring_for_display(self, recurring: list[RecurringTask]) -> str:
        """繰り返しタスクリストを表示用テキストに変換"""
        if not recurring:
            return "登録済みの繰り返しタスクはありません。"

        rrule_labels = {
            "daily": "毎日",
            "weekly": "毎週",
            "monthly": "毎月",
            "bimonthly": "隔月",
            "yearly": "毎年",
        }
        weekday_labels = ["月", "火", "水", "木", "金", "土", "日"]

        lines = [f"🔁 繰り返しタスク（{len(recurring)}件）\n"]

        for i, rt in enumerate(recurring, 1):
            label = rrule_labels.get(rt.rrule, rt.rrule)
            detail = ""
            if rt.rrule == "weekly" and rt.day_of_week is not None:
                detail = f"{weekday_labels[rt.day_of_week]}曜"
            elif rt.day_of_month is not None:
                detail = f"{rt.day_of_month}日"
            lines.append(f"{i}. {rt.title}（{label}{detail}）")

        return "\n".join(lines)


task_service = TaskService()
