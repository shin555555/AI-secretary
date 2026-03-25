# 実装進捗

最終更新: 2026-03-25（doc-sync）

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
| ✅ Phase 3 | Googleカレンダー連携 | 完了 |
| ✅ Phase 4 | タスク管理 + リマインド | 完了 |
| ✅ Phase 5 | パーソナライズ | 完了 |
| ✅ Phase 6 | 安定化・自動起動 | 完了 |
| ✅ Phase 7 | Gmail連携・ヘルプ・リッチメニュー9ボタン | 完了 |
| ✅ Phase 8 | カレンダー・タスク改善・日程調整 | 完了 |
| ✅ Phase 9 | 品質改善・機能拡張（変更/削除/サマリー/通知等） | 完了 |
| 🔲 Phase 10 | 利用者情報管理（ClientInfo・受給者証・リマインド） | 未着手 |
| 🔲 Phase 11 | テスト・セキュリティ修正（ユニットテスト・PIIフィルタ誤検知） | 未着手 |
| 🔲 Phase 12 | プロアクティブ通知・会話品質改善 | 未着手 |

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

- [x] Google OAuth2 セットアップスクリプト（scripts/setup_google_oauth.py）
- [x] calendar_service.py（取得・作成・衝突検出）
- [x] 「今日の予定は？」→ 実データ返却
- [x] 「明日14時に面談」→ カレンダー登録
- [x] 繰り返し予定（RRULE）対応
- [x] datetime_parser.py（コードベース日付解決、LLMは生テキスト抽出のみ）

## Phase 4 チェックリスト（タスク管理）

- [x] SQLite DB セットアップ（base.py）→ SQLCipher暗号化済み
- [x] Task・RecurringTask モデル（app/models/task.py）
- [x] task_service.py（CRUD + 優先度 + 削除 + 繰り返しタスク）
- [x] task_parser.py（コードベース日付解決）
- [x] APScheduler: 朝8:00 ブリーフィング（scheduler/jobs.py）
- [x] APScheduler: 期限24時間前リマインド 18:00（scheduler/jobs.py）
- [x] APScheduler: 繰り返しタスク自動生成 0:00（scheduler/jobs.py）

## Phase 5 チェックリスト（パーソナライズ）

- [x] memory_service.py（Phase 2で先行実装済み）
- [x] Preference モデル・CRUD（app/models/preference.py, app/services/preference_service.py）
- [x] InteractionLog モデル・行動ログ記録（app/models/preference.py）
- [x] コンテキスト記憶（直近10ターン）（Phase 2で先行実装済み）

## Phase 6 チェックリスト（安定化）

- [x] エラーハンドリング（グレースフルデグラデーション実装済み）
- [x] Windows 自動起動設定（タスクスケジューラ: 平日7:30スリープ解除+起動、ログオン時起動）
- [x] ログローテーション設定（RotatingFileHandler: 5MB x 3ファイル）
- [x] start_server.bat / stop_server.bat（英語版、エンコーディング問題対応済み）
- [x] Quick Tunnel + LINE Webhook URL自動更新（scripts/start_tunnel.py）
- [x] SQLCipher暗号化DB導入（AES-256、キーはWindows資格情報マネージャーで管理）
- [x] トンネル死活監視・自動復旧（startup.py: 60秒ごとプロセス監視、5分ごとWebhook疎通チェック）
- [x] 深夜0時自動スリープ（タスクスケジューラ: RinAISecretary-SleepAt0）
- [x] 手動テスト Phase 1〜5 クリア（docs/testing.md 参照、2026-03-24 完了）

---

## v2 タスク

### Gmail連携（Phase 7）
- [x] OAuthスコープ追加（gmail.readonly + gmail.send + gmail.compose）→ トークン再取得
- [x] gmail_service.py — Gmail API接続・メール取得・下書き・送信
- [x] メールトリアージ — ルールベース除外 + LLM 3段階分類（要返信/要確認/スキップ）
- [x] mail_check インテント — 「メール確認」で重要メール一覧表示
- [x] mail_detail インテント — 「メール1の詳細」で本文要約表示
- [x] mail_draft インテント — 「メール1に下書き。〇〇と伝えて」→ 確認 → Gmail下書き保存
- [x] mail_reply インテント — 「メール1に返信して。〇〇と伝えて」→ 確認 → 直接送信
- [x] mail_drafts インテント — 「下書き一覧」で凛が作成した下書きを表示
- [x] mail_send インテント — 「下書き1を送信して」で保存済み下書きを送信
- [x] 朝ブリーフィングに未読重要メール件数・概要を追加
- [x] MailFilterRule モデル — ユーザーフィードバックで仕分けルールを学習・蓄積
- [x] PIIフィルタ: メール本文のGemini送信時はPIIフィルタ必須（Ollama優先）

### ヘルプ・リッチメニュー拡張（Phase 7）
- [x] help インテント — 「ヘルプ」「使い方」「何ができる？」で機能一覧を分かりやすく表示
- [x] リッチメニュー9ボタン化（3x3）— メール確認・下書き一覧・ヘルプを追加（上段青/中段緑/下段オレンジ）
- [x] LINEリッチメニュー（6ボタン版） — B案 2x3レイアウト実装済み（2026-03-19）
- [x] LINE Loadingアニメーション — LLM処理中に「考え中」表示（2026-03-19）

### カレンダー・タスク改善（Phase 8）
- [x] schedule_create 聞き返し改善 — リッチメニュー「予定追加」時に日時がない場合「どんな予定を追加しますか？」と聞き返し
- [x] カレンダーAPIタイムゾーンバグ修正 — `"Z"`（UTC）→ `"+09:00"`（JST）に全API呼び出しを修正
- [x] schedule_search インテント追加 — 「〇〇の予定っていつ？」でキーワード検索（過去半年〜未来半年）
- [x] 日付パーサー「X日→曜日」バグ修正 — `"23日"` が `"日"` に誤マッチして日曜日になるバグを修正
- [x] task_add 聞き返し改善 — リッチメニュー「タスク追加」時に内容がない場合「どんなタスクを追加しますか？」と聞き返し
- [x] task_priority 強化 — 7日間のタスク+予定を総合判断、予定からの先回り準備提案（「打ち合わせの資料準備は？」等）
- [x] schedule_find_slot インテント追加 — 「〇〇と打ち合わせしたい」で空き時間候補を提示、番号選択で登録
- [x] 「他の日時は？」で次の候補を提示する継続対話
- [x] コードレビュー指摘修正 — PIIフィルタ追加、1時間ハードコード修正、import整理、30分丸めエッジケース修正

### Phase 9: 品質改善・機能拡張（2026-03-25 洗い出し）

#### 🔴 Critical（秘書として致命的）
- [x] 予定の変更機能 — 「会議を14時に変更して」→ 既存予定を更新（schedule_update インテント + calendar_service.update_event）（2026-03-25 実装済み）
- [x] 予定の削除機能 — 「会議をキャンセルして」→ 既存予定を削除（schedule_delete インテント + calendar_service.delete_event）（2026-03-25 実装済み）
- [x] 平文バックアップDB削除 — data/secretary.db.plaintext.backup を削除（ファイルが存在しないことを確認済み）

#### 🟡 High（頻繁に問題になる）
- [x] 日付解析の拡張 — 「再来週の水曜」「3日後」「1週間後」「今週末」に対応（2026-03-25 実装済み）
- [x] 時刻の業務時間推定 — 「3時」→ 午前3時ではなく15時（9-17時の業務時間内なら午後を優先）（2026-03-25 実装済み）
- [x] 祝日対応 — ブリーフィングの祝日抑制（日本の祝日カレンダー参照）（2026-03-25 実装済み）
- [x] ブリーフィング失敗時のリトライ・通知 — 一度の失敗で終了せず再試行、失敗が続いたらユーザーに通知（2026-03-25 実装済み）
- [x] Geminiレート制限対応 — 指数バックオフリトライの実装（2026-03-25 実装済み）
- [x] GeminiのAPIキーがログに出る問題 — URLパラメータからx-goog-api-keyヘッダーに移行 + エラーログのサニタイズ（2026-03-25 実装済み）
- [x] PIIフィルタ強化 — マイナンバー（12桁）、銀行口座番号、クレジットカード番号のパターン追加（2026-03-25 実装済み）

#### 🟢 Medium（改善すると良い）
- [x] 時刻不明時の聞き返し — 「10日に面談」→ デフォルト9時ではなく「何時ですか？」と確認（2026-03-25 実装済み）
- [x] タスクの編集機能 — タイトル変更・期限変更（2026-03-25 実装済み: task_editインテント + task_service.update_task）
- [x] 予定のリマインド — カレンダー予定の30分前通知（2026-03-25 実装済み: 10分間隔で実行、二重通知防止付き）
- [x] 複合リクエスト対応 — 「予定教えて、あとタスクも追加して」→ 複数インテント処理（2026-03-25 実装済み: LLMがカンマ区切りで返す、順次処理＋結合）
- [x] 会話コンテキストの代名詞解決 — 「それを変更して」の「それ」を直前の会話から解決（2026-03-25 実装済み: LLMで代名詞→具体名詞に書き換え）
- [x] メール受信通知 — 重要メール着信時のプッシュ通知（2026-03-25 実装済み: 15分間隔ポーリング、二重通知防止付き）
- [ ] HTMLメール・添付ファイル認識 — 「PDFが添付されています」と通知
- [x] 週報・月報サマリー — 「今週何件の面談があった？」のような振り返り（2026-03-25 実装済み: summary_reportインテント + _handle_summary_report、カテゴリ別集計・完了タスク表示）

---

## Phase 10: 利用者情報管理（2026-03-25 ギャップ分析より追加）

> 就労継続支援事業所の業務に特化した機能。現在は完全未実装。

#### 🔴 Critical
- [ ] `app/models/client_info.py` — ClientInfoモデル（氏名・受給者証番号・有効期限・個別支援計画更新期限・category）
- [ ] `app/services/client_service.py` — ClientInfo CRUD（登録・一覧・検索・更新・削除）
- [ ] インテント追加 — `client_add` / `client_list` / `client_check` / `client_update` / `client_delete`
- [ ] LINEから利用者登録・一覧・期限確認の操作（secretary.pyにルーティング追加）

#### 🟡 High
- [ ] 受給者証更新リマインド — 有効期限30日前・7日前にLINE Push通知（APSchedulerジョブ追加）
- [ ] 個別支援計画更新追跡 — 更新対象月の月初にLINE Push通知
- [ ] PIIフィルタに利用者名・受給者証番号のマスク追加（pii_filter.py拡張）

#### 🟢 Medium
- [ ] 利用者ごとのタスク・予定との紐付け（Task.client_id フィールド追加）
- [ ] 月次利用者サービス提供実績の集計（summary_reportに統合）

---

## Phase 11: テスト・セキュリティ修正（2026-03-25 ギャップ分析より追加）

> 現在 `tests/` ディレクトリには `__init__.py` のみ。PIIフィルタに誤検知リスクあり。

#### 🔴 Critical
- [ ] PIIフィルタ誤検知修正 — `"12月4日 10:00"` が `\d{4}\s?\d{4}\s?\d{4}` のマイナンバーパターンにマッチする問題（数字境界アサーション `\b` または桁数厳密化で修正）
- [ ] `tests/test_pii_filter.py` — redact/restore の正常ケース・誤検知ケースのユニットテスト

#### 🟡 High
- [ ] `tests/test_datetime_parser.py` — 「再来週の水曜」「3日後」「今週末」「一昨日」等の全パターンテスト
- [ ] `tests/test_task_service.py` — CRUD・期限計算・完了タスク集計のテスト
- [ ] `tests/test_intent_classifier.py` — 代表的な日本語メッセージの分類精度テスト（モック使用）

#### 🟢 Medium
- [ ] `tests/test_summary_report.py` — カテゴリ別集計ロジックのユニットテスト
- [ ] pytest設定（`pyproject.toml` の `[tool.pytest.ini_options]`）とCI統合（GitHub Actions）
- [ ] カバレッジレポート設定（`pytest-cov`）

---

## Phase 12: プロアクティブ通知・会話品質改善（2026-03-25 ギャップ分析より追加）

> 現在は「聞かれたら答える」型。「先回りして通知する」プロアクティブ機能が欠如。

#### 🟡 High（プロアクティブ通知）
- [ ] 月末業務予告通知 — 毎月25日17:00に「月末が近づいています。国保連請求・月次報告の準備はいかがですか？」を自動Push
- [ ] 金曜週次総括 — 毎週金曜17:30に今週の予定・完了タスク・翌週の予定をLINE Push
- [ ] 異常検知通知 — 平日午前9時を過ぎてもメッセージがない場合（＝何らかの問題）に軽いチェックインメッセージ

#### 🟡 High（会話品質）
- [ ] 長文レスポンスの「続き」対応 — LINEの5000文字制限を超える場合に「続きを見る」で次のチャンクを取得
- [ ] 議事録テンプレート自動生成 — 会議予定終了後30分で「議事録を作成しますか？」とPush、テンプレートをGoogleドキュメント or LINEに返す

#### 🟢 Medium（会話品質・UX）
- [ ] ペルソナ応答パターンの拡充 — 凛の応答パターンをsystem_prompt.pyに追記（励まし・体調確認・労いなど感情的なサポート）
- [ ] HTMLメール・添付ファイル認識 — メール本文のHTMLタグ除去 + 「PDFが添付されています」と通知
- [ ] タスク進捗ステータス拡充 — `in_progress`（作業中）の明示的利用（現状は pending/done の2値のみ実質使用）
- [ ] タスク完了時の達成感フィードバック — 「お疲れ様でした！今日N件完了しました」等の振り返り

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

### 2026-03-18（Phase 3〜6 実装）
- **Phase 3 完了**: calendar_service.py、datetime_parser.py（コードベース日付解決に変更 — LLMの曜日計算が不正確だったため）
- **Phase 4 完了**: Task/RecurringTaskモデル、task_service.py、task_parser.py、APScheduler 3ジョブ（朝ブリーフィング/繰り返しタスク生成/期限リマインド）
- **Phase 5 完了**: Preference/InteractionLogモデル、preference_service.py
- **Phase 6 完了**: タスクスケジューラ（平日7:30 WakeToRun）、start_server.bat/stop_server.bat（英語化 — 日本語batがエンコーディングエラー）、ログローテーション
- Quick Tunnel URL自動取得 + LINE Webhook URL自動更新スクリプト（start_tunnel.py）実装 — ドメイン不要、毎回のURL変更に自動対応
- Cloudflare Zero Trust永続トンネルはドメイン必須のため断念、Quick Tunnel + 自動更新方式に変更
- LINEからの全機能動作確認済み（会話、カレンダー、タスク管理、削除）

### 2026-03-18（セキュリティ強化）
- SQLCipher暗号化DB導入（sqlcipher3パッケージ、AES-256）
- 暗号化キーはOS keyring（Windows資格情報マネージャー）で管理 — コード・.envに秘密情報なし
- 移行スクリプト（scripts/migrate_to_sqlcipher.py）作成
- 平文バックアップ（data/secretary.db.plaintext.backup）は動作確認後に削除可

### 2026-03-19（Phase 7 完了・バグ修正）
- **Phase 7 完了**: Gmail連携（gmail_service.py）、ヘルプ（help インテント）、リッチメニュー9ボタン化
- Gmail OAuth スコープ追加後にトークン再取得（data/google_token.json 削除→再認証）
- **バグ修正1**: インテント分類で `mail_draft` が `mail_drafts` より先にマッチする問題 → 完全一致優先・長い名前優先の部分一致に変更
- **バグ修正2**: Gmail drafts().get() がデフォルト minimal フォーマットを返すため件名・宛先が取得できなかった → `format="full"` を指定
- **バグ修正3**: 下書きヘッダーが小文字（`subject`, `to`）で返るため大文字でのget()がMISSINGになっていた → `.lower()` で正規化
- リッチメニューUI改善: アイコンサイズ 120→160px、ラベルサイズ 72→96px、下段カラーをパープル→オレンジ（#E67E22）に変更
- **UX改善**: LINE Loadingアニメーション実装 — メッセージ受信直後に `show_loading_animation`（20秒）を呼び出し、LLM処理中の「考え中」を視覚的に表示。Reply送信時に自動消滅。失敗時も処理は継続（グレースフルデグラデーション）。

### 2026-03-19（Phase 8 完了）
- **カレンダー改修3件**: 聞き返し改善 / タイムゾーン `"Z"` → `"+09:00"` 修正 / schedule_search 追加
- **日付パーサーバグ修正**: `WEEKDAY_MAP` の `"日"` が `"23日"` 内の数字＋日にマッチ → `re.search(r"\d" + re.escape(label), raw)` で除外
- **タスク優先提案強化**: 今日のタスク/予定だけでなく7日間スコープ、予定からの先回り準備提案を追加
- **空き時間検索・日程調整**: `find_available_slots()` で営業時間内の空きを算出、候補提示→番号選択→登録のフロー実装
- **コードレビュー実施**: PIIフィルタ漏れ（Critical）、1時間ハードコード、30分丸めエッジケースを修正

### 2026-03-23（安定性修正・自動化強化）
- **バグ修正1**: `BackgroundScheduler()` にタイムゾーン未指定 → UTC基準で曜日判定がずれ土日にもブリーフィングが送信されていた → `BackgroundScheduler(timezone="Asia/Tokyo")` に修正
- **バグ修正2**: `calendar_service.create_event()` で `fromisoformat()` が `ValueError` を投げた際に `str` 型のまま `isoformat()` を呼んでエラー → `try/except ValueError` でキャッチし `None` 返却に修正
- **安定化**: `start_tunnel.py` のヘルスチェックをローカル優先に変更 — DNS未解決（`getaddrinfo failed`）でもWebhook URL更新に進めるよう修正
- **自動復旧強化**: `startup.py` にトンネル死活監視ループを追加 — 60秒ごとプロセス生死確認・自動再起動、5分ごとLINE APIでWebhook疎通テスト・失敗時はトンネル再起動
- **深夜スリープ**: `scripts/sleep_server.bat` 新規作成、タスクスケジューラ `RinAISecretary-SleepAt0`（毎日0:00）登録 → サーバー停止+PCスリープ
- **cloudflaredサービス無効化**: サービス版cloudflaredとコンソール版の競合が原因でWebhookが530エラーになっていた → `sc config cloudflared start= disabled` で無効化
- **タスクスケジューラ改善**: `setup_scheduler.ps1` をパスワード不要（S4U/Interactive方式）に変更、SleepAt0タスクを追加

### 2026-03-24（手動テスト Phase 4〜5 完了・設定反映機能修正）
- **手動テスト完了**: Phase 4（タスク管理）全項目 + Phase 5（パーソナライズ）全項目クリア
- **バグ修正3**: 設定検索時に保存済み設定が反映されない問題 → `_handle_schedule_search()` で見つからない場合に設定確認・`_handle_general()` でも設定をコンテキストに注入するよう修正
- **機能改善**: 「レセはいつだっけ？」のような質問で、カレンダーに見つからない場合、保存済み設定（「レセは毎月10日まで」等）を表示するよう拡張
- **汎用会話強化**: `_handle_general()` に保存済み設定をプロンプトコンテキストに自動注入 — ユーザーの好み設定がLLM応答に常に反映されるよう改善

_（開発中に発生した問題・決定事項をここに記録）_

### 2026-03-25（Mediumタスク追加実装）
- **メール受信通知**: mail_notification_check()ジョブ追加（15分間隔、平日のみ）、通知済みID記憶で二重通知防止、日付変更でリセット
- **週報・月報サマリー**: summary_reportインテント追加、_handle_summary_report()実装（今週/先週/今月/先月を自動判定）、カレンダー予定のカテゴリ別集計（面談/会議/研修/その他）、task_service.get_completed_tasks_between()追加

### 2026-03-25（Mediumタスク消化・バグ修正）
- **実装完了**: 時刻不明時の聞き返し（single予定のみ、繰り返し予定は9:00デフォルト維持）
- **実装完了**: タスクの編集機能（task_editインテント + update_task / find_task_by_keyword）
- **実装完了**: 予定リマインド30分前Push通知（10分間隔チェック、二重通知防止付き）
- **実装完了**: 複合リクエスト対応（LLMカンマ区切り複数インテント、pending時は先頭のみ処理）
- **実装完了**: 代名詞解決（few-shotプロンプト付きLLM書き換え、3文字以下・代名詞なしはスキップ）
- **バグ修正**: 予定重複時「はい」で強制登録できないバグ → pending_action保存 + force_create_event追加
- **予定の変更・削除**: schedule_update / schedule_delete インテント実装、変更・削除の確認フロー、複数候補の番号選択
- **セキュリティ修正**: GeminiのAPIキーをURLパラメータ→x-goog-api-keyヘッダーに移行、エラーログに_sanitize_error()でマスク処理追加
- **日付解析拡張**: datetime_parser.py / task_parser.py に「X日後/前」「X週間後/前」「Xヶ月後」「再来週X曜」「今週X曜」「今週末」「一昨日/おととい/あさって」を追加
- **業務時間推定**: _resolve_time() で 1〜6時を13〜18時（午後）として解釈
- **祝日対応**: _is_japanese_holiday() を純Python実装（固定祝日・ハッピーマンデー・春分/秋分近似式・振替休日・国民の休日）、2026〜2030年で検証済み
- **ブリーフィング耐障害性**: morning_briefing() に3回リトライ（30秒/60秒待機）+ 全失敗時ユーザー通知Push
- **Geminiレート制限**: _generate_gemini() に指数バックオフ（2/4/8秒）3回リトライ実装
- **PIIフィルタ強化**: クレジットカード（16桁）・マイナンバー（12桁）・銀行口座番号パターン追加、長いパターン優先でマッチ順序修正
