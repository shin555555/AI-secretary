# アーキテクチャ方針

## 全体構成
- **バックエンド**: Python FastAPI（ローカルPC上で動作）
- **LLM**: Ollama（ローカル）+ Google Gemini（フォールバック）
- **DB**: SQLite + SQLCipher（暗号化）
- **外部連携**: LINE Messaging API, Google Calendar API
- **トンネル**: Cloudflare Tunnel
- **スケジューラ**: APScheduler

## ディレクトリ構成ルール
- `app/api/` — FastAPIルート（HTTPエンドポイント）のみ。ビジネスロジックを書かない
- `app/services/` — ビジネスロジック層。各サービスは単一責任
- `app/models/` — SQLAlchemyモデル（DBスキーマ）
- `app/schemas/` — Pydantic型定義（リクエスト/レスポンス）
- `app/prompts/` — LLMプロンプトテンプレート
- `config/` — 設定管理
- `scheduler/` — 定期実行ジョブ
- `data/` — 実行時データ（gitignore対象）

## サービス層の設計原則

### 依存の方向
```
api/ → services/ → models/
                 → schemas/
                 → external APIs
```
- api層はservices層に依存する（直接DBやAPIを叩かない）
- services層は他のservicesに依存してよい

### コアオーケストレータ: `secretary.py`
- すべてのLINEメッセージはここを経由する
- インテント分類 → 適切なサービスにルーティング → 応答生成
- 新機能追加時はここにインテントとルーティングを追加

### LLMサービス: `llm_service.py`
- Ollama と Gemini の切り替えを抽象化
- 外部API（Gemini）使用時は必ず `pii_filter.py` を経由
- ヘルスチェックでOllamaの生死を判定し、自動フォールバック

## データベース方針
- ORM: SQLAlchemy 2.0（非同期セッション）
- マイグレーション: 初期段階では不要。必要になったらAlembicを導入
- すべてのテーブルに `created_at`, `updated_at` を含める

## エラーハンドリング
- 外部サービス障害時はグレースフルデグラデーション（使える機能だけ動かす）
- ユーザー向けメッセージは日本語で分かりやすく
- すべてのエラーをログに記録（ローテーション付き）
- 例外は具体的にキャッチ（bare `except:` 禁止）

## 禁止パターン
- グローバル変数で状態管理（FastAPIのDI・DBを使う）
- 同期的なHTTPリクエスト（`requests`禁止、`httpx`のasyncを使う）
- LLMの出力をバリデーションなしでDB/APIに渡す
