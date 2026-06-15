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
    header = f"📰 *{now.month}/{now.day} 건기식 뉴스*"

    if not summaries:
        body_text = f"{header}\n오늘은 주목할 만한 건기식 뉴스가 없습니다."
    else:
        body_text = f"{header} · 총 {len(summaries)}건"

    try:
        # unfurl_*=False: 슬랙이 링크를 큰 미리보기 카드로 자동 전개하는 것을 막아
        # 우리가 만든 요약과 카드가 중복 노출되는 가독성 저하를 방지한다.
        response = client.chat_postMessage(
            channel=channel_id,
            text=body_text,
            unfurl_links=False,
            unfurl_media=False,
        )
    except SlackApiError as e:
        logger.error("Slack API 오류 (본문 메시지): %s", e)
        return

    if not summaries:
        return

    ts = response["ts"]

    for article in summaries[:10]:  # 최대 10개 main 기사 (supplement는 각 메시지에 포함)
        thread_text = _format_article(article)
        try:
            client.chat_postMessage(
                channel=channel_id,
                text=thread_text,
                thread_ts=ts,
                unfurl_links=False,
                unfurl_media=False,
            )
        except SlackApiError as e:
            logger.error("Slack API 오류 (스레드 메시지): %s", e)
            return


def _format_article(article: SummarizedArticle) -> str:
    """단일 기사(+ 보완 기사 포함)를 Slack 메시지 텍스트로 포맷.

    제목을 원문 링크로 걸고(unfurl은 notify에서 비활성화) 출처·3줄 요약을 잇는다.
    보완 기사도 제목 링크 + 3줄 요약을 유지하되 '└ 연관기사' 구분만 둔다.
    """
    lines = [
        f"*<{article.url}|{article.headline}>*",
        article.keyword_source,
        article.summary,
    ]

    for sup in article.supplements:
        label = f" [{sup.relation_label}]" if sup.relation_label else ""
        lines.append("")
        lines.append(f"└ 연관기사{label}")
        lines.append(f"*<{sup.url}|{sup.headline}>*")
        lines.append(sup.summary)

    return "\n".join(lines)
