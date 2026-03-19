"""
tests/test_analyzer.py — analyzer.py 단위 테스트
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


class TestAnalyzeApiFailure:
    """6.3 test_analyze_api_failure — mock OpenAI 실패 시 예외 전파 검증"""

    def test_analyze_api_failure_propagates_exception(self):
        """OpenAI API 호출 실패 시 예외가 상위로 전파되어야 한다."""
        from models import Article

        articles = [
            Article(
                title="테스트 기사",
                url="https://example.com/1",
                content="테스트 내용",
                source="naver",
                published_at="2024-01-01T00:00:00Z",
            )
        ]

        mock_client_instance = MagicMock()
        mock_client_instance.chat.completions.create.side_effect = Exception("API 연결 실패")

        with patch.dict(os.environ, REQUIRED_VARS, clear=False):
            with patch("openai.OpenAI", return_value=mock_client_instance):
                from analyzer import analyze
                with pytest.raises(Exception, match="API 연결 실패"):
                    analyze(articles)

    def test_analyze_api_timeout_propagates(self):
        """OpenAI API 타임아웃 시 예외가 상위로 전파되어야 한다."""
        import openai
        from models import Article

        articles = [
            Article(
                title="테스트 기사",
                url="https://example.com/1",
                content="테스트 내용",
                source="naver",
            )
        ]

        mock_client_instance = MagicMock()
        mock_client_instance.chat.completions.create.side_effect = openai.APITimeoutError(
            request=MagicMock()
        )

        with patch.dict(os.environ, REQUIRED_VARS, clear=False):
            with patch("openai.OpenAI", return_value=mock_client_instance):
                from analyzer import analyze
                with pytest.raises(Exception):
                    analyze(articles)
