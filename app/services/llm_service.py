import logging
from typing import Any

import httpx

from config.settings import settings

logger = logging.getLogger(__name__)


class LLMService:
    """LLM抽象レイヤー: Ollama優先、Geminiフォールバック"""

    def __init__(self) -> None:
        self._ollama_url = settings.ollama_base_url
        self._ollama_model = settings.ollama_model
        self._gemini_api_key = settings.gemini_api_key
        self._gemini_model = "gemini-2.0-flash"
        self._timeout = httpx.Timeout(60.0, connect=10.0)

    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
    ) -> str:
        """LLMで応答を生成。Ollama → Gemini の順にフォールバック"""
        # Ollama を試行
        if await self._is_ollama_available():
            try:
                return await self._generate_ollama(prompt, system_prompt, temperature)
            except Exception as e:
                logger.warning(f"Ollama生成失敗、Geminiにフォールバック: {e}")

        # Gemini フォールバック
        if self._gemini_api_key:
            try:
                return await self._generate_gemini(prompt, system_prompt, temperature)
            except Exception as e:
                logger.error(f"Gemini生成も失敗: {e}")

        return "申し訳ございません、現在応答を生成できません。しばらくしてからもう一度お試しください。"

    async def _is_ollama_available(self) -> bool:
        """Ollamaのヘルスチェック"""
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(3.0)) as client:
                resp = await client.get(f"{self._ollama_url}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False

    async def _generate_ollama(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float,
    ) -> str:
        """Ollamaでローカル推論"""
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": self._ollama_model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._ollama_url}/api/chat",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            content: str = data["message"]["content"]
            logger.info(f"Ollama応答生成完了（{len(content)}文字）")
            return content.strip()

    async def _generate_gemini(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float,
    ) -> str:
        """Google Gemini APIで推論（PIIフィルタ済みデータのみ渡すこと）"""
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self._gemini_model}:generateContent?key={self._gemini_api_key}"
        )

        contents: list[dict[str, Any]] = []
        if system_prompt:
            contents.append({
                "role": "user",
                "parts": [{"text": f"[System]\n{system_prompt}"}],
            })
            contents.append({
                "role": "model",
                "parts": [{"text": "承知しました。指示に従います。"}],
            })
        contents.append({
            "role": "user",
            "parts": [{"text": prompt}],
        })

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": 1024,
            },
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            text: str = data["candidates"][0]["content"]["parts"][0]["text"]
            logger.info(f"Gemini応答生成完了（{len(text)}文字）")
            return text.strip()


# シングルトンインスタンス
llm_service = LLMService()
