# セキュリティルール【最重要】

このプロジェクトは就労継続支援事業所の利用者個人情報を扱う。セキュリティは最優先事項。

## 個人情報（PII）の取扱い

### 絶対ルール
- **外部API（Gemini等）に個人情報を送信しない** — 必ず `pii_filter.py` を通す
- 利用者の氏名・受給者証番号・電話番号・住所は `SQLCipher` 暗号化DB内のみに保存
- ログファイルに個人情報を出力しない
- エラーメッセージに個人情報を含めない

### PIIフィルタの適用
```python
# NG: 直接Geminiに送信
response = await gemini.generate(user_message)

# OK: PIIフィルタを通してから送信
filtered_message = pii_filter.redact(user_message)
response = await gemini.generate(filtered_message)
restored_response = pii_filter.restore(response)
```

## 秘密情報の管理

### .env ファイル
- `.env` は **絶対にgitにコミットしない**（.gitignore必須）
- `.env.example` にはダミー値のみ記載
- APIキー・トークンはすべて環境変数経由で読み込む（Pydantic Settings）

### コード内のハードコード禁止
```python
# NG
LINE_CHANNEL_SECRET = "abc123secret"

# OK
from config.settings import settings
LINE_CHANNEL_SECRET = settings.line_channel_secret
```

### DB暗号化鍵
- SQLCipherの暗号化鍵は OS キーリング（`keyring`）に保存
- コード・環境変数・ファイルに直接書かない

## 認証・アクセス制御
- LINE Webhook は `X-Line-Signature` のHMAC-SHA256検証を必ず行う
- LINE UserID で自分のみ応答するよう制限（他ユーザーのメッセージは無視）
- Google OAuth2 トークンは暗号化して保存

## コードレビュー時のチェック項目
新しいコードを書く際、以下を必ず確認：
1. 外部APIに送るデータに個人情報が含まれていないか？
2. `.env` に新しい秘密情報を追加した場合、`.env.example` も更新したか？
3. ログ出力に個人情報が混入していないか？
4. 新しいエンドポイントに認証チェックがあるか？
