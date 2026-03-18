import logging

from fastapi import APIRouter, Header, HTTPException, Request
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhook import WebhookParser
from linebot.v3.webhooks import MessageEvent, TextMessageContent

from config.settings import settings
from app.services.secretary import secretary

logger = logging.getLogger(__name__)

router = APIRouter()

configuration = Configuration(access_token=settings.line_channel_access_token)
parser = WebhookParser(channel_secret=settings.line_channel_secret)


@router.post("/webhook/line")
async def line_webhook(
    request: Request,
    x_line_signature: str = Header(...),
) -> dict[str, str]:
    body = (await request.body()).decode("utf-8")

    # 署名検証
    try:
        events = parser.parse(body, x_line_signature)
    except InvalidSignatureError:
        logger.warning("LINE署名検証失敗")
        raise HTTPException(status_code=403, detail="Invalid signature")

    for event in events:
        if not isinstance(event, MessageEvent):
            continue
        if not isinstance(event.message, TextMessageContent):
            continue

        # アクセス制限: 登録済みユーザーのみ応答
        user_id = event.source.user_id
        if settings.line_user_id and user_id != settings.line_user_id:
            logger.warning(f"未登録ユーザーからのメッセージを無視: user_id={user_id[:8]}...")
            continue

        user_message = event.message.text
        logger.info(f"受信: {user_message[:50]}")

        # Phase 2: 凛（AI秘書）が応答を生成
        try:
            reply_text = await secretary.handle_message(user_message)
        except Exception as e:
            logger.error(f"応答生成エラー: {e}")
            reply_text = "申し訳ございません、処理中にエラーが発生しました。もう一度お試しください。"

        with ApiClient(configuration) as api_client:
            messaging_api = MessagingApi(api_client)
            messaging_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply_text)],
                )
            )

    return {"status": "ok"}
