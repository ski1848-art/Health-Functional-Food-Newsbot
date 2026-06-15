import logging
import os
from datetime import datetime

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from models import SummarizedArticle

logger = logging.getLogger(__name__)

# 보완 관계 레이블별 이모지
_RELATION_EMOJI = {
    "규제 동향": "⚖️",
    "시장 반응": "📈",
    "연구 근거": "🔬",
    "소비자 트렌드": "👥",
    "경쟁사 동향": "🏢",
}
_DEFAULT_SUPPLEMENT_EMOJI = "🔗"


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
        grouped = [s for s in summaries if s.supplements]
        body_text = (
            f"{header}\n"
            f"📰 총 {len(summaries)}건"
            + (f"  |  🔗 연관 그룹 {len(grouped)}개" if grouped else "")
        )

    try:
        response = client.chat_postMessage(channel=channel_id, text=body_text)
    except SlackApiError as e:
        logger.error("Slack API 오류 (본문 메시지): %s", e)
        return

    if not summaries:
        return

    ts = response["ts"]

    for article in summaries[:10]:  # 최대 10건
        thread_text = _format_article(article)
        try:
            client.chat_postMessage(channel=channel_id, text=thread_text, thread_ts=ts)
        except SlackApiError as e:
            logger.error("Slack API 오류 (스레드 메시지): %s", e)
            return


def _format_article(article: SummarizedArticle) -> str:
    """단일 기사(+ 보완 기사 포함)를 Slack 메시지 텍스트로 포맷."""
    lines = [
        f"*{article.keyword_source} {article.headline}*",
        article.summary,
        f"<{article.url}|🔗 원문 보기>",
    ]

    if article.supplements:
        lines.append("")
        lines.append("*📎 연관 기사*")
        for sup in article.supplements:
            emoji = _RELATION_EMOJI.get(sup.relation_label or "", _DEFAULT_SUPPLEMENT_EMOJI)
            label = f"[{sup.relation_label}]" if sup.relation_label else ""
            lines.append(f"{emoji} {label} *{sup.headline}*")
            lines.append(sup.summary)
            lines.append(f"<{sup.url}|🔗 원문 보기>")

    return "\n".join(lines)
