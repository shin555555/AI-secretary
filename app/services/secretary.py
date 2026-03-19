import re
import logging
from datetime import datetime

from app.prompts.intent_classifier import INTENT_CLASSIFICATION_PROMPT, VALID_INTENTS
from app.prompts.system_prompt import SYSTEM_PROMPT
from app.services.calendar_service import calendar_service
from app.services.datetime_parser import parse_schedule_from_message
from app.services.gmail_service import gmail_service
from app.services.llm_service import llm_service
from app.services.mail_filter_service import mail_filter_service
from app.services.memory_service import memory_service
from app.services.pii_filter import pii_filter
from app.services.preference_service import preference_service
from app.services.task_parser import parse_task_from_message
from app.services.task_service import task_service

logger = logging.getLogger(__name__)


class Secretary:
    """凛のコアオーケストレータ: インテント分類 → サービスルーティング → 応答生成"""

    def __init__(self) -> None:
        self._pending_action: dict | None = None

    async def handle_message(self, user_message: str) -> str:
        """ユーザーメッセージを処理して応答を生成"""
        # メール下書き/送信の確認応答を処理
        if self._pending_action:
            confirmation_result = await self._handle_confirmation(user_message)
            if confirmation_result:
                return confirmation_result

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
            "mail_check": lambda: self._handle_mail_check(),
            "mail_detail": lambda: self._handle_mail_detail(user_message),
            "mail_draft": lambda: self._handle_mail_draft(user_message),
            "mail_reply": lambda: self._handle_mail_reply(user_message),
            "mail_drafts": lambda: self._handle_mail_drafts(),
            "mail_send": lambda: self._handle_mail_send(user_message),
            "help": lambda: self._handle_help(),
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
        """週間予定を取得して返答（今日から/今週/来週）"""
        if any(w in user_message for w in ["来週", "next week"]):
            events = await calendar_service.get_week_events(weeks_offset=1)
            label = "来週"
        elif any(w in user_message for w in ["今日から", "これから", "向こう", "今後"]):
            events = await calendar_service.get_upcoming_events(days=7)
            label = "今日から1週間"
        else:
            events = await calendar_service.get_upcoming_events(days=7)
            label = "今日から1週間"

        if events is None:
            return "申し訳ございません、カレンダーへの接続に失敗しました。"

        formatted = calendar_service.format_events_for_display(events, show_date=True)
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

        lines.append("")

        # メール
        try:
            messages = await gmail_service.get_important_messages()
            if messages:
                lines.append(gmail_service.format_for_briefing(messages))
            else:
                lines.append("📧 未読の重要メールはありません。")
        except Exception as e:
            logger.warning(f"ブリーフィングのメール取得失敗: {e}")
            lines.append("📧 メールの取得に失敗しました。")

        return "\n".join(lines)

    # --- メール ---

    async def _handle_mail_check(self) -> str:
        """重要メール一覧を表示"""
        messages = await gmail_service.get_important_messages()
        if messages is None:
            return "申し訳ございません、Gmailへの接続に失敗しました。Google認証にGmail権限が含まれているか確認してください。"

        if not messages:
            return "📧 未読の重要メールはありません。"

        # LLMでトリアージ（件名・差出人・snippetのみ渡す）
        triage_results = await self._triage_messages(messages)

        # トリアージ結果をメッセージに付与
        for i, msg in enumerate(messages):
            if i < len(triage_results):
                msg["triage_summary"] = triage_results[i].get("summary", msg.get("snippet", "")[:60])

        return gmail_service.format_mail_list(messages, triage_results)

    async def _handle_mail_detail(self, user_message: str) -> str:
        """メールの詳細（本文要約）を表示"""
        num = self._extract_number(user_message)
        if not num:
            return "メール番号を指定してください。例：「メール1の詳細」"

        msg = gmail_service.get_cached_message(num)
        if not msg:
            return f"メール{num}が見つかりません。まず「メール確認」で一覧を表示してください。"

        body = await gmail_service.get_message_body(msg["id"])
        if not body:
            return f"メール{num}の本文を取得できませんでした。"

        # LLMで要約（Ollamaローカル優先）
        summary_prompt = f"以下のメール本文を3行以内で要約してください。\n\n差出人: {msg['from_name']}\n件名: {msg['subject']}\n\n{body[:800]}"

        if await llm_service._is_ollama_available():
            summary = await llm_service.generate(prompt=summary_prompt, temperature=0.3)
        else:
            filtered = pii_filter.redact(summary_prompt)
            summary = await llm_service.generate(prompt=filtered, temperature=0.3)
            summary = pii_filter.restore(summary)

        from_display = msg["from_name"] or msg["from_email"]
        return f"📧 メール{num}の詳細\n\n差出人: {from_display}\n件名: {msg['subject']}\n時刻: {msg['time']}\n\n📝 要約:\n{summary}"

    async def _handle_mail_draft(self, user_message: str) -> str:
        """メールの返信下書きを作成"""
        num = self._extract_number(user_message)
        if not num:
            return "メール番号を指定してください。例：「メール1に下書き。〇〇と伝えて」"

        msg = gmail_service.get_cached_message(num)
        if not msg:
            return f"メール{num}が見つかりません。まず「メール確認」で一覧を表示してください。"

        # ユーザーの指示を抽出
        instruction = re.sub(r"メール\s*\d+\s*に?\s*下書き[。、]?\s*", "", user_message).strip()
        if not instruction:
            instruction = "適切な返信"

        # 返信文を生成
        reply_body = await self._generate_reply(msg, instruction)

        # 保留状態として会話コンテキストに保存
        self._pending_action = {
            "type": "draft",
            "msg": msg,
            "reply_body": reply_body,
            "subject": f"Re: {msg['subject']}",
        }

        return f"以下の内容で下書き作成します。よろしいですか？\n\n---\n{reply_body}\n---\n\n「OK」で下書き保存、「修正して：〇〇」で書き直します。"

    async def _handle_mail_reply(self, user_message: str) -> str:
        """メールに返信して送信"""
        num = self._extract_number(user_message)
        if not num:
            return "メール番号を指定してください。例：「メール1に返信して。〇〇と伝えて」"

        msg = gmail_service.get_cached_message(num)
        if not msg:
            return f"メール{num}が見つかりません。まず「メール確認」で一覧を表示してください。"

        # ユーザーの指示を抽出
        instruction = re.sub(r"メール\s*\d+\s*に?\s*返信(して)?[。、]?\s*", "", user_message).strip()
        if not instruction:
            instruction = "適切な返信"

        # 返信文を生成
        reply_body = await self._generate_reply(msg, instruction)

        # 保留状態として保存
        self._pending_action = {
            "type": "send",
            "msg": msg,
            "reply_body": reply_body,
            "subject": f"Re: {msg['subject']}",
        }

        return f"以下の内容で返信します。よろしいですか？\n\n---\n{reply_body}\n---\n\n「送信」で送信、「修正して：〇〇」で書き直します。"

    async def _handle_mail_drafts(self) -> str:
        """下書き一覧を表示"""
        drafts = await gmail_service.get_drafts()
        if drafts is None:
            return "申し訳ございません、下書きの取得に失敗しました。"
        return gmail_service.format_draft_list(drafts)

    async def _handle_mail_send(self, user_message: str) -> str:
        """下書きを送信"""
        num = self._extract_number(user_message)
        if not num:
            return "下書き番号を指定してください。例：「下書き1を送信して」"

        drafts = await gmail_service.get_drafts()
        if not drafts or num > len(drafts):
            return f"下書き{num}が見つかりません。「下書き一覧」で確認してください。"

        draft = drafts[num - 1]
        result = await gmail_service.send_draft(draft["draft_id"])
        if result:
            return f"✅ {draft['to']}への返信を送信しました。"
        return "申し訳ございません、送信に失敗しました。"

    async def _triage_messages(self, messages: list[dict]) -> list[dict]:
        """LLMでメールをトリアージ（件名・差出人・snippetのみ）"""
        mail_list = "\n".join(
            f"{i+1}. 差出人: {m['from_name']} <{m['from_email']}> | 件名: {m['subject']} | 冒頭: {m.get('snippet', '')[:80]}"
            for i, m in enumerate(messages)
        )

        prompt = f"""以下のメール一覧を分類してください。各メールについて以下の形式で1行ずつ返してください:
番号|レベル|要約

レベルは以下の3つから選択:
- reply: 相手が返事を待っている（要返信）
- check: 読んでおくべき（要確認、返信不要）
- skip: 対応不要

要約は20文字以内で内容を簡潔に。

メール一覧:
{mail_list}"""

        try:
            if await llm_service._is_ollama_available():
                result = await llm_service.generate(prompt=prompt, temperature=0.2)
            else:
                filtered = pii_filter.redact(prompt)
                result = await llm_service.generate(prompt=filtered, temperature=0.2)
                result = pii_filter.restore(result)

            # パース
            triage = []
            for line in result.strip().split("\n"):
                parts = line.split("|")
                if len(parts) >= 3:
                    level = parts[1].strip().lower()
                    if level not in ("reply", "check", "skip"):
                        level = "check"
                    triage.append({
                        "level": level,
                        "summary": parts[2].strip(),
                    })
                else:
                    triage.append({"level": "check", "summary": ""})

            return triage
        except Exception as e:
            logger.warning(f"トリアージ失敗: {e}")
            return [{"level": "check", "summary": ""} for _ in messages]

    async def _generate_reply(self, msg: dict, instruction: str) -> str:
        """LLMで返信文を生成"""
        body = await gmail_service.get_message_body(msg["id"], max_chars=500)
        body_text = body[:300] if body else msg.get("snippet", "")

        prompt = f"""以下のメールに対する返信文を作成してください。

差出人: {msg['from_name']}
件名: {msg['subject']}
本文（冒頭）: {body_text}

ユーザーの指示: {instruction}

【ルール】
- ビジネスメールとして適切な丁寧語で書く
- 宛名（〇〇様）と締めの挨拶を含める
- 簡潔にまとめる（5行以内）
- 署名は不要
- 返信文のみを出力（説明不要）"""

        if await llm_service._is_ollama_available():
            return await llm_service.generate(prompt=prompt, temperature=0.5)
        else:
            filtered = pii_filter.redact(prompt)
            result = await llm_service.generate(prompt=filtered, temperature=0.5)
            return pii_filter.restore(result)

    async def _handle_confirmation(self, user_message: str) -> str | None:
        """メール下書き/送信の確認応答を処理"""
        action = self._pending_action
        if not action:
            return None

        msg_lower = user_message.strip().lower()
        msg_text = user_message.strip()

        # 「OK」→ 下書き保存
        if action["type"] == "draft" and msg_lower in ("ok", "ＯＫ", "はい", "おk", "オッケー", "おけ"):
            self._pending_action = None
            result = await gmail_service.create_draft(
                to=action["msg"]["from_email"],
                subject=action["subject"],
                body=action["reply_body"],
                thread_id=action["msg"].get("thread_id"),
                in_reply_to=action["msg"].get("message_id_header"),
            )
            if result:
                memory_service.save_message(role="assistant", content="📝 下書きをGmailに保存しました。")
                return "📝 下書きをGmailに保存しました。"
            return "申し訳ございません、下書きの保存に失敗しました。"

        # 「送信」→ 直接送信
        if action["type"] == "send" and msg_lower in ("送信", "送って", "はい", "ok", "ＯＫ"):
            self._pending_action = None
            result = await gmail_service.send_reply(
                to=action["msg"]["from_email"],
                subject=action["subject"],
                body=action["reply_body"],
                thread_id=action["msg"].get("thread_id"),
                in_reply_to=action["msg"].get("message_id_header"),
            )
            if result:
                memory_service.save_message(role="assistant", content="✅ 返信を送信しました。")
                return "✅ 返信を送信しました。"
            return "申し訳ございません、送信に失敗しました。"

        # 「修正して：〇〇」→ 書き直し
        modify_match = re.search(r"修正(して)?[：:]?\s*(.+)", msg_text)
        if modify_match:
            new_instruction = modify_match.group(2).strip()
            reply_body = await self._generate_reply(action["msg"], new_instruction)
            action["reply_body"] = reply_body

            if action["type"] == "draft":
                return f"修正しました。以下の内容で下書き作成します。よろしいですか？\n\n---\n{reply_body}\n---\n\n「OK」で下書き保存、「修正して：〇〇」で書き直します。"
            else:
                return f"修正しました。以下の内容で返信します。よろしいですか？\n\n---\n{reply_body}\n---\n\n「送信」で送信、「修正して：〇〇」で書き直します。"

        # 「キャンセル」「やめる」→ 取り消し
        if msg_lower in ("キャンセル", "やめる", "やめて", "取り消し", "cancel"):
            self._pending_action = None
            return "操作をキャンセルしました。"

        # 確認応答として認識できなかった → pending を維持しつつ None を返す（通常のインテント分類へ）
        self._pending_action = None
        return None

    def _extract_number(self, text: str) -> int | None:
        """テキストから数字を抽出"""
        match = re.search(r"(\d+)", text)
        return int(match.group(1)) if match else None

    async def _handle_help(self) -> str:
        """凛にできることを表示"""
        return """📖 凛にできること

📅 スケジュール
• 「今日の予定」— 今日の予定を確認
• 「今週の予定」— 今日から1週間の予定を確認
• 「予定を追加したい」— カレンダーに予定を登録

📋 タスク管理
• 「タスク一覧」— 未完了タスクを表示
• 「タスク追加：〇〇 金曜まで」— タスクを登録
• 「タスク1完了」— タスクを完了にする
• 「〇〇を削除して」— タスクを削除

📧 メール
• 「メール確認」— 重要な未読メールを表示
• 「メール1の詳細」— メールの本文要約を表示
• 「メール1に下書き。〇〇と伝えて」— 返信の下書きを作成
• 「メール1に返信して。〇〇と伝えて」— 返信を送信
• 「下書き一覧」— 保存した下書きを確認
• 「下書き1を送信して」— 下書きを送信

⚙️ その他
• 「ブリーフィング」— 予定+タスク+メールのまとめ
• 「覚えて：〇〇」— 設定や情報を記憶
• 「設定一覧」— 覚えている情報を確認

何でもお気軽に話しかけてくださいね。"""

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
