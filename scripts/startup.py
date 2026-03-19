"""ヘッドレス起動スクリプト（タスクスケジューラ用）

GUIウィンドウなしでサーバーとトンネルを起動する。
ロック画面・ログオフ状態でも動作する。
"""

import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
PYTHON = PROJECT_DIR / ".venv" / "Scripts" / "python.exe"
LOG_DIR = PROJECT_DIR / "data" / "logs"


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
    tunnel_log = open(LOG_DIR / "tunnel_stdout.log", "a", encoding="utf-8")
    tunnel = subprocess.Popen(
        [str(PYTHON), str(PROJECT_DIR / "scripts" / "start_tunnel.py")],
        cwd=str(PROJECT_DIR),
        stdout=tunnel_log,
        stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    log(f"Tunnel started (PID: {tunnel.pid})")

    # PIDファイルを書き出し（stop用）
    pid_file = PROJECT_DIR / "data" / "server.pid"
    pid_file.write_text(f"{server.pid}\n{tunnel.pid}", encoding="utf-8")

    # サーバープロセスが終了するまで待機
    try:
        server.wait()
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
        tunnel_log.close()
        if pid_file.exists():
            pid_file.unlink()
        log("Rin AI Secretary stopped.")


if __name__ == "__main__":
    main()
