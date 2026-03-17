# セットアップガイド（Phase 0）

## 前提条件

- Windows 11, Python 3.11+
- Git インストール済み
- インターネット接続

---

## 1. Ollama インストール

```bash
# https://ollama.com/download から Windows インストーラをDL・実行

# インストール後、モデルpull（いずれか選択）
ollama pull gemma2:9b-instruct-q5_K_M   # バランス型（推奨）
ollama pull qwen2.5:14b-instruct-q4_K_M # 日本語特化（重い）

# 動作確認
ollama run gemma2:9b-instruct-q5_K_M "こんにちは"
```

---

## 2. Python 仮想環境

```bash
cd C:\Users\user\Desktop\AI-secretary

# 仮想環境作成
python -m venv .venv

# 有効化（PowerShell）
.venv\Scripts\Activate.ps1

# 依存関係インストール（requirements.txt 作成後）
pip install -r requirements.txt
```

---

## 3. LINE 公式アカウント作成

1. [LINE Developers Console](https://developers.line.biz/) にアクセス
2. プロバイダー作成（例: 「凛AI秘書」）
3. 新規チャネル → **Messaging API** を選択
4. チャネル名: 「凛（りん）」
5. **チャネルアクセストークン（長期）** を発行 → `.env` に保存
6. **チャネルシークレット** をコピー → `.env` に保存
7. 設定変更:
   - 応答メッセージ: **OFF**
   - Webhook: **ON**
8. Webhook URL は Cloudflare Tunnel 設定後に入力

---

## 4. Google Cloud セットアップ

1. [Google Cloud Console](https://console.cloud.google.com/) にアクセス
2. 新規プロジェクト作成（例: 「ai-secretary」）
3. **Google Calendar API** を有効化
4. 認証情報 → **OAuth 2.0 クライアントID** 作成
   - アプリケーション種別: デスクトップアプリ
5. JSON をダウンロード → `data/google_credentials.json` に保存

---

## 5. Cloudflare Tunnel

```bash
# cloudflared をDLしてインストール
# https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/

# ログイン（ブラウザが開く）
cloudflared tunnel login

# トンネル作成
cloudflared tunnel create ai-secretary

# 起動テスト（ポート8000でFastAPIが動いている前提）
cloudflared tunnel --url http://localhost:8000

# 表示されたURLを LINE Webhook URL に設定
# 例: https://xxxx.trycloudflare.com/webhook/line
```

---

## 6. .env ファイル作成

```bash
cp .env.example .env
# .env を編集して各値を入力
```

`.env` の内容（`.env.example` から）:
```env
# LINE
LINE_CHANNEL_SECRET=your_channel_secret_here
LINE_CHANNEL_ACCESS_TOKEN=your_access_token_here
LINE_USER_ID=your_line_user_id_here  # 自分のユーザーID（botに話しかけてログで確認）

# Google
GOOGLE_CREDENTIALS_PATH=data/google_credentials.json
GOOGLE_TOKEN_PATH=data/google_token.json

# Gemini（フォールバック用）
GEMINI_API_KEY=your_gemini_api_key_here  # Google AI Studio で無料取得

# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gemma2:9b-instruct-q5_K_M

# APScheduler
BRIEFING_HOUR=8
BRIEFING_MINUTE=0

# アプリ設定
APP_HOST=0.0.0.0
APP_PORT=8000
LOG_LEVEL=INFO
```

---

## 7. 動作確認

```bash
# サーバー起動
python -m uvicorn app.main:app --reload --port 8000

# ヘルスチェック
curl http://localhost:8000/health
# → {"status": "ok"} が返れば成功
```
