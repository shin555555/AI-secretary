# セッション引き継ぎ（Claudeへの指示）

新しいセッション開始時にこのファイルをClaudeに読み込ませること。

---

## プロジェクト概要

就労継続支援B型事業所の管理者専用 **AI秘書「凛（りん）」** の開発。
LINE経由で自然言語操作、Googleカレンダー連携、タスク管理、朝ブリーフィングを提供。
月額0円（ローカルLLM + 無料APIのハイブリッド構成）。

## 必ず読むファイル

1. `requirements.md` — 全仕様（これが唯一の正）
2. `docs/progress.md` — 現在の進捗・チェックリスト
3. `.claude/rules/security.md` — セキュリティルール（最重要）
4. `.claude/rules/ai-behavior.md` — Claudeへの行動指示
5. `docs/decisions.md` — 設計上の決定事項

## 技術スタック（要約）

- Python FastAPI + SQLCipher + APScheduler
- Ollama（ローカルLLM）+ Gemini API（フォールバック）
- LINE Messaging API + Google Calendar API
- Cloudflare Tunnel（Webhook公開）

## 現在の作業状態

→ `docs/progress.md` を確認してください。

## 重要な制約（忘れないこと）

- **個人情報は外部APIに送らない** → pii_filter.py 経由必須
- **秘密情報はコードにハードコードしない** → .env + Pydantic Settings
- **requirements.md に記載のない機能は追加しない**
- **git push は明示的に指示されるまで実行しない**
