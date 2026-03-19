import logging
import os
from datetime import datetime

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from models import SummarizedArticle

logger = logging.getLogger(__name__)


def notify(summaries: list[SummarizedArticle]) -> None:
    """Slack 채널에 본문 메시지 + 스레드 발송."""
    token = os.environ.get("SLACK_BOT_TOKEN")
    channel_id = os.environ.get("SLACK_CHANNEL_ID")

    client = WebClient(token=token)

    now = datetime.now()
    header = f"[{now.month}/{now.day} 건기식 뉴스 봇]"

    if not summaries:
        body_text = f"{header}\n오늘은 주목할 만한 건기식 뉴스가 없습니다."
    else:
        body_text = header

    try:
        response = client.chat_postMessage(channel=channel_id, text=body_text)
    except SlackApiError as e:
        logger.error("Slack API 오류 (본문 메시지): %s", e)
        return

    if not summaries:
        return

    ts = response["ts"]

    for article in summaries[:10]:  # 최대 10건
        thread_text = (
            f"*{article.keyword_source} {article.headline}*\n"
            f"{article.summary}\n"
            f"<{article.url}|🔗 링크 보기>"
        )
        try:
            client.chat_postMessage(channel=channel_id, text=thread_text, thread_ts=ts)
        except SlackApiError as e:
            logger.error("Slack API 오류 (스레드 메시지): %s", e)
            return
