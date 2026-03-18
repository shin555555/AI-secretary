import logging
import re

logger = logging.getLogger(__name__)


class PIIFilter:
    """個人情報（PII）の検出・除去・復元を行うフィルタ"""

    def __init__(self) -> None:
        # 置換マッピング: {プレースホルダ: 元の値}
        self._mapping: dict[str, str] = {}
        self._counter: int = 0

        # 正規表現パターン（日本語向け）
        self._patterns: list[tuple[str, str]] = [
            # 電話番号（090-1234-5678、03-1234-5678 等）
            (r"\d{2,4}[-\s]?\d{2,4}[-\s]?\d{3,4}", "PHONE"),
            # 受給者証番号（数字10桁前後）
            (r"受給者証[番号:：\s]*[\d\-]+", "CERT"),
            # メールアドレス
            (r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", "EMAIL"),
            # 住所（〒付き）
            (r"〒?\d{3}[-\s]?\d{4}[^\n]*", "ADDRESS"),
        ]

        # DB登録済みのクライアント名（動的に追加可能）
        self._client_names: list[str] = []

    def add_client_names(self, names: list[str]) -> None:
        """保護対象のクライアント名を登録"""
        self._client_names = names

    def redact(self, text: str) -> str:
        """テキストからPIIを除去し、プレースホルダに置換"""
        self._mapping.clear()
        self._counter = 0
        result = text

        # クライアント名の置換（完全一致、長い名前から先に処理）
        for name in sorted(self._client_names, key=len, reverse=True):
            if name in result:
                placeholder = self._create_placeholder("CLIENT")
                self._mapping[placeholder] = name
                result = result.replace(name, placeholder)

        # 正規表現パターンによる置換
        for pattern, label in self._patterns:
            matches = re.findall(pattern, result)
            for match in matches:
                if any(p in match for p in self._mapping):
                    continue  # 既に置換済み
                placeholder = self._create_placeholder(label)
                self._mapping[placeholder] = match
                result = result.replace(match, placeholder, 1)

        if self._mapping:
            logger.info(f"PII除去: {len(self._mapping)}件のPIIをマスク")

        return result

    def restore(self, text: str) -> str:
        """プレースホルダを元の値に復元"""
        result = text
        for placeholder, original in self._mapping.items():
            result = result.replace(placeholder, original)
        return result

    def _create_placeholder(self, label: str) -> str:
        """一意なプレースホルダを生成"""
        self._counter += 1
        return f"[{label}_{self._counter:03d}]"


# シングルトンインスタンス
pii_filter = PIIFilter()
