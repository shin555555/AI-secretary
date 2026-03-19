"""LINEリッチメニューのセットアップスクリプト

B案: 2行3列（上段=カレンダー系、下段=タスク系）
  📅 今日の予定 | 🗓️ 週間予定  | 📝 予定追加
  📋 タスク一覧 | ➕ タスク追加 | ✅ ブリーフィング
"""

import json
import os
import sys
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFont

# プロジェクトルート
PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_DIR))

MENU_IMAGE_PATH = PROJECT_DIR / "data" / "rich_menu.png"

# リッチメニューサイズ（LINE仕様: 2500x1686 for 2行）
WIDTH = 2500
HEIGHT = 1686
COLS = 3
ROWS = 2
CELL_W = WIDTH // COLS
CELL_H = HEIGHT // ROWS

# ボタン定義（B案）
BUTTONS = [
    # 上段: カレンダー系（統一ブルー）
    {"label": "今日の予定", "emoji": "\U0001f4c5", "text": "今日の予定は？",
     "bg": "#4A90D9"},
    {"label": "週間予定", "emoji": "\U0001f5d3", "text": "今日から1週間の予定教えて",
     "bg": "#4A90D9"},
    {"label": "予定追加", "emoji": "\U0001f4dd", "text": "予定を追加したい",
     "bg": "#4A90D9"},
    # 下段: タスク系（統一グリーン）
    {"label": "タスク一覧", "emoji": "\U0001f4cb", "text": "タスク一覧",
     "bg": "#2ECC71"},
    {"label": "タスク追加", "emoji": "➕", "text": "タスクを追加したい",
     "bg": "#2ECC71"},
    {"label": "ブリーフィング", "emoji": "✅", "text": "ブリーフィング",
     "bg": "#2ECC71"},
]


def get_line_token() -> str:
    """LINE_CHANNEL_ACCESS_TOKEN を取得"""
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    if token:
        return token

    env_file = PROJECT_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("LINE_CHANNEL_ACCESS_TOKEN="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def find_font(size: int = 96) -> ImageFont.FreeTypeFont:
    """日本語フォントを検索"""
    font_candidates = [
        "C:/Windows/Fonts/meiryob.ttc",
        "C:/Windows/Fonts/meiryo.ttc",
        "C:/Windows/Fonts/YuGothB.ttc",
        "C:/Windows/Fonts/msgothic.ttc",
    ]
    for path in font_candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size=size)

    return ImageFont.load_default()


def find_emoji_font(size: int = 160) -> ImageFont.FreeTypeFont | None:
    """絵文字フォントを検索"""
    emoji_candidates = [
        "C:/Windows/Fonts/seguiemj.ttf",
    ]
    for path in emoji_candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                continue
    return None


def generate_menu_image() -> Path:
    """リッチメニュー画像を生成"""
    img = Image.new("RGB", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(img)

    font_label = find_font(size=96)
    emoji_font_large = find_emoji_font(size=160)
    font_fallback = find_font(size=160)

    for i, btn in enumerate(BUTTONS):
        col = i % COLS
        row = i // COLS
        x0 = col * CELL_W
        y0 = row * CELL_H
        x1 = x0 + CELL_W
        y1 = y0 + CELL_H

        # 背景色を塗る
        draw.rectangle([x0, y0, x1, y1], fill=btn["bg"])

        # 枠線（セル間の区切り）
        draw.rectangle([x0, y0, x1, y1], outline="#FFFFFF", width=4)

        cx = x0 + CELL_W // 2
        cy = y0 + CELL_H // 2

        # 絵文字を描画
        emoji_text = btn["emoji"]
        e_font = emoji_font_large or font_fallback
        try:
            ebbox = draw.textbbox((0, 0), emoji_text, font=e_font)
            ew = ebbox[2] - ebbox[0]
            eh = ebbox[3] - ebbox[1]
            draw.text((cx - ew // 2, cy - eh - 30), emoji_text, font=e_font, fill="#FFFFFF")
        except Exception:
            draw.text((cx - 80, cy - 190), emoji_text, font=font_fallback, fill="#FFFFFF")

        # ラベルを描画
        label = btn["label"]
        lbbox = draw.textbbox((0, 0), label, font=font_label)
        lw = lbbox[2] - lbbox[0]
        draw.text((cx - lw // 2, cy + 60), label, font=font_label, fill="#FFFFFF")

    MENU_IMAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(MENU_IMAGE_PATH))
    print(f"[OK] Menu image saved: {MENU_IMAGE_PATH}")
    return MENU_IMAGE_PATH


def create_rich_menu(token: str) -> str | None:
    """LINE APIでリッチメニューを作成し、IDを返す"""
    areas = []
    for i, btn in enumerate(BUTTONS):
        col = i % COLS
        row = i // COLS
        areas.append({
            "bounds": {
                "x": col * CELL_W,
                "y": row * CELL_H,
                "width": CELL_W,
                "height": CELL_H,
            },
            "action": {
                "type": "message",
                "label": btn["label"],
                "text": btn["text"],
            },
        })

    body = {
        "size": {"width": WIDTH, "height": HEIGHT},
        "selected": True,
        "name": "凛メニュー",
        "chatBarText": "メニュー",
        "areas": areas,
    }

    resp = httpx.post(
        "https://api.line.me/v2/bot/richmenu",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=body,
        timeout=10,
    )

    if resp.status_code == 200:
        menu_id = resp.json().get("richMenuId")
        print(f"[OK] Rich menu created: {menu_id}")
        return menu_id
    else:
        print(f"[ERROR] Failed to create rich menu: {resp.status_code} {resp.text}")
        return None


def upload_menu_image(token: str, menu_id: str, image_path: Path) -> bool:
    """リッチメニュー画像をアップロード"""
    with open(image_path, "rb") as f:
        resp = httpx.post(
            f"https://api-data.line.me/v2/bot/richmenu/{menu_id}/content",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "image/png",
            },
            content=f.read(),
            timeout=30,
        )

    if resp.status_code == 200:
        print("[OK] Menu image uploaded")
        return True
    else:
        print(f"[ERROR] Failed to upload image: {resp.status_code} {resp.text}")
        return False


def set_default_menu(token: str, menu_id: str) -> bool:
    """リッチメニューをデフォルトに設定"""
    resp = httpx.post(
        f"https://api.line.me/v2/bot/user/all/richmenu/{menu_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )

    if resp.status_code == 200:
        print("[OK] Rich menu set as default")
        return True
    else:
        print(f"[ERROR] Failed to set default: {resp.status_code} {resp.text}")
        return False


def delete_existing_menus(token: str) -> None:
    """既存のリッチメニューを削除"""
    resp = httpx.get(
        "https://api.line.me/v2/bot/richmenu/list",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )

    if resp.status_code == 200:
        menus = resp.json().get("richmenus", [])
        for menu in menus:
            mid = menu["richMenuId"]
            httpx.delete(
                f"https://api.line.me/v2/bot/richmenu/{mid}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            print(f"[OK] Deleted old menu: {mid}")


def main() -> None:
    print("=== LINE Rich Menu Setup (B案) ===\n")

    token = get_line_token()
    if not token:
        print("[ERROR] LINE_CHANNEL_ACCESS_TOKEN not found")
        sys.exit(1)

    # 1. 既存メニュー削除
    print("Step 1: Cleaning up existing menus...")
    delete_existing_menus(token)

    # 2. 画像生成
    print("\nStep 2: Generating menu image...")
    image_path = generate_menu_image()

    # 3. リッチメニュー作成
    print("\nStep 3: Creating rich menu...")
    menu_id = create_rich_menu(token)
    if not menu_id:
        sys.exit(1)

    # 4. 画像アップロード
    print("\nStep 4: Uploading menu image...")
    if not upload_menu_image(token, menu_id, image_path):
        sys.exit(1)

    # 5. デフォルトに設定
    print("\nStep 5: Setting as default menu...")
    if not set_default_menu(token, menu_id):
        sys.exit(1)

    print("\n=== Setup Complete ===")
    print(f"Rich Menu ID: {menu_id}")
    print("LINEアプリでトーク画面を開くと、メニューが表示されます。")


if __name__ == "__main__":
    main()
