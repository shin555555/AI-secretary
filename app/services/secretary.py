import logging

from app.prompts.intent_classifier import INTENT_CLASSIFICATION_PROMPT, VALID_INTENTS
from app.prompts.system_prompt import SYSTEM_PROMPT
from app.services.llm_service import llm_service
from app.services.memory_service import memory_service
from app.services.pii_filter import pii_filter

logger = logging.getLogger(__name__)


class Secretary:
    """凛のコアオーケストレータ: インテント分類 → サービスルーティング → 応答生成"""

    async def handle_message(self, user_message: str) -> str:
        """ユーザーメッセージを処理して応答を生成"""
        # インテント分類
        intent = await self._classify_intent(user_message)
        logger.info(f"インテント: {intent}")

        # 会話履歴にユーザーメッセージを保存
        memory_service.save_message(role="user", content=user_message, intent=intent)

        # インテントに応じたルーティング
        # Phase 2: まずは全インテントをLLM会話で処理
        # Phase 3-4で各サービスへのルーティングを追加
        response = await self._handle_general(user_message, intent)

        # 会話履歴に凛の応答を保存
        memory_service.save_message(role="assistant", content=response)

        return response

    async def _classify_intent(self, user_message: str) -> str:
        """LLMでインテント分類"""
        prompt = INTENT_CLASSIFICATION_PROMPT.format(user_message=user_message)

        raw_intent = await llm_service.generate(
            prompt=prompt,
            temperature=0.1,  # 分類は低温度で確実に
        )

        # 応答からインテント名を抽出（余計なテキストを除去）
        intent = raw_intent.strip().lower()
        for valid in VALID_INTENTS:
            if valid in intent:
                return valid

        logger.warning(f"不明なインテント: {raw_intent} → generalにフォールバック")
        return "general"

    async def _handle_general(self, user_message: str, intent: str) -> str:
        """汎用LLM会話で応答を生成（会話履歴付き）"""
        # 会話コンテキストを取得
        context = memory_service.format_context_for_prompt()

        # コンテキスト付きプロンプトを構築
        if context:
            prompt = f"{context}\n\nユーザー: {user_message}"
        else:
            prompt = user_message

        # Ollamaが使える場合はそのまま送信（ローカルなのでPII問題なし）
        if await llm_service._is_ollama_available():
            return await llm_service.generate(
                prompt=prompt,
                system_prompt=SYSTEM_PROMPT,
            )

        # Geminiフォールバック時はPIIフィルタ必須
        filtered_prompt = pii_filter.redact(prompt)
        filtered_response = await llm_service.generate(
            prompt=filtered_prompt,
            system_prompt=SYSTEM_PROMPT,
        )
        response: str = pii_filter.restore(filtered_response)
        return response


# シングルトンインスタンス
secretary = Secretary()
