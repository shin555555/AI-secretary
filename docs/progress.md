# 実装進捗

最終更新: 2026-03-18

## フェーズ一覧

| フェーズ | 内容 | ステータス |
|---------|------|-----------|
| ✅ 要件定義 | requirements.md 作成 | 完了 |
| ✅ Claudeルール | .claude/rules/ 作成 | 完了 |
| ✅ ドキュメント整備 | docs/ 作成（progress/setup/testing/decisions/onboarding） | 完了 |
| ✅ Git/GitHub | .gitignore・.env.example 作成、GitHubにpush | 完了 |
| ✅ Phase 0 | 環境構築 | 完了 |
| ✅ Phase 1 | LINE Echo Bot | 完了 |
| ✅ Phase 2 | LLM統合（凛ペルソナ） | 完了 |
| ⬜ Phase 3 | Googleカレンダー連携 | 未着手 |
| ⬜ Phase 4 | タスク管理 + リマインド | 未着手 |
| ⬜ Phase 5 | パーソナライズ | 未着手 |
| ⬜ Phase 6 | 安定化・自動起動 | 未着手 |

## Phase 0 チェックリスト（環境構築）

- [x] Python 3.11+ インストール確認（Python 3.12.8）
- [x] Ollama インストール + モデルpull（gemma2:9b-instruct-q5_K_M, v0.18.0）
- [x] LINE公式アカウント作成（Messaging API チャネル @042ndwhq）
- [x] Google Cloud プロジェクト作成 + Calendar API 有効化（2026-03-18 完了）
- [x] Google OAuth2 認証情報作成（2026-03-18 完了）
- [x] Cloudflare Tunnel インストール（cloudflared 2025.8.1）
- [x] Python仮想環境作成 + 依存関係インストール（.venv/）
- [x] .env ファイル作成（LINE_CHANNEL_SECRET, LINE_CHANNEL_ACCESS_TOKEN, LINE_USER_ID 設定済み）

## Phase 1 チェックリスト（LINE Echo Bot）

- [x] FastAPI 骨格作成（main.py, health.py）
- [x] LINE Webhook エンドポイント（line_webhook.py）
- [x] LINE 署名検証（HMAC-SHA256）
- [x] エコーボット動作確認
- [x] Cloudflare Tunnel 疎通確認（Quick Tunnel）
- [x] LINE から送信 → エコー返信 確認（2026-03-18）

## Phase 2 チェックリスト（LLM統合）

- [x] llm_service.py（Ollama バックエンド）
- [x] 凛のシステムプロンプト（system_prompt.py）
- [x] インテント分類（intent_classifier.py）
- [x] 会話履歴保存（conversations テーブル + memory_service.py）
- [x] Gemini フォールバック
- [x] pii_filter.py 実装
- [x] LINE で自然な会話ができる（2026-03-18 確認済み）

## Phase 3 チェックリスト（カレンダー）

- [ ] Google OAuth2 セットアップスクリプト
- [ ] calendar_service.py（取得・作成・衝突検出）
- [ ] 「今日の予定は？」→ 実データ返却
- [ ] 「明日14時に面談」→ カレンダー登録

## Phase 4 チェックリスト（タスク管理）

- [x] SQLite DB セットアップ（base.py）※標準SQLite版、SQLCipher化はPhase 6で検討
- [ ] Task モデル・スキーマ
- [ ] task_service.py（CRUD + 優先度）
- [ ] 自然言語タスク解析
- [ ] APScheduler: 朝8:00 ブリーフィング
- [ ] APScheduler: 期限24時間前リマインド

## Phase 5 チェックリスト（パーソナライズ）

- [x] memory_service.py（Phase 2で先行実装済み）
- [ ] preference テーブル・CRUD
- [ ] interaction_log テーブル
- [x] コンテキスト記憶（直近10ターン）（Phase 2で先行実装済み）

## Phase 6 チェックリスト（安定化）

- [ ] エラーハンドリング全体見直し
- [ ] Windows 自動起動設定（NSSM）
- [ ] ログローテーション設定
- [ ] 手動テスト全項目クリア（docs/testing.md 参照）

---

## 既知の問題・メモ

### 2026-03-18
- requirements.md に繰り返しタスク（ルーティン）・繰り返しカレンダー予定（RRULE）機能を追加
- decisions.md に設計決定を記録
- Phase 0 実装開始：pyproject.toml, requirements.txt, ディレクトリ構成, config/, app/ 作成
- FastAPI + LINE Webhook コード実装済み（エコーボット）
- LINE公式アカウント作成完了（@042ndwhq）、.env に3項目設定済み
- cloudflared インストール完了（v2025.8.1）、Quick Tunnel で疎通確認成功
- **Phase 1 完了**: LINE → エコーボット → 返信 の全フロー動作確認済み
- Ollama 0.18.0 + gemma2:9b-instruct-q5_K_M インストール完了（32GB RAM）
- **Phase 2 完了**: llm_service / secretary / pii_filter / memory_service / intent_classifier 実装
- LINE で凛（りん）として自然な会話応答を確認
- Google Cloud プロジェクトの作成、Calendar API 有効化、OAuth 同意画面設定
- Desktop 向け OAuth クライアントID 払い出し完了 (`data/google_credentials.json`) 
- `scripts/setup_google_oauth.py` 経由で初回認証フロー実行、`data/google_token.json` 保存完了
- **Phase 0 （環境構築）完全完了！**
- 次は **Phase 3（Googleカレンダー連携実装）** に移ります

_（開発中に発生した問題・決定事項をここに記録）_
