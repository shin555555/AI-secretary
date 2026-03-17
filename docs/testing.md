# テスト手順

## 手動テストチェックリスト（リリース前に全項目確認）

### Phase 1: LINE疎通
- [ ] LINEから「こんにちは」→ エコー返信が返る
- [ ] 不正な署名リクエスト → 403エラー

### Phase 2: AI会話
- [ ] LINEから「こんにちは」→ 凛が自然な日本語で応答
- [ ] 意味不明なメッセージ → 確認質問で返す
- [ ] Ollama停止状態 → Geminiにフォールバックし応答
- [ ] **Gemini送信ログに個人情報が含まれないこと**（security.md参照）

### Phase 3: カレンダー
- [ ] 「今日の予定は？」→ Googleカレンダーの実データ表示
- [ ] 「今週の予定」→ 1週間分の予定表示
- [ ] 「明日14時に○○さん面談」→ カレンダーに登録される
- [ ] 既存予定と重複する時間 → 警告メッセージ

### Phase 4: タスク管理
- [ ] 「タスク追加：報告書作成 金曜まで」→ タスク登録確認
- [ ] 「タスク一覧」→ 未完了タスク表示（優先度順）
- [ ] 「タスク1完了」→ ステータス更新
- [ ] 「次何やる？」→ 優先度考慮した提案
- [ ] 朝8:00 → LINEにブリーフィング通知到着
- [ ] 期限前日 → リマインド通知

### Phase 5: パーソナライズ
- [ ] 「覚えて：国保連請求は毎月10日」→ 好み保存
- [ ] 次回会話で設定が反映される
- [ ] 直近10ターンの会話コンテキストが維持される

### Phase 6: 安定性
- [ ] PC再起動後にサービスが自動起動
- [ ] Google Calendar API エラー時 → タスク機能のみ動作
- [ ] LINE API エラー時 → エラーログ記録・graceful degradation

---

## ユニットテスト実行

```bash
# 全テスト実行
pytest tests/ -v

# 特定ファイルのみ
pytest tests/test_pii_filter.py -v
pytest tests/test_task_service.py -v
```

---

## LINEテスト用コマンド（scripts/test_line_reply.py）

```bash
# 手動でLINEにメッセージ送信テスト
python scripts/test_line_reply.py --message "テストメッセージ"

# 朝ブリーフィングを今すぐ実行
python scripts/test_line_reply.py --briefing
```
