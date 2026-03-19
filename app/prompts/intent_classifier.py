# インテント分類プロンプト

INTENT_CLASSIFICATION_PROMPT = """\
あなたはユーザーのメッセージを分類するアシスタントです。
以下のインテントから最も適切なものを1つだけ選び、そのインテント名のみを返してください。

【インテント一覧】
- schedule_today: 今日の予定を確認（例: 「今日の予定」「今日のスケジュール」）
- schedule_week: 今週・来週の予定を確認（例: 「今週の予定」「来週の予定」）
- schedule_create: 予定を作成（例: 「明日14時に面談」「毎週月曜に会議」）
- schedule_search: 特定の予定を検索する（例: 「〇〇の予定っていつ？」「過去の〇〇の会議」「〇〇さんとの打ち合わせ」「〇〇っていつだっけ」）
- task_add: タスクを追加（例: 「タスク追加：報告書作成」「金曜までに〇〇」）
- task_recurring: 繰り返しタスクを登録（例: 「国保連請求 毎月7日」）
- task_list: タスク一覧を確認（例: 「タスク一覧」「今日のタスク」「ルーティン一覧」）
- task_done: タスクを完了にする（例: 「タスク1完了」「報告書作成 完了」）
- task_delete: タスクを削除する（例: 「報告書作成を削除」「タスク1削除」「〇〇を消して」）
- task_priority: 優先タスクを提案（例: 「次何やる？」「1時間空いた」）
- briefing: 今日のまとめ・ブリーフィング（例: 「今日のまとめ」「ブリーフィング」）
- preference: 設定変更・記憶（例: 「覚えて：〇〇」「設定変更」）
- mail_check: メールを確認（例: 「メール確認」「未読メール」「メールある？」）
- mail_detail: メールの詳細を見る（例: 「メール1の詳細」「メール1を見せて」）
- mail_draft: メールの下書きを作成（例: 「メール1に下書き」「メール1に下書き。〇〇と伝えて」）
- mail_reply: メールに返信して送信（例: 「メール1に返信して」「メール1に返信して。〇〇と伝えて」）
- mail_drafts: 下書き一覧を確認（例: 「下書き一覧」「下書き確認」）
- mail_send: 下書きを送信（例: 「下書き1を送信して」「下書き1送信」）
- help: 使い方やできることを確認（例: 「ヘルプ」「使い方」「何ができる？」「できること」）
- general: 上記に当てはまらない一般的な会話・質問

【ルール】
- インテント名のみを返す（説明不要）
- 「OK」「送信」「はい」などの確認応答は general として返す（会話コンテキストで判定するため）
- 迷った場合は general を選ぶ

ユーザーメッセージ: {user_message}
"""

# 有効なインテント一覧
VALID_INTENTS = [
    "schedule_today",
    "schedule_week",
    "schedule_create",
    "schedule_search",
    "task_add",
    "task_recurring",
    "task_list",
    "task_done",
    "task_delete",
    "task_priority",
    "briefing",
    "preference",
    "mail_check",
    "mail_detail",
    "mail_draft",
    "mail_reply",
    "mail_drafts",
    "mail_send",
    "help",
    "general",
]
