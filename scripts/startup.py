"""ヘッドレス起動スクリプト（タスクスケジューラ用）

GUIウィンドウなしでサーバーとトンネルを起動する。
ロック画面・ログオフ状態でも動作する。
トンネル死活監視付き：切断時は自動再起動+Webhook URL再設定。
"""

import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
PYTHON = PROJECT_DIR / ".venv" / "Scripts" / "python.exe"
LOG_DIR = PROJECT_DIR / "data" / "logs"

TUNNEL_CHECK_INTERVAL = 60  # トンネル死活チェック間隔（秒）
WEBHOOK_VERIFY_INTERVAL = 300  # Webhook疎通チェック間隔（秒）


def log(msg: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}\n"
    print(line, end="")
    with open(LOG_DIR / "startup.log", "a", encoding="utf-8") as f:
        f.write(line)


def is_port_in_use(port: int) -> bool:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0


def start_tunnel() -> subprocess.Popen:
    """トンネルプロセスを起動して返す"""
    tunnel_log = open(LOG_DIR / "tunnel_stdout.log", "a", encoding="utf-8")
    tunnel = subprocess.Popen(
        [str(PYTHON), str(PROJECT_DIR / "scripts" / "start_tunnel.py")],
        cwd=str(PROJECT_DIR),
        stdout=tunnel_log,
        stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    log(f"Tunnel started (PID: {tunnel.pid})")
    return tunnel


def verify_webhook_reachable() -> bool:
    """LINE Webhook疎通テスト（LINE APIから実際にリクエストを送信）"""
    try:
        import httpx

        sys.path.insert(0, str(PROJECT_DIR))
        from scripts.start_tunnel import get_line_token

        token = get_line_token()
        if not token:
            return False

        # 現在のWebhook URLを取得
        resp = httpx.get(
            "https://api.line.me/v2/bot/channel/webhook/endpoint",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if resp.status_code != 200:
            return False

        endpoint = resp.json().get("endpoint", "")
        if not endpoint:
            return False

        # 疎通テスト
        resp2 = httpx.post(
            "https://api.line.me/v2/bot/channel/webhook/test",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"endpoint": endpoint},
            timeout=15,
        )
        if resp2.status_code == 200:
            result = resp2.json()
            return result.get("success", False)
    except Exception as e:
        log(f"Webhook verify error: {e}")
    return False


def main() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # 既にサーバーが起動していたらスキップ
    if is_port_in_use(8000):
        log("Server already running on port 8000. Skipping.")
        return

    log("Starting Rin AI Secretary (headless mode)...")

    # サーバー起動（CREATE_NO_WINDOW でウィンドウなし）
    server_log = open(LOG_DIR / "server_stdout.log", "a", encoding="utf-8")
    server = subprocess.Popen(
        [
            str(PYTHON),
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
        ],
        cwd=str(PROJECT_DIR),
        stdout=server_log,
        stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    log(f"Server started (PID: {server.pid})")

    # サーバーの起動を待つ
    for i in range(10):
        time.sleep(1)
        if is_port_in_use(8000):
            log("Server is ready on port 8000")
            break
    else:
        log("WARNING: Server did not start within 10 seconds")

    # トンネル起動
    tunnel = start_tunnel()

    # PIDファイルを書き出し（stop用）
    pid_file = PROJECT_DIR / "data" / "server.pid"
    pid_file.write_text(f"{server.pid}\n{tunnel.pid}", encoding="utf-8")

    # メインループ: サーバー＋トンネル監視
    last_webhook_check = time.time()
    tunnel_restart_count = 0

    try:
        while True:
            # サーバーが死んだら全体終了
            if server.poll() is not None:
                log(f"Server process exited (code: {server.returncode}). Shutting down.")
                break

            # トンネルが死んだら再起動
            if tunnel.poll() is not None:
                tunnel_restart_count += 1
                log(f"Tunnel process died (code: {tunnel.returncode}). Restarting... (attempt #{tunnel_restart_count})")

                if tunnel_restart_count > 10:
                    log("ERROR: Tunnel restarted too many times. Waiting 5 minutes before retry.")
                    time.sleep(300)
                    tunnel_restart_count = 0

                time.sleep(5)
                tunnel = start_tunnel()
                pid_file.write_text(f"{server.pid}\n{tunnel.pid}", encoding="utf-8")
                last_webhook_check = time.time()  # 再起動直後はWebhookチェックをスキップ

            # 定期Webhook疎通チェック
            now = time.time()
            if now - last_webhook_check >= WEBHOOK_VERIFY_INTERVAL:
                last_webhook_check = now
                if not verify_webhook_reachable():
                    log("WARNING: Webhook is not reachable! Restarting tunnel...")
                    tunnel.terminate()
                    try:
                        tunnel.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        tunnel.kill()
                    time.sleep(3)
                    tunnel = start_tunnel()
                    tunnel_restart_count += 1
                    pid_file.write_text(f"{server.pid}\n{tunnel.pid}", encoding="utf-8")
                else:
                    log("Webhook health check: OK")

            time.sleep(TUNNEL_CHECK_INTERVAL)

    except KeyboardInterrupt:
        log("Shutting down...")
    finally:
        server.terminate()
        tunnel.terminate()
        try:
            server.wait(timeout=5)
            tunnel.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            tunnel.kill()
        server_log.close()
        if pid_file.exists():
            pid_file.unlink()
        log("Rin AI Secretary stopped.")


if __name__ == "__main__":
    main()
