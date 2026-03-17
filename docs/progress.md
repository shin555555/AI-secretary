# 実装進捗

最終更新: 2026-03-17

## フェーズ一覧

| フェーズ | 内容 | ステータス |
|---------|------|-----------|
| ✅ 要件定義 | requirements.md 作成 | 完了 |
| ✅ Claudeルール | .claude/rules/ 作成 | 完了 |
| ⬜ Phase 0 | 環境構築 | 未着手 |
| ⬜ Phase 1 | LINE Echo Bot | 未着手 |
| ⬜ Phase 2 | LLM統合（凛ペルソナ） | 未着手 |
| ⬜ Phase 3 | Googleカレンダー連携 | 未着手 |
| ⬜ Phase 4 | タスク管理 + リマインド | 未着手 |
| ⬜ Phase 5 | パーソナライズ | 未着手 |
| ⬜ Phase 6 | 安定化・自動起動 | 未着手 |

## Phase 0 チェックリスト（環境構築）

- [ ] Python 3.11+ インストール確認
- [ ] Ollama インストール + モデルpull（gemma2:9b または qwen2.5:14b）
- [ ] LINE公式アカウント作成（Messaging API チャネル）
- [ ] Google Cloud プロジェクト作成 + Calendar API 有効化
- [ ] Google OAuth2 認証情報作成
- [ ] Cloudflare Tunnel インストール（cloudflared）
- [ ] Python仮想環境作成 + 依存関係インストール
- [ ] .env ファイル作成（.env.example から）

## Phase 1 チェックリスト（LINE Echo Bot）

- [ ] FastAPI 骨格作成（main.py, health.py）
- [ ] LINE Webhook エンドポイント（line_webhook.py）
- [ ] LINE 署名検証（HMAC-SHA256）
- [ ] エコーボット動作確認
- [ ] Cloudflare Tunnel 疎通確認
- [ ] LINE から送信 → エコー返信 確認

## Phase 2 チェックリスト（LLM統合）

- [ ] llm_service.py（Ollama バックエンド）
- [ ] 凛のシステムプロンプト（system_prompt.py）
- [ ] インテント分類（intent_classifier.py）
- [ ] 会話履歴保存（conversations テーブル）
- [ ] Gemini フォールバック
- [ ] pii_filter.py 実装
- [ ] LINE で自然な会話ができる

## Phase 3 チェックリスト（カレンダー）

- [ ] Google OAuth2 セットアップスクリプト
- [ ] calendar_service.py（取得・作成・衝突検出）
- [ ] 「今日の予定は？」→ 実データ返却
- [ ] 「明日14時に面談」→ カレンダー登録

## Phase 4 チェックリスト（タスク管理）

- [ ] SQLCipher DB セットアップ（base.py）
- [ ] Task モデル・スキーマ
- [ ] task_service.py（CRUD + 優先度）
- [ ] 自然言語タスク解析
- [ ] APScheduler: 朝8:00 ブリーフィング
- [ ] APScheduler: 期限24時間前リマインド

## Phase 5 チェックリスト（パーソナライズ）

- [ ] memory_service.py
- [ ] preference テーブル・CRUD
- [ ] interaction_log テーブル
- [ ] コンテキスト記憶（直近10ターン）

## Phase 6 チェックリスト（安定化）

- [ ] エラーハンドリング全体見直し
- [ ] Windows 自動起動設定（NSSM）
- [ ] ログローテーション設定
- [ ] 手動テスト全項目クリア（docs/testing.md 参照）

---

## 既知の問題・メモ

_（開発中に発生した問題・決定事項をここに記録）_
