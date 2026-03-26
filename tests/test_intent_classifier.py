"""インテント分類のユニットテスト

_pre_classify_intent: キーワードベース事前分類（モック不要）
_classify_intent: LLM呼び出し結果のパース・バリデーション（LLMをモック）
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.secretary import Secretary


@pytest.fixture()
def secretary():
    return Secretary()


# ===== _pre_classify_intent（キーワードベース事前分類） =====


class TestPreClassifyScheduleUpdate:
    def test_update_meeting_time(self, secretary):
        assert secretary._pre_classify_intent("会議を14時に変更して") == "schedule_update"

    def test_reschedule(self, secretary):
        assert secretary._pre_classify_intent("面談をリスケして") == "schedule_update"

    def test_move_schedule(self, secretary):
        assert secretary._pre_classify_intent("予定を変更したい") == "schedule_update"

    def test_shift_meeting(self, secretary):
        assert secretary._pre_classify_intent("打ち合わせを15時にずらして") == "schedule_update"

    def test_schedule_henkou(self, secretary):
        assert secretary._pre_classify_intent("スケジュール変更") == "schedule_update"


class TestPreClassifyScheduleDelete:
    def test_delete_meeting(self, secretary):
        assert secretary._pre_classify_intent("明日の会議を削除して") == "schedule_delete"

    def test_cancel_mendan(self, secretary):
        assert secretary._pre_classify_intent("面談をキャンセルして") == "schedule_delete"

    def test_delete_yotei(self, secretary):
        assert secretary._pre_classify_intent("予定を消して") == "schedule_delete"

    def test_torikeshi(self, secretary):
        assert secretary._pre_classify_intent("打ち合わせを取り消して") == "schedule_delete"

    def test_task_delete_not_schedule(self, secretary):
        """「タスク」を含む場合はschedule_deleteにならない"""
        assert secretary._pre_classify_intent("タスクを削除して") is None


class TestPreClassifySummary:
    def test_shuuhou(self, secretary):
        assert secretary._pre_classify_intent("週報お願い") == "summary_report"

    def test_geppo(self, secretary):
        assert secretary._pre_classify_intent("月報見せて") == "summary_report"

    def test_furikaeri(self, secretary):
        assert secretary._pre_classify_intent("今週の振り返り") == "summary_report"


class TestPreClassifyNoMatch:
    def test_general_message(self, secretary):
        assert secretary._pre_classify_intent("おはよう") is None

    def test_schedule_check(self, secretary):
        """予定確認は事前分類対象外（LLMに委ねる）"""
        assert secretary._pre_classify_intent("今日の予定教えて") is None

    def test_task_add(self, secretary):
        assert secretary._pre_classify_intent("タスク追加：報告書") is None


# ===== _classify_intent（LLMモック） =====


@pytest.mark.asyncio
class TestClassifyIntentParsing:
    async def test_single_intent(self, secretary):
        with patch.object(secretary, "_classify_intent", wraps=secretary._classify_intent):
            with patch("app.services.secretary.llm_service.generate", new_callable=AsyncMock, return_value="schedule_check"):
                result = await secretary._classify_intent("今日の予定")
                assert result == ["schedule_check"]

    async def test_multiple_intents_comma(self, secretary):
        with patch("app.services.secretary.llm_service.generate", new_callable=AsyncMock, return_value="schedule_check,task_add"):
            result = await secretary._classify_intent("予定教えて、あとタスク追加")
            assert result == ["schedule_check", "task_add"]

    async def test_unknown_falls_back_to_general(self, secretary):
        with patch("app.services.secretary.llm_service.generate", new_callable=AsyncMock, return_value="unknown_intent"):
            result = await secretary._classify_intent("なんか変なメッセージ")
            assert result == ["general"]

    async def test_partial_match(self, secretary):
        """LLMが「インテント: schedule_check」のように余計なテキストを返した場合"""
        with patch("app.services.secretary.llm_service.generate", new_callable=AsyncMock, return_value="インテント: schedule_check"):
            result = await secretary._classify_intent("今日の予定は？")
            assert result == ["schedule_check"]

    async def test_mail_drafts_vs_mail_draft(self, secretary):
        """mail_drafts が mail_draft より先にマッチしないこと（完全一致優先）"""
        with patch("app.services.secretary.llm_service.generate", new_callable=AsyncMock, return_value="mail_draft"):
            result = await secretary._classify_intent("メール1に下書き")
            assert result == ["mail_draft"]

        with patch("app.services.secretary.llm_service.generate", new_callable=AsyncMock, return_value="mail_drafts"):
            result = await secretary._classify_intent("下書き一覧")
            assert result == ["mail_drafts"]

    async def test_empty_response_falls_back(self, secretary):
        with patch("app.services.secretary.llm_service.generate", new_callable=AsyncMock, return_value=""):
            result = await secretary._classify_intent("テスト")
            assert result == ["general"]

    async def test_whitespace_trimmed(self, secretary):
        with patch("app.services.secretary.llm_service.generate", new_callable=AsyncMock, return_value="  task_list  \n"):
            result = await secretary._classify_intent("タスク一覧")
            assert result == ["task_list"]

    async def test_case_insensitive(self, secretary):
        with patch("app.services.secretary.llm_service.generate", new_callable=AsyncMock, return_value="SCHEDULE_CHECK"):
            result = await secretary._classify_intent("今日の予定")
            assert result == ["schedule_check"]


# ===== インテント分類の代表的なメッセージ（事前分類で捕捉されるもの） =====


class TestRepresentativeMessages:
    """日本語メッセージの事前分類カバレッジ"""

    @pytest.mark.parametrize("msg,expected", [
        ("会議を14時に変更して", "schedule_update"),
        ("面談を来週にリスケして", "schedule_update"),
        ("予定変更", "schedule_update"),
        ("ミーティングを削除して", "schedule_delete"),
        ("面談をキャンセル", "schedule_delete"),
        ("予定を消して", "schedule_delete"),
        ("週報", "summary_report"),
        ("月報", "summary_report"),
        ("先週の振り返り", "summary_report"),
    ])
    def test_pre_classify(self, secretary, msg, expected):
        assert secretary._pre_classify_intent(msg) == expected

    @pytest.mark.parametrize("msg", [
        "おはようございます",
        "今日の予定教えて",
        "タスク追加：資料作成",
        "メール確認して",
        "ヘルプ",
        "1時間空いた",
    ])
    def test_not_pre_classified(self, secretary, msg):
        """LLMに委ねるべきメッセージが事前分類されないこと"""
        assert secretary._pre_classify_intent(msg) is None
