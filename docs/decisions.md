# 設計上の決定・メモ

開発中の重要な決定や判断をここに記録する。

---

## 2026-03-17

### AI秘書の名前: 凛（りん）
- ユーザー希望: しっかりした女性秘書
- 選定理由: 凛とした佇まい、的確で頼れるイメージが業務秘書として最適
- 口調: 丁寧語（ですます調）、簡潔で的確

### LLM戦略: ローカル + クラウドハイブリッド
- 普段: Ollama（gemma2:9b）でローカル処理 → 個人情報がPCから出ない
- 外出時・Ollama停止時: Gemini API（無料枠）にフォールバック
- Gemini送信前: PIIフィルタで個人情報をプレースホルダ置換

### DB暗号化: SQLCipher
- Windows環境でのインストールが困難な場合の代替案:
  - 標準SQLite + cryptography（Fernet）による列レベル暗号化
  - 優先: SQLCipher を試して、失敗したら代替案に切り替え

### LINE Push 200通/月制限の対策
- バッチ化: 朝ブリーフィングに1日分をまとめる（〜30通/月）
- リマインドは期限24時間前のみ（個別）
- 合計 50〜80通/月 を想定 → 200通以内に収まる予定

### Cloudflare Tunnel（ngrokの代替）
- ngrokは無料枠でURL変更のたびにLINE Webhook設定更新が必要
- Cloudflare Tunnel: 安定URL + 無料 + 自動TLSで優位

---

### Claudeルール設定（ai-behavior.md）
- 回答スタイル: 簡潔重視（コード中心）
- 自律度: 基本お任せ（requirements.mdに沿って進め、問題時のみ報告）
- コード: 変数・関数名は英語、コメントは日本語
- セキュリティ: 全項目最高レベル（PII・外部API・.env管理）

### GitHub リポジトリ
- URL: https://github.com/shin555555/AI-secretary.git
- ブランチ: master
- 除外設定: .env, data/, *.db を .gitignore で除外

### プロジェクト現在地（2026-03-17）
- 実装コードはまだ0行
- 次のアクション: Phase 0 環境構築（docs/setup.md 参照）

## 2026-03-18

### 繰り返しタスク・繰り返し予定機能の追加（UX改善）
- **背景**: 月次業務（国保連請求等）を毎回手動追加するのはストレスとなるため追加
- **繰り返しタスク（ローカルDB）**: recurring_tasksテーブルで定義 → APSchedulerが毎日0:00に自動生成
- **繰り返し予定（Google Calendar）**: Google Calendar の RRULE 形式で登録・管理
- **対応パターン**: 毎日/毎週/毎月/隔月/X月ごと/毎年
- **LINEからの管理**: ルーティン一覧・削除・変更コマンドを追加

### DB方針: 標準SQLite先行
- SQLCipherはWindows環境でのインストールが複雑なため、まず標準SQLiteで実装
- 暗号化はPhase 6（安定化）で検討（SQLCipher or Fernet列レベル暗号化）
- data/secretary.db に配置（.gitignore対象）

### 会話コンテキスト: Phase 5から前倒し実装
- memory_service.py と直近10ターンのコンテキスト記憶をPhase 2で先行実装
- 理由: LLM会話の品質にコンテキストが大きく影響するため、早期に組み込み

## 2026-03-19

### LINE Loadingアニメーション導入（UX改善）
- **背景**: LLM応答生成に数秒かかる間、LINE画面で何も反応がなく「ちゃんと動いているか」不安になる
- **採用案**: LINE Messaging APIの `show_loading_animation`（チャット画面に「入力中…」風の3点アニメーション表示）
- **却下案**: 即時テキスト一次応答（「少々お待ちください」）→ Push APIの月200通制限を消費するため不採用
- **実装**: Webhook受信直後に `loading_seconds=20` で呼び出し、Reply送信時に自動消滅
- **障害時**: Loading表示失敗しても処理は継続（グレースフルデグラデーション）

_（開発中に新しい決定が生じたらここに追記）_
