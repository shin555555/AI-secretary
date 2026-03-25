import json
import re
import logging
from datetime import datetime, timedelta

from app.prompts.intent_classifier import INTENT_CLASSIFICATION_PROMPT, VALID_INTENTS
from app.prompts.system_prompt import SYSTEM_PROMPT
from app.services.calendar_service import calendar_service
from app.services.datetime_parser import parse_schedule_from_message, _resolve_date
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
        self._pending_slots: list[dict] = []
        self._pending_slot_purpose: str | None = None
        self._pending_slot_duration: int = 60
        self._last_slot_skip: int = 0

    async def handle_message(self, user_message: str) -> str:
        """ユーザーメッセージを処理して応答を生成"""
        # メール下書き/送信の確認応答を処理
        if self._pending_action:
            confirmation_result = await self._handle_confirmation(user_message)
            if confirmation_result:
                return confirmation_result

        # 空き時間候補からの選択を処理（「1番で予定入れて」等）
        if hasattr(self, "_pending_slots") and self._pending_slots:
            slot_result = await self._handle_slot_selection(user_message)
            if slot_result:
                return slot_result

        # キーワードベースの事前分類（LLMの誤分類を防止）
        pre_intent = self._pre_classify_intent(user_message)
        if pre_intent:
            intent = pre_intent
            logger.info(f"インテント（事前分類）: {intent}")
        else:
            intent = await self._classify_intent(user_message)
            logger.info(f"インテント: {intent}")

        memory_service.save_message(role="user", content=user_message, intent=intent)

        # インテントに応じたルーティング
        handler_map = {
            "schedule_check": lambda: self._handle_schedule_check(user_message),
            "schedule_week": lambda: self._handle_schedule_week(user_message),
            "schedule_create": lambda: self._handle_schedule_create(user_message),
            "schedule_search": lambda: self._handle_schedule_search(user_message),
            "schedule_update": lambda: self._handle_schedule_update(user_message),
            "schedule_delete": lambda: self._handle_schedule_delete(user_message),
            "schedule_find_slot": lambda: self._handle_schedule_find_slot(user_message),
            "task_add": lambda: self._handle_task_add(user_message),
            "task_recurring": lambda: self._handle_task_recurring(user_message),
            "task_list": lambda: self._handle_task_list(user_message),
            "task_done": lambda: self._handle_task_done(user_message),
            "task_delete": lambda: self._handle_task_delete(user_message),
            "task_priority": lambda: self._handle_task_priority(user_message),
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

    def _pre_classify_intent(self, user_message: str) -> str | None:
        """キーワードベースの事前分類（LLM誤分類を防止）"""
        msg = user_message.strip()

        # 予定の変更パターン
        if re.search(r"(予定|スケジュール|会議|面談|打ち合わせ|ミーティング).*(変更|ずらし|移動|リスケ)", msg):
            return "schedule_update"
        if re.search(r"(変更|ずらし|移動|リスケ).*(予定|スケジュール|会議|面談|打ち合わせ|ミーティング)", msg):
            return "schedule_update"
        # 「〇〇を△時に変更して」パターン（時刻変更）
        if re.search(r".+を\d{1,2}時.*に?(変更|ずらし|移動)", msg):
            return "schedule_update"
        if "予定を変更" in msg or "予定変更" in msg or "スケジュール変更" in msg:
            return "schedule_update"

        # 予定の削除パターン（「タスク」を含まない場合）
        if "タスク" not in msg:
            if re.search(r"(予定|スケジュール|会議|面談|打ち合わせ|ミーティング).*(削除|キャンセル|取り消|消して|なくし)", msg):
                return "schedule_delete"
            if re.search(r"(削除|キャンセル|取り消).*(予定|スケジュール|会議|面談|打ち合わせ|ミーティング)", msg):
                return "schedule_delete"
            # 「面談を削除して」のように予定名+削除
            if re.search(r".+を(削除|キャンセル)", msg) and not re.search(r"タスク|メール|下書き", msg):
                return "schedule_delete"

        return None

    async def _classify_intent(self, user_message: str) -> str:
        """LLMでインテント分類"""
        prompt = INTENT_CLASSIFICATION_PROMPT.format(user_message=user_message)
        raw_intent = await llm_service.generate(prompt=prompt, temperature=0.1)

        intent = raw_intent.strip().lower()

        # 完全一致を優先
        if intent in VALID_INTENTS:
            return intent

        # 部分一致フォールバック（長い名前を先にチェック）
        for valid in sorted(VALID_INTENTS, key=len, reverse=True):
            if valid in intent:
                return valid

        logger.warning(f"不明なインテント: {raw_intent} → generalにフォールバック")
        return "general"

    # --- カレンダー ---

    async def _handle_schedule_check(self, user_message: str) -> str:
        """特定の日または月の予定を取得して返答"""
        now = datetime.now()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # 月単位のパターンを先にチェック
        month_range = self._detect_month_range(user_message, now)
        if month_range:
            start, end, label = month_range
            events = await calendar_service._get_events_between(start, end)
            if events is None:
                return "申し訳ございません、カレンダーへの接続に失敗しました。"
            formatted = calendar_service.format_events_for_display(events, show_date=True)
            if formatted == "予定はありません。":
                return f"{label}の予定はございません。"
            count = len(events)
            return f"{label}の予定です（{count}件）：\n\n{formatted}"

        # 日単位のパターン
        target_date = _resolve_date(user_message)
        if target_date is None:
            target_date = today

        days_offset = (target_date.date() - today.date()).days

        # 日付ラベルを生成
        weekday_names = ["月", "火", "水", "木", "金", "土", "日"]
        if days_offset == 0:
            label = "本日"
        elif days_offset == 1:
            label = "明日"
        elif days_offset == 2:
            label = "明後日"
        elif days_offset == -1:
            label = "昨日"
        else:
            wd = weekday_names[target_date.weekday()]
            label = f"{target_date.month}/{target_date.day}({wd})"

        events = await calendar_service._get_events_for_range(days=days_offset)
        if events is None:
            return "申し訳ございません、カレンダーへの接続に失敗しました。Google認証が完了しているか確認してください。"

        formatted = calendar_service.format_events_for_display(events)
        if formatted == "予定はありません。":
            return f"{label}の予定はございません。"

        return f"{label}の予定です：\n\n{formatted}"

    def _detect_month_range(
        self, message: str, now: datetime
    ) -> tuple[datetime, datetime, str] | None:
        """メッセージから月単位の日付範囲を検出"""
        year = now.year
        month = now.month

        if "来月" in message:
            if month == 12:
                start = datetime(year + 1, 1, 1)
            else:
                start = datetime(year, month + 1, 1)
            label = f"来月（{start.month}月）"
        elif "先月" in message:
            if month == 1:
                start = datetime(year - 1, 12, 1)
            else:
                start = datetime(year, month - 1, 1)
            label = f"先月（{start.month}月）"
        elif "今月" in message:
            start = datetime(year, month, 1)
            label = f"今月（{month}月）"
        else:
            return None

        # 月末日を算出
        if start.month == 12:
            end = datetime(start.year + 1, 1, 1)
        else:
            end = datetime(start.year, start.month + 1, 1)

        return start, end, label

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
        # リッチメニューからの短い入力は聞き返す
        short_phrases = ["予定を追加", "予定を追加したい", "予定追加", "予定の追加", "予定を登録", "予定登録"]
        if user_message.strip() in short_phrases:
            return "予定の登録ですね。どのような予定を追加しますか？\n（例：「明日14時から1時間、田中さんと面談」「毎週月曜10時に朝礼」）"

        parsed = await parse_schedule_from_message(user_message)
        if not parsed:
            return "予定の内容を読み取れませんでした。もう少し詳しく教えていただけますか？\n例：「明日14時から1時間、田中さんと面談」"

        title = parsed.get("title", "無題")
        start = parsed.get("start_datetime")
        end = parsed.get("end_datetime")
        rrule = parsed.get("rrule")

        if not start:
            return "日時の指定が見当たりません。いつの予定か教えていただけますか？\n例：「3月20日15時から打ち合わせ」"

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

    async def _handle_schedule_search(self, user_message: str) -> str:
        """キーワードで予定を検索"""
        # LLMでキーワードを抽出
        extract_prompt = f"ユーザーのメッセージから、検索したい予定のキーワード（人名や会議名など）だけを抽出して単語で返してください。説明不要、キーワードのみ。\nメッセージ：{user_message}"
        keyword = await llm_service.generate(prompt=extract_prompt, temperature=0.1)
        keyword = keyword.strip().strip("「」『』\"'")

        if not keyword:
            return "検索キーワードを読み取れませんでした。何の予定を探していますか？"

        events = await calendar_service.search_events(keyword)

        if not events:
            # カレンダーに見つからない場合、保存済み設定も確認
            prefs = preference_service.get_all_preferences()
            matching = {k: v for k, v in prefs.items() if keyword in k or keyword in v}
            if matching:
                lines = [f"カレンダーに「{keyword}」の予定はありませんが、保存済みの情報がございます：\n"]
                for k, v in matching.items():
                    lines.append(f"📝 {k}: {v}")
                return "\n".join(lines)
            # 設定にも見つからない場合、汎用会話で回答を試みる
            return await self._handle_general(user_message, "schedule_search")

        formatted = calendar_service.format_events_for_display(events, show_date=True)
        return f"「{keyword}」に関する予定です：\n\n{formatted}"

    async def _handle_schedule_update(self, user_message: str) -> str:
        """予定を変更する（検索→候補表示→確認→更新）"""
        short_phrases = ["予定を変更", "予定変更", "予定を変更したい", "スケジュール変更"]
        if user_message.strip() in short_phrases:
            return "どの予定をどのように変更しますか？\n（例：「明日の会議を15時に変更して」「田中さん面談を来週月曜に変更」）"

        # LLMで変更対象と変更内容を抽出
        extract_prompt = f"""ユーザーのメッセージから予定の変更情報を抽出してJSON形式で返してください。

- search_keyword: 変更対象の予定キーワード（「会議」「面談」「田中さん」等）
- new_date_raw: 変更後の日付表現（「明日」「来週月曜」等。変更なしならnull）
- new_time_raw: 変更後の時刻表現（「15時」「14:00」等。変更なしならnull）
- new_title: 変更後のタイトル（変更なしならnull）

JSONのみ返してください。
メッセージ：{user_message}"""

        if await llm_service._is_ollama_available():
            raw = await llm_service.generate(prompt=extract_prompt, temperature=0.1)
        else:
            filtered = pii_filter.redact(extract_prompt)
            raw = await llm_service.generate(prompt=filtered, temperature=0.1)
            raw = pii_filter.restore(raw)

        try:
            clean = raw.strip()
            if "```" in clean:
                clean = clean.split("```")[1]
                if clean.startswith("json"):
                    clean = clean[4:]
            parsed = json.loads(clean.strip())
        except (json.JSONDecodeError, IndexError):
            return "変更内容を読み取れませんでした。\n例：「会議を15時に変更して」「田中さん面談を明日に変更」"

        keyword = parsed.get("search_keyword", "")
        if not keyword:
            return "どの予定を変更するか分かりませんでした。予定のタイトルや相手の名前を含めてください。"

        # カレンダーから検索
        events = await calendar_service.search_events(keyword)
        if not events:
            return f"「{keyword}」に一致する予定が見つかりませんでした。"

        # 未来の予定のみに絞る
        now = datetime.now()
        future_events = []
        for e in events:
            try:
                start_str = e["start"]
                start_dt = datetime.fromisoformat(start_str)
                if start_dt.tzinfo is not None:
                    start_dt = start_dt.replace(tzinfo=None)
                if start_dt >= now:
                    future_events.append(e)
            except (ValueError, KeyError):
                future_events.append(e)

        if not future_events:
            return f"「{keyword}」に一致する今後の予定が見つかりませんでした。"

        # 候補が1件なら直接変更、複数なら選択を求める
        if len(future_events) == 1:
            target = future_events[0]
        else:
            # 保留状態に保存して選択を求める
            self._pending_action = {
                "type": "schedule_update",
                "events": future_events,
                "parsed": parsed,
            }
            lines = [f"「{keyword}」に一致する予定が{len(future_events)}件あります。どれを変更しますか？\n"]
            weekday_names = ["月", "火", "水", "木", "金", "土", "日"]
            for i, e in enumerate(future_events[:5], 1):
                try:
                    dt = datetime.fromisoformat(e["start"])
                    if dt.tzinfo is not None:
                        dt = dt.replace(tzinfo=None)
                    wd = weekday_names[dt.weekday()]
                    lines.append(f"  {i}. {dt.month}/{dt.day}({wd}) {dt.strftime('%H:%M')} {e['title']}")
                except (ValueError, KeyError):
                    lines.append(f"  {i}. {e['title']}")
            lines.append("\n番号で選んでください。（例：「1」）")
            return "\n".join(lines)

        # 変更を実行
        return await self._execute_schedule_update(target, parsed)

    async def _execute_schedule_update(self, target: dict, parsed: dict) -> str:
        """予定の変更を実行"""
        from app.services.datetime_parser import _resolve_date, _resolve_time

        new_start = None
        new_end = None

        new_date = _resolve_date(parsed.get("new_date_raw"))
        new_time = _resolve_time(parsed.get("new_time_raw"))

        # 元の開始時刻を取得
        try:
            orig_start = datetime.fromisoformat(target["start"])
            if orig_start.tzinfo is not None:
                orig_start = orig_start.replace(tzinfo=None)
            orig_end = datetime.fromisoformat(target["end"])
            if orig_end.tzinfo is not None:
                orig_end = orig_end.replace(tzinfo=None)
            duration = orig_end - orig_start
        except (ValueError, KeyError):
            duration = timedelta(hours=1)
            orig_start = datetime.now()

        if new_date and new_time:
            new_start = new_date.replace(hour=new_time[0], minute=new_time[1])
        elif new_date:
            new_start = new_date.replace(hour=orig_start.hour, minute=orig_start.minute)
        elif new_time:
            new_start = orig_start.replace(hour=new_time[0], minute=new_time[1])

        if new_start:
            new_end = new_start + duration

        new_title = parsed.get("new_title")

        if not new_start and not new_title:
            return "変更内容が指定されていません。日時やタイトルの変更内容を教えてください。"

        result = await calendar_service.update_event(
            event_id=target["id"],
            title=new_title,
            start_datetime=new_start,
            end_datetime=new_end,
        )

        if result is None:
            return "申し訳ございません、予定の変更に失敗しました。"

        weekday_names = ["月", "火", "水", "木", "金", "土", "日"]
        changes = []
        if new_title:
            changes.append(f"📝 タイトル: {new_title}")
        if new_start:
            wd = weekday_names[new_start.weekday()]
            changes.append(f"⏰ 日時: {new_start.month}/{new_start.day}({wd}) {new_start.strftime('%H:%M')}〜{new_end.strftime('%H:%M')}")

        return f"✅ 予定を変更しました。\n\n📅 {result.get('title', target['title'])}\n" + "\n".join(changes)

    async def _handle_schedule_delete(self, user_message: str) -> str:
        """予定を削除する（検索→候補表示→確認→削除）"""
        short_phrases = ["予定を削除", "予定削除", "予定をキャンセル", "予定を消して"]
        if user_message.strip() in short_phrases:
            return "どの予定を削除しますか？\n（例：「明日の会議を削除して」「田中さん面談をキャンセル」）"

        # LLMでキーワード抽出
        extract_prompt = f"ユーザーのメッセージから、削除したい予定のキーワード（人名や会議名など）だけを抽出して単語で返してください。説明不要、キーワードのみ。\nメッセージ：{user_message}"
        keyword = await llm_service.generate(prompt=extract_prompt, temperature=0.1)
        keyword = keyword.strip().strip("「」『』\"'")

        if not keyword:
            return "どの予定を削除するか分かりませんでした。予定のタイトルや相手の名前を含めてください。"

        events = await calendar_service.search_events(keyword)
        if not events:
            return f"「{keyword}」に一致する予定が見つかりませんでした。"

        # 未来の予定のみ
        now = datetime.now()
        future_events = []
        for e in events:
            try:
                start_dt = datetime.fromisoformat(e["start"])
                if start_dt.tzinfo is not None:
                    start_dt = start_dt.replace(tzinfo=None)
                if start_dt >= now:
                    future_events.append(e)
            except (ValueError, KeyError):
                future_events.append(e)

        if not future_events:
            return f"「{keyword}」に一致する今後の予定が見つかりませんでした。"

        # 候補が1件なら確認、複数なら選択
        if len(future_events) == 1:
            target = future_events[0]
            self._pending_action = {
                "type": "schedule_delete_confirm",
                "event": target,
            }
            weekday_names = ["月", "火", "水", "木", "金", "土", "日"]
            try:
                dt = datetime.fromisoformat(target["start"])
                if dt.tzinfo is not None:
                    dt = dt.replace(tzinfo=None)
                wd = weekday_names[dt.weekday()]
                time_str = f"{dt.month}/{dt.day}({wd}) {dt.strftime('%H:%M')}"
            except (ValueError, KeyError):
                time_str = ""
            return f"以下の予定を削除してよろしいですか？\n\n📅 {target['title']}\n⏰ {time_str}\n\n「はい」で削除します。"
        else:
            self._pending_action = {
                "type": "schedule_delete_select",
                "events": future_events,
            }
            lines = [f"「{keyword}」に一致する予定が{len(future_events)}件あります。どれを削除しますか？\n"]
            weekday_names = ["月", "火", "水", "木", "金", "土", "日"]
            for i, e in enumerate(future_events[:5], 1):
                try:
                    dt = datetime.fromisoformat(e["start"])
                    if dt.tzinfo is not None:
                        dt = dt.replace(tzinfo=None)
                    wd = weekday_names[dt.weekday()]
                    lines.append(f"  {i}. {dt.month}/{dt.day}({wd}) {dt.strftime('%H:%M')} {e['title']}")
                except (ValueError, KeyError):
                    lines.append(f"  {i}. {e['title']}")
            lines.append("\n番号で選んでください。（例：「1」）")
            return "\n".join(lines)

    async def _handle_schedule_find_slot(self, user_message: str) -> str:
        """空き時間を検索して提案"""
        # LLMで目的（打ち合わせ相手・内容）と希望時間を抽出
        extract_prompt = f"""ユーザーのメッセージから以下をJSON形式で抽出してください。
- purpose: 目的や相手（「Bさんと打ち合わせ」等。不明なら null）
- duration_minutes: 希望時間（分）。不明なら60
- is_alternative: 「他の日時」「別の候補」など既に提示した候補以外を求めているか（true/false）

JSONのみ返してください。
メッセージ：{user_message}"""

        if await llm_service._is_ollama_available():
            raw = await llm_service.generate(prompt=extract_prompt, temperature=0.1)
        else:
            filtered_prompt = pii_filter.redact(extract_prompt)
            raw = await llm_service.generate(prompt=filtered_prompt, temperature=0.1)
            raw = pii_filter.restore(raw)

        purpose = None
        duration = 60
        is_alt = False
        try:
            clean = raw.strip()
            if "```" in clean:
                clean = clean.split("```")[1]
                if clean.startswith("json"):
                    clean = clean[4:]
            parsed = json.loads(clean.strip())
            purpose = parsed.get("purpose")
            duration = parsed.get("duration_minutes", 60) or 60
            is_alt = parsed.get("is_alternative", False)
        except (json.JSONDecodeError, IndexError, AttributeError):
            pass

        # 「他の日時は？」の場合、前回のスキップ数を加算
        skip = 0
        if is_alt and self._last_slot_skip:
            skip = self._last_slot_skip

        slots = await calendar_service.find_available_slots(
            days=10, duration_minutes=duration, skip_count=skip,
        )

        if not slots:
            return "申し訳ございません、今後10日間で条件に合う空き時間が見つかりませんでした。"

        # 最大5件提案
        display_slots = slots[:5]
        self._last_slot_skip = skip + len(display_slots)

        purpose_text = f"「{purpose}」" if purpose else "予定"
        lines = [f"📅 {purpose_text}の候補日時です（{duration}分）：\n"]

        for i, slot in enumerate(display_slots, 1):
            lines.append(
                f"  {i}. {slot['date']} {slot['start']}〜{slot['end']}"
                f"（{slot['minutes']}分空き）"
            )

        lines.append("\n「1番で予定入れて」で登録できます。")
        lines.append("「他の日時は？」で別の候補も出せます。")

        # 選択用に候補を保持
        self._pending_slots = display_slots
        self._pending_slot_purpose = purpose
        self._pending_slot_duration = duration

        return "\n".join(lines)

    async def _handle_slot_selection(self, user_message: str) -> str | None:
        """空き時間候補からの選択を処理"""
        msg = user_message.strip()

        # 「他の日時は？」「別の候補」→ schedule_find_slotに流す（インテント分類に任せる）
        alt_keywords = ["他の", "別の", "それ以外", "他は", "ほかの", "ほかは"]
        if any(k in msg for k in alt_keywords):
            self._pending_slots = []
            return None  # インテント分類に委ねる

        # 「1番」「2で」等の番号選択を検出
        num_match = re.search(r"(\d+)\s*(?:番|で|に|を)", msg)
        if not num_match:
            # 候補選択でなさそう → pending維持せずインテント分類へ
            self._pending_slots = []
            return None

        idx = int(num_match.group(1)) - 1
        slots = self._pending_slots
        if idx < 0 or idx >= len(slots):
            return f"1〜{len(slots)}の番号で選んでください。"

        selected = slots[idx]
        purpose = getattr(self, "_pending_slot_purpose", None) or "予定"
        self._pending_slots = []

        # カレンダーに登録（ユーザーが指定した希望時間で）
        duration = getattr(self, "_pending_slot_duration", 60)
        start_dt = selected["start_dt"]
        end_dt = start_dt + timedelta(minutes=duration)

        result = await calendar_service.create_event(
            title=purpose, start_datetime=start_dt, end_datetime=end_dt,
        )

        if result is None:
            return "申し訳ございません、予定の登録に失敗しました。"

        if result.get("conflict"):
            return f"⚠️ 時間が重複しています：{result['conflict']}"

        weekday_names = ["月", "火", "水", "木", "金", "土", "日"]
        wd = weekday_names[start_dt.weekday()]
        return (
            f"✅ 予定を登録しました。\n\n"
            f"📅 {purpose}\n"
            f"⏰ {start_dt.month}/{start_dt.day}({wd}) "
            f"{start_dt.strftime('%H:%M')}〜{end_dt.strftime('%H:%M')}"
        )

    # --- タスク管理 ---

    async def _handle_task_add(self, user_message: str) -> str:
        """タスクを追加"""
        # リッチメニューや短い抽象的な指示の場合は聞き返す
        short_patterns = ["タスク追加", "タスクを追加", "タスク登録", "タスクを登録", "タスクを追加したい", "タスク追加したい"]
        cleaned = user_message.strip()
        if any(cleaned == p or cleaned == p + "して" or cleaned == p + "する" for p in short_patterns):
            return "タスクの追加ですね。どんなタスクを追加しますか？\n（例：「報告書作成 金曜まで」「国保連請求の準備」）"

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
        if any(w in user_message for w in ["ルーティン", "繰り返し", "定期", "毎月", "毎週", "毎日"]):
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

    async def _handle_task_priority(self, user_message: str) -> str:
        """空き時間・予定・タスクを総合的に判断して提案"""
        tasks = task_service.get_pending_tasks()
        week_events = await calendar_service.get_upcoming_events(days=7)
        now = datetime.now()
        weekday_names = ["月", "火", "水", "木", "金", "土", "日"]

        # --- コード側で状況整理 ---
        # 未完了タスク（期限情報付き）
        task_lines = []
        for i, task in enumerate(tasks[:15], 1):
            due = ""
            urgency = ""
            if task.due_date:
                days_left = (task.due_date.date() - now.date()).days
                due = f" (期限: {task.due_date.strftime('%m/%d')})"
                if days_left < 0:
                    urgency = " 【期限超過！】"
                elif days_left == 0:
                    urgency = " 【今日期限】"
                elif days_left == 1:
                    urgency = " 【明日期限】"
                elif days_left <= 3:
                    urgency = f" 【あと{days_left}日】"
            priority = f" [優先度{task.priority}]" if task.priority <= 2 else ""
            task_lines.append(f"{i}. {task.title}{due}{priority}{urgency}")

        # 今後の予定（日数付きで整形）
        upcoming_lines = []
        for event in week_events:
            try:
                if event.get("all_day"):
                    start_dt = datetime.fromisoformat(event["start"])
                    time_str = "終日"
                else:
                    start_dt = datetime.fromisoformat(event["start"])
                    end_dt = datetime.fromisoformat(event["end"])
                    time_str = f"{start_dt.strftime('%H:%M')}-{end_dt.strftime('%H:%M')}"
                days_until = (start_dt.date() - now.date()).days
                if days_until == 0:
                    day_label = "今日"
                elif days_until == 1:
                    day_label = "明日"
                else:
                    wd = weekday_names[start_dt.weekday()]
                    day_label = f"{days_until}日後({start_dt.month}/{start_dt.day} {wd})"
                upcoming_lines.append(f"・{day_label} {time_str} {event['title']}")
            except (ValueError, KeyError):
                upcoming_lines.append(f"・{event.get('title', '不明')}")

        # --- 応答を組み立て ---
        result_parts = []

        # タスク状況
        if task_lines:
            result_parts.append("📋 未完了タスク：")
            result_parts.extend(task_lines)
        else:
            result_parts.append("📋 未完了タスクはありません。")

        # 今後の予定
        if upcoming_lines:
            result_parts.append("")
            result_parts.append("📅 今後1週間の予定：")
            result_parts.extend(upcoming_lines)

        # LLMに提案を生成させる（予定がある場合は必ず）
        if task_lines or upcoming_lines:
            task_text = "\n".join(task_lines) if task_lines else "なし"
            event_text = "\n".join(upcoming_lines) if upcoming_lines else "なし"

            prompt = f"""秘書「凛」として、以下の状況を踏まえて今やるべきことを3件以内で提案してください。

現在時刻: {now.strftime('%m/%d %H:%M')}
ユーザーの発言: {user_message}

未完了タスク:
{task_text}

今後1週間の予定:
{event_text}

提案のルール:
- 期限超過・今日期限のタスクは最優先
- 予定の事前準備を必ず提案すること（打ち合わせなら資料準備、面談なら面談シート確認など）
- 各提案に理由を一言添える
- 丁寧語、簡潔に"""

            if await llm_service._is_ollama_available():
                suggestion = await llm_service.generate(prompt=prompt, temperature=0.5)
            else:
                filtered = pii_filter.redact(prompt)
                suggestion = await llm_service.generate(prompt=filtered, temperature=0.5)
                suggestion = pii_filter.restore(suggestion)

            result_parts.append("")
            result_parts.append("💡 提案：")
            result_parts.append(suggestion.strip())
        else:
            result_parts.append("\n✨ タスクも予定もありません。ゆっくりお過ごしください。")

        return "\n".join(result_parts)

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
        """メール下書き/送信/予定変更・削除の確認応答を処理"""
        action = self._pending_action
        if not action:
            return None

        msg_lower = user_message.strip().lower()
        msg_text = user_message.strip()

        # 予定変更: 候補選択
        if action["type"] == "schedule_update":
            num_match = re.search(r"(\d+)", msg_text)
            if num_match:
                idx = int(num_match.group(1)) - 1
                events = action["events"]
                if 0 <= idx < len(events):
                    self._pending_action = None
                    return await self._execute_schedule_update(events[idx], action["parsed"])
                return f"1〜{len(events)}の番号で選んでください。"
            if msg_lower in ("キャンセル", "やめる", "やめて", "cancel"):
                self._pending_action = None
                return "操作をキャンセルしました。"
            return None

        # 予定削除: 確認
        if action["type"] == "schedule_delete_confirm":
            if msg_lower in ("はい", "ok", "yes", "削除", "消して"):
                self._pending_action = None
                event = action["event"]
                success = await calendar_service.delete_event(event["id"])
                if success:
                    return f"🗑️ 「{event['title']}」を削除しました。"
                return "申し訳ございません、予定の削除に失敗しました。"
            if msg_lower in ("キャンセル", "やめる", "やめて", "いいえ", "cancel"):
                self._pending_action = None
                return "削除をキャンセルしました。"
            self._pending_action = None
            return None

        # 予定削除: 候補選択
        if action["type"] == "schedule_delete_select":
            num_match = re.search(r"(\d+)", msg_text)
            if num_match:
                idx = int(num_match.group(1)) - 1
                events = action["events"]
                if 0 <= idx < len(events):
                    target = events[idx]
                    self._pending_action = {
                        "type": "schedule_delete_confirm",
                        "event": target,
                    }
                    weekday_names = ["月", "火", "水", "木", "金", "土", "日"]
                    try:
                        dt = datetime.fromisoformat(target["start"])
                        if dt.tzinfo is not None:
                            dt = dt.replace(tzinfo=None)
                        wd = weekday_names[dt.weekday()]
                        time_str = f"{dt.month}/{dt.day}({wd}) {dt.strftime('%H:%M')}"
                    except (ValueError, KeyError):
                        time_str = ""
                    return f"以下の予定を削除してよろしいですか？\n\n📅 {target['title']}\n⏰ {time_str}\n\n「はい」で削除します。"
                return f"1〜{len(events)}の番号で選んでください。"
            if msg_lower in ("キャンセル", "やめる", "やめて", "cancel"):
                self._pending_action = None
                return "操作をキャンセルしました。"
            self._pending_action = None
            return None

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
• 「今日の予定」「明日の予定」— 特定の日の予定を確認
• 「今週の予定」— 今日から1週間の予定を確認
• 「予定を追加したい」— カレンダーに予定を登録
• 「会議を15時に変更して」— 予定を変更
• 「明日の面談を削除して」— 予定を削除
• 「〇〇と打ち合わせしたい」— 空き時間を検索して候補提示

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
        """汎用LLM会話で応答を生成（会話履歴+保存済み設定付き）"""
        context = memory_service.format_context_for_prompt()

        # 保存済み設定をコンテキストに追加
        prefs = preference_service.get_all_preferences()
        pref_context = ""
        if prefs:
            pref_lines = [f"- {k}: {v}" for k, v in prefs.items()]
            pref_context = f"\n\n【ユーザーが覚えてほしいと言った情報】\n" + "\n".join(pref_lines)

        if context:
            prompt = f"{context}{pref_context}\n\nユーザー: {user_message}"
        else:
            prompt = f"{pref_context}\n\nユーザー: {user_message}" if pref_context else user_message

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
