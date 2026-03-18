import os
import sys

# プロジェクトルートパスを sys.path に追加して、config モジュールをインポートできるようにする
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from config.settings import settings

# アプリケーションに必要なスコープ
# ここでは Google Calendar の予定を読み書きする権限を要求します
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def main() -> None:
    print("=== Google Calendar API 認証セットアップ ===")
    
    # 認証情報JSONファイルのパスを確認
    credentials_path = settings.google_credentials_path
    if not os.path.exists(credentials_path):
        print(f"【エラー】 認証情報ファイルが見つかりません: {credentials_path}")
        print("Google Cloud ConsoleからダウンロードしたJSONファイルを")
        print(f"'{credentials_path}' として配置してください。")
        return

    # トークン保存先のパス
    token_path = settings.google_token_path

    creds = None
    # 既存のトークンがあれば読み込む
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    # 有効なトークンがない場合はログインフローを開始
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("既存のトークンをリフレッシュしています...")
            creds.refresh(Request())
        else:
            print("ブラウザでGoogleアカウントの認証を行います...")
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            # ローカルサーバーを立ち上げてコールバックを受け取る
            creds = flow.run_local_server(port=0)

        # 取得したトークンをファイルに保存
        with open(token_path, "w") as token:
            token.write(creds.to_json())
            print(f"認証成功！ トークンを保存しました: {token_path}")
    else:
        print(f"既に有効なトークンが存在します: {token_path}")


if __name__ == "__main__":
    main()
