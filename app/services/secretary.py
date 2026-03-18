import re
import logging
from datetime import datetime

from app.prompts.intent_classifier import INTENT_CLASSIFICATION_PROMPT, VALID_INTENTS
from app.prompts.system_prompt import SYSTEM_PROMPT
from app.services.calendar_service import calendar_service
from app.services.datetime_parser import parse_schedule_from_message
from app.services.llm_service import llm_service
from app.services.memory_service import memory_service
from app.services.pii_filter import pii_filter
from app.services.preference_service import preference_service
from app.services.task_parser import parse_task_from_message
from app.services.task_service import task_service

logger = logging.getLogger(__name__)


class Secretary:
    """凛のコアオーケストレータ: インテント分類 → サービスルーティング → 応答生成"""

    async def handle_message(self, user_message: str) -> str:
        """ユーザーメッセージを処理して応答を生成"""
        intent = await self._classify_intent(user_message)
        logger.info(f"インテント: {intent}")

        memory_service.save_message(role="user", content=user_message, intent=intent)

        # インテントに応じたルーティング
        handler_map = {
            "schedule_today": lambda: self._handle_schedule_today(),
            "schedule_week": lambda: self._handle_schedule_week(user_message),
            "schedule_create": lambda: self._handle_schedule_create(user_message),
            "task_add": lambda: self._handle_task_add(user_message),
            "task_recurring": lambda: self._handle_task_recurring(user_message),
            "task_list": lambda: self._handle_task_list(user_message),
            "task_done": lambda: self._handle_task_done(user_message),
            "task_delete": lambda: self._handle_task_delete(user_message),
            "task_priority": lambda: self._handle_task_priority(),
            "briefing": lambda: self._handle_briefing(),
            "preference": lambda: self._handle_preference(user_message),
        }

        handler = handler_map.get(intent)
        if handler:
            response = await handler()
        else:
            response = await self._handle_general(user_message, intent)

        memory_service.save_message(role="assistant", content=response)

        # 行動ログ記録
        preference_service.log_interaction(intent, {"message_length": len(user_message)})

        return response

    async def _classify_intent(self, user_message: str) -> str:
        """LLMでインテント分類"""
        prompt = INTENT_CLASSIFICATION_PROMPT.format(user_message=user_message)
        raw_intent = await llm_service.generate(prompt=prompt, temperature=0.1)

        intent = raw_intent.strip().lower()
        for valid in VALID_INTENTS:
            if valid in intent:
                return valid

        logger.warning(f"不明なインテント: {raw_intent} → generalにフォールバック")
        return "general"

    # --- カレンダー ---

    async def _handle_schedule_today(self) -> str:
        """今日の予定を取得して返答"""
        events = await calendar_service.get_today_events()
        if events is None:
            return "申し訳ございません、カレンダーへの接続に失敗しました。Google認証が完了しているか確認してください。"

        formatted = calendar_service.format_events_for_display(events)
        if formatted == "予定はありません。":
            return "本日の予定はございません。"

        return f"本日の予定です：\n\n{formatted}"

    async def _handle_schedule_week(self, user_message: str) -> str:
        """今週または来週の予定を取得して返答"""
        weeks_offset = 1 if any(w in user_message for w in ["来週", "next week"]) else 0
        events = await calendar_service.get_week_events(weeks_offset=weeks_offset)
        if events is None:
            return "申し訳ございません、カレンダーへの接続に失敗しました。"

        formatted = calendar_service.format_events_for_display(events)
        label = "来週" if weeks_offset == 1 else "今週"
        if formatted == "予定はありません。":
            return f"{label}の予定はございません。"

        return f"{label}の予定です：\n\n{formatted}"

    async def _handle_schedule_create(self, user_message: str) -> str:
        """予定を作成する"""
        parsed = await parse_schedule_from_message(user_message)
        if not parsed:
            return "予定の内容を読み取れませんでした。もう少し詳しく教えていただけますか？\n例：「明日14時から1時間、田中さんと面談」"

        title = parsed.get("title", "無題")
        start = parsed.get("start_datetime")
        end = parsed.get("end_datetime")
        rrule = parsed.get("rrule")

        if not start:
            return "日時を読み取れませんでした。具体的な日時を含めて教えてください。\n例：「3月20日15時から打ち合わせ」"

        result = await calendar_service.create_event(
            title=title, start_datetime=start, end_datetime=end, rrule=rrule,
        )

        if result is None:
            return "申し訳ございません、カレンダーへの登録に失敗しました。"

        if result.get("conflict"):
            conflict_info = result["conflict"]
            return f"⚠️ 時間が重複しています：{conflict_info}\n\nそれでも登録しますか？「はい」とお返事いただければ強制登録します。"

        repeat_note = f"（{rrule} で繰り返し）" if rrule else ""
        return f"✅ 予定を登録しました{repeat_note}\n\n📅 {title}\n⏰ {result.get('start', start)}"

    # --- タスク管理 ---

    async def _handle_task_add(self, user_message: str) -> str:
        """タスクを追加"""
        parsed = await parse_task_from_message(user_message)
        if not parsed:
            return "タスクの内容を読み取れませんでした。\n例：「タスク追加：報告書作成 金曜まで」"

        title = parsed.get("title", "無題")
        due_date = None
        if parsed.get("due_date"):
            try:
                due_date = datetime.fromisoformat(parsed["due_date"])
            except ValueError:
                pass

        priority = parsed.get("priority", 3)
        category = parsed.get("category")

        task = task_service.add_task(
            title=title, due_date=due_date, priority=priority, category=category,
        )

        due_str = f"\n📅 期限: {due_date.strftime('%m/%d')}" if due_date else ""
        return f"✅ タスクを追加しました。\n\n📋 {task.title}{due_str}"

    async def _handle_task_recurring(self, user_message: str) -> str:
        """繰り返しタスクを登録"""
        parsed = await parse_task_from_message(user_message)
        if not parsed or not parsed.get("is_recurring"):
            return "繰り返しタスクの内容を読み取れませんでした。\n例：「国保連請求 毎月7日」「出欠記録 毎日」"

        title = parsed.get("title", "無題")
        rrule = parsed.get("rrule", "monthly")
        day_of_week = parsed.get("day_of_week")
        day_of_month = parsed.get("day_of_month")
        months = parsed.get("months")
        priority = parsed.get("priority", 3)

        rt = task_service.add_recurring_task(
            title=title,
            rrule=rrule,
            day_of_week=day_of_week,
            day_of_month=day_of_month,
            months=months,
            priority=priority,
        )

        rrule_labels = {
            "daily": "毎日", "weekly": "毎週", "monthly": "毎月",
            "bimonthly": "隔月", "yearly": "毎年",
        }
        label = rrule_labels.get(rrule, rrule)
        return f"🔁 繰り返しタスクを登録しました。\n\n📋 {rt.title}（{label}）\n期限前にリマインドもお送りします。"

    async def _handle_task_list(self, user_message: str) -> str:
        """タスク一覧を表示"""
        if any(w in user_message for w in ["ルーティン", "繰り返し", "定期"]):
            recurring = task_service.get_active_recurring_tasks()
            return task_service.format_recurring_for_display(recurring)

        tasks = task_service.get_pending_tasks()
        return task_service.format_tasks_for_display(tasks)

    async def _handle_task_done(self, user_message: str) -> str:
        """タスクを完了にする"""
        # 「タスク1完了」のようなパターン
        match = re.search(r"タスク\s*(\d+)", user_message)
        if match:
            task_id = int(match.group(1))
            # IDではなく表示番号（1始まり）なので、一覧から取得
            tasks = task_service.get_pending_tasks()
            idx = task_id - 1
            if 0 <= idx < len(tasks):
                completed = task_service.complete_task(tasks[idx].id)
                if completed:
                    return f"✅ 「{completed.title}」を完了にしました。お疲れさまです！"

        # タイトルキーワードで検索
        keyword = user_message.replace("完了", "").replace("タスク", "").strip()
        if keyword:
            completed = task_service.complete_task_by_title(keyword)
            if completed:
                return f"✅ 「{completed.title}」を完了にしました。お疲れさまです！"

        return "該当するタスクが見つかりませんでした。「タスク一覧」で番号を確認してから「タスク1完了」のように指定してください。"

    async def _handle_task_delete(self, user_message: str) -> str:
        """タスクを削除する"""
        # 「タスク1削除」のようなパターン
        match = re.search(r"タスク\s*(\d+)", user_message)
        if match:
            task_id = int(match.group(1))
            tasks = task_service.get_pending_tasks()
            idx = task_id - 1
            if 0 <= idx < len(tasks):
                deleted = task_service.delete_task(tasks[idx].id)
                if deleted:
                    return f"🗑️ 「{deleted.title}」を削除しました。"

        # タイトルキーワードで検索
        keyword = (
            user_message
            .replace("削除", "").replace("消して", "").replace("消す", "")
            .replace("タスク", "").replace("を", "").replace("して", "")
            .strip()
        )
        if keyword:
            deleted = task_service.delete_task_by_title(keyword)
            if deleted:
                return f"🗑️ 「{deleted.title}」を削除しました。"

        return "該当するタスクが見つかりませんでした。「タスク一覧」で確認してから「〇〇を削除して」と指定してください。"

    async def _handle_task_priority(self) -> str:
        """優先タスクを提案"""
        tasks = task_service.get_pending_tasks()
        if not tasks:
            return "未完了のタスクはありません。素晴らしいですね！"

        # 上位3件を提案
        top_tasks = tasks[:3]
        lines = ["次に取り組むべきタスクの提案です：\n"]
        for i, task in enumerate(top_tasks, 1):
            due = ""
            if task.due_date:
                due = f"（期限: {task.due_date.strftime('%m/%d')}）"
            lines.append(f"{i}. {task.title}{due}")

        return "\n".join(lines)

    async def _handle_briefing(self) -> str:
        """ブリーフィング（予定+タスクのまとめ）"""
        lines = []

        # 予定
        events = await calendar_service.get_today_events()
        if events:
            formatted = calendar_service.format_events_for_display(events)
            lines.append(f"📅 今日の予定（{len(events)}件）")
            lines.append(formatted)
        else:
            lines.append("📅 今日の予定はありません。")

        lines.append("")

        # タスク
        today_tasks = task_service.get_today_due_tasks()
        if today_tasks:
            lines.append(f"✅ 今日期限のタスク（{len(today_tasks)}件）")
            for task in today_tasks:
                priority_mark = "【緊急】" if task.priority <= 2 else ""
                lines.append(f"• {task.title}{priority_mark}")
        else:
            lines.append("✅ 今日期限のタスクはありません。")

        lines.append("")

        # 未完了タスク数
        all_pending = task_service.get_pending_tasks()
        if all_pending:
            lines.append(f"📋 未完了タスク合計: {len(all_pending)}件")

        return "\n".join(lines)

    # --- パーソナライズ ---

    async def _handle_preference(self, user_message: str) -> str:
        """設定変更・記憶"""
        # 「覚えて：〇〇」パターン
        memo_match = re.search(r"覚えて[：:]?\s*(.+)", user_message)
        if memo_match:
            content = memo_match.group(1).strip()
            # key=value形式かチェック
            if "=" in content or "は" in content:
                parts = re.split(r"[=は]", content, maxsplit=1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip()
                    preference_service.set_preference(key, value)
                    return f"📝 覚えました：{key} = {value}"
            # フリーテキストならメモとして保存
            preference_service.set_preference(f"memo_{datetime.now().strftime('%Y%m%d%H%M')}", content)
            return f"📝 覚えました：{content}"

        # 「設定一覧」「覚えていること」
        if any(w in user_message for w in ["設定一覧", "覚えていること", "記憶", "設定確認"]):
            return preference_service.format_preferences_for_display()

        # 「忘れて：〇〇」
        forget_match = re.search(r"忘れて[：:]?\s*(.+)", user_message)
        if forget_match:
            key = forget_match.group(1).strip()
            if preference_service.delete_preference(key):
                return f"🗑️ 「{key}」の設定を削除しました。"
            return f"「{key}」という設定は見つかりませんでした。"

        return "設定を保存するには「覚えて：〇〇」、確認するには「設定一覧」と送ってください。"

    # --- 汎用会話 ---

    async def _handle_general(self, user_message: str, _intent: str) -> str:
        """汎用LLM会話で応答を生成（会話履歴付き）"""
        context = memory_service.format_context_for_prompt()

        if context:
            prompt = f"{context}\n\nユーザー: {user_message}"
        else:
            prompt = user_message

        if await llm_service._is_ollama_available():
            return await llm_service.generate(
                prompt=prompt,
                system_prompt=SYSTEM_PROMPT,
            )

        filtered_prompt = pii_filter.redact(prompt)
        filtered_response = await llm_service.generate(
            prompt=filtered_prompt,
            system_prompt=SYSTEM_PROMPT,
        )
        response: str = pii_filter.restore(filtered_response)
        return response


# シングルトンインスタンス
secretary = Secretary()
