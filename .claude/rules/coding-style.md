# コーディングスタイル

## 言語・フォーマット
- **コード（変数名・関数名・クラス名）**: 英語
- **コメント・docstring**: 日本語
- **コミットメッセージ**: 日本語
- **ユーザーへの説明**: 日本語

## 命名規則
- 変数・関数: `snake_case` （例: `get_tasks`, `line_user_id`）
- クラス: `PascalCase` （例: `TaskService`, `PIIFilter`）
- 定数: `UPPER_SNAKE_CASE` （例: `MAX_RETRY_COUNT`, `BRIEFING_HOUR`）
- ファイル: `snake_case.py` （例: `llm_service.py`, `line_webhook.py`）

## Python スタイル
- Python 3.11+
- type hints 必須（すべての関数引数と戻り値）
- async/await を使用（FastAPI + httpx）
- 関数型コンポーネント優先（クラスは状態管理が必要な場合のみ）
- f-string を使用（.format() や % は使わない）

## インポート順序
```python
# 1. 標準ライブラリ
import os
from datetime import datetime

# 2. サードパーティ
from fastapi import APIRouter
from sqlalchemy import select

# 3. プロジェクト内
from app.services.task_service import TaskService
```

## Linter / Formatter
- ruff（lint + format）
- strict mode は段階的に導入
