"""
tests/test_notifier.py — notifier.py 단위 테스트
"""
import os
import sys
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

REQUIRED_VARS = {
    "OPENAI_API_KEY": "test-openai-key",
    "SLACK_BOT_TOKEN": "xoxb-test-token",
    "SLACK_CHANNEL_ID": "C12345678",
    "NAVER_CLIENT_ID": "test-naver-id",
    "NAVER_CLIENT_SECRET": "test-naver-secret",
}


class TestNotifyEmptySummaries:
    """6.4 test_notify_empty_summaries — 빈 목록 입력 시 '뉴스 없음' 메시지 발송 검증"""

    def test_notify_empty_summaries_sends_no_news_message(self):
        """빈 리스트 입력 시 '오늘은 주목할 만한 건기식 뉴스가 없습니다.' 포함 메시지가 발송되어야 한다."""
        mock_client = MagicMock()
        mock_client.chat_postMessage.return_value = {"ts": "1234567890.000001"}

        with patch.dict(os.environ, REQUIRED_VARS, clear=False):
            with patch("notifier.WebClient", return_value=mock_client):
                from notifier import notify
                notify([])

        assert mock_client.chat_postMessage.call_count == 1
        call_kwargs = mock_client.chat_postMessage.call_args
        text_arg = call_kwargs[1].get("text") or (call_kwargs[0][0] if call_kwargs[0] else call_kwargs[1]["text"])
        assert "오늘은 주목할 만한 건기식 뉴스가 없습니다." in text_arg

    def test_notify_empty_summaries_no_thread_messages(self):
        """빈 리스트 입력 시 스레드 메시지는 발송되지 않아야 한다."""
        mock_client = MagicMock()
        mock_client.chat_postMessage.return_value = {"ts": "1234567890.000001"}

        with patch.dict(os.environ, REQUIRED_VARS, clear=False):
            with patch("notifier.WebClient", return_value=mock_client):
                from notifier import notify
                notify([])

        # 본문 메시지 1번만 호출 (스레드 없음)
        assert mock_client.chat_postMessage.call_count == 1


class TestNotifySlackFailure:
    """6.5 test_notify_slack_failure — mock Slack 실패 시 로그 기록 후 종료 검증"""

    def test_notify_slack_failure_no_exception(self):
        """Slack API 실패 시 예외 없이 종료되어야 한다 (로그 기록 후 return)."""
        from slack_sdk.errors import SlackApiError

        mock_client = MagicMock()
        mock_client.chat_postMessage.side_effect = SlackApiError(
            message="channel_not_found",
            response={"error": "channel_not_found"},
        )

        with patch.dict(os.environ, REQUIRED_VARS, clear=False):
            with patch("notifier.WebClient", return_value=mock_client):
                from notifier import notify
                # 예외가 발생하지 않아야 함
                notify([])

    def test_notify_slack_failure_with_summaries_no_exception(self):
        """요약 목록이 있을 때 Slack API 실패해도 예외 없이 종료되어야 한다."""
        from slack_sdk.errors import SlackApiError
        from models import SummarizedArticle

        summaries = [
            SummarizedArticle(
                keyword_source="[건강기능식품/네이버]",
                headline="테스트 헤드라인",
                summary="테스트 요약 내용입니다.",
                url="https://example.com/1",
            )
        ]

        mock_client = MagicMock()
        mock_client.chat_postMessage.side_effect = SlackApiError(
            message="not_authed",
            response={"error": "not_authed"},
        )

        with patch.dict(os.environ, REQUIRED_VARS, clear=False):
            with patch("notifier.WebClient", return_value=mock_client):
                from notifier import notify
                # 예외가 발생하지 않아야 함
                notify(summaries)


class TestNotifyWithSupplements:
    """보완관계 그룹 렌더링 — _format_article 및 본문 요약 검증"""

    def _main_with_supplement(self):
        from models import SummarizedArticle

        return SummarizedArticle(
            keyword_source="[건기식/네이버]",
            headline="콜라겐 신제품 출시",
            summary="• 핵심 요약",
            url="https://example.com/main",
            supplements=[
                SummarizedArticle(
                    keyword_source="[규제/식약처]",
                    headline="콜라겐 표시기준 개정",
                    summary="• 규제 요약",
                    url="https://example.com/sup",
                    role="supplement",
                    relation_label="규제 동향",
                )
            ],
        )

    def test_format_article_includes_supplements(self):
        """supplements가 있으면 '연관 기사' 섹션과 보완 기사 내용이 메시지에 포함된다."""
        from notifier import _format_article

        text = _format_article(self._main_with_supplement())

        assert "콜라겐 신제품 출시" in text
        assert "연관 기사" in text
        assert "콜라겐 표시기준 개정" in text
        assert "규제 동향" in text
        assert "https://example.com/sup" in text

    def test_body_text_shows_group_count(self):
        """연관 그룹이 있으면 본문 헤더에 '연관 그룹 N개'가 표시된다."""
        from notifier import notify

        mock_client = MagicMock()
        mock_client.chat_postMessage.return_value = {"ts": "123.456"}

        with patch.dict(os.environ, REQUIRED_VARS, clear=False):
            with patch("notifier.WebClient", return_value=mock_client):
                notify([self._main_with_supplement()])

        body_text = mock_client.chat_postMessage.call_args_list[0][1].get("text", "")
        assert "연관 그룹 1개" in body_text
