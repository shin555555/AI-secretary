"""Quick Tunnel起動 + LINE Webhook URL自動更新スクリプト"""

import re
import subprocess
import sys
import time

import httpx

CLOUDFLARED_PATH = r"C:\Program Files (x86)\cloudflared\cloudflared.exe"
LOCAL_URL = "http://localhost:8000"
WEBHOOK_PATH = "/webhook/line"
MAX_WAIT_SECONDS = 30


def get_line_token() -> str:
    """環境変数または.envからLINE_CHANNEL_ACCESS_TOKENを取得"""
    import os
    from pathlib import Path

    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    if token:
        return token

    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("LINE_CHANNEL_ACCESS_TOKEN="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def update_line_webhook(tunnel_url: str, token: str) -> bool:
    """LINE Messaging APIのWebhook URLを更新"""
    webhook_url = f"{tunnel_url}{WEBHOOK_PATH}"
    try:
        resp = httpx.put(
            "https://api.line.me/v2/bot/channel/webhook/endpoint",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"endpoint": webhook_url},
            timeout=10,
        )
        if resp.status_code == 200:
            print(f"[OK] LINE Webhook URL updated: {webhook_url}")
            return True
        else:
            print(f"[ERROR] LINE API response: {resp.status_code} {resp.text}")
            return False
    except Exception as e:
        print(f"[ERROR] Failed to update LINE webhook: {e}")
        return False


def verify_webhook(tunnel_url: str, token: str) -> bool:
    """LINE Webhook URLが正しく設定されたか検証"""
    try:
        resp = httpx.get(
            "https://api.line.me/v2/bot/channel/webhook/endpoint",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if resp.status_code == 200:
            current = resp.json().get("endpoint", "")
            expected = f"{tunnel_url}{WEBHOOK_PATH}"
            if current == expected:
                print(f"[OK] Webhook URL verified: {current}")
                return True
            else:
                print(f"[ERROR] Webhook URL mismatch! expected={expected}, actual={current}")
                return False
    except Exception as e:
        print(f"[WARN] Webhook verification failed: {e}")
    return False


def main() -> None:
    token = get_line_token()
    if not token:
        print("[ERROR] LINE_CHANNEL_ACCESS_TOKEN not found in .env")
        sys.exit(1)

    print("[INFO] Starting Cloudflare Quick Tunnel...")
    process = subprocess.Popen(
        [CLOUDFLARED_PATH, "tunnel", "--url", LOCAL_URL],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    tunnel_url = None
    start_time = time.time()

    try:
        for line in iter(process.stdout.readline, ""):
            print(f"  [cloudflared] {line.rstrip()}")

            # trycloudflare.com URLを検出
            match = re.search(r"(https://[a-zA-Z0-9-]+\.trycloudflare\.com)", line)
            if match:
                tunnel_url = match.group(1)
                print(f"\n[OK] Tunnel URL: {tunnel_url}")
                break

            if time.time() - start_time > MAX_WAIT_SECONDS:
                print("[ERROR] Timeout waiting for tunnel URL")
                process.terminate()
                sys.exit(1)

        if tunnel_url:
            webhook_updated = False

            for attempt in range(5):
                wait_sec = 3 + attempt * 2
                print(f"[INFO] Waiting {wait_sec}s for tunnel to stabilize (attempt {attempt + 1}/5)...")
                time.sleep(wait_sec)

                # health check（ローカル→トンネル経由の順で確認）
                try:
                    local_resp = httpx.get(f"{LOCAL_URL}/health", timeout=5)
                    if local_resp.status_code != 200:
                        print(f"[WARN] Local health check returned {local_resp.status_code}, retrying...")
                        continue
                except Exception as e:
                    print(f"[WARN] Local health check failed: {e}, retrying...")
                    continue

                try:
                    resp = httpx.get(f"{tunnel_url}/health", timeout=10)
                    if resp.status_code != 200:
                        print(f"[WARN] Tunnel health check returned {resp.status_code}, retrying...")
                        continue
                except Exception as e:
                    print(f"[WARN] Tunnel health check failed: {e} (DNS may not be ready, proceeding anyway)")

                print("[OK] Health check passed")

                # webhook URL更新
                if update_line_webhook(tunnel_url, token):
                    # 更新後に検証
                    if verify_webhook(tunnel_url, token):
                        webhook_updated = True
                        break
                    else:
                        print("[WARN] Verification failed, retrying...")

            if not webhook_updated:
                print("")
                print("=" * 60)
                print("[CRITICAL] LINE Webhook URL の更新に失敗しました！")
                print("LINE からのメッセージを受信できません。")
                print("")
                print("手動で以下のURLを設定してください:")
                print(f"  {tunnel_url}{WEBHOOK_PATH}")
                print("")
                print("LINE Developers Console:")
                print("  https://developers.line.biz/console/")
                print("=" * 60)
                print("")

            print("\n[INFO] Tunnel is running. Press Ctrl+C to stop.")
            # トンネルプロセスを維持
            process.wait()

    except KeyboardInterrupt:
        print("\n[INFO] Shutting down tunnel...")
        process.terminate()
        process.wait()


if __name__ == "__main__":
    main()
