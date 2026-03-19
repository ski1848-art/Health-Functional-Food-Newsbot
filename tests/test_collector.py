"""
tests/test_collector.py — collector.py 단위 테스트
"""
import os
import sys
from datetime import datetime, timezone, timedelta
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


def _rfc822(dt: datetime) -> str:
    """datetime을 RFC 822 형식 문자열로 변환."""
    return dt.strftime("%a, %d %b %Y %H:%M:%S +0000")


class TestCollectNaverMock:
    """6.2 test_collect_naver_mock — mock HTTP 응답으로 파싱 및 48시간 필터 검증"""

    def test_collect_naver_mock(self):
        """48시간 이내 기사만 반환되고 Article 필드가 올바르게 파싱되어야 한다."""
        now = datetime.now(timezone.utc)
        recent_pub = _rfc822(now - timedelta(hours=24))   # 48시간 이내
        old_pub = _rfc822(now - timedelta(hours=72))       # 48시간 초과

        mock_response_data = {
            "items": [
                {
                    "title": "건강기능식품 최신 뉴스",
                    "link": "https://example.com/news/1",
                    "originallink": "https://original.com/news/1",
                    "description": "건기식 관련 최신 내용입니다.",
                    "pubDate": recent_pub,
                },
                {
                    "title": "오래된 건기식 뉴스",
                    "link": "https://example.com/news/2",
                    "originallink": "https://original.com/news/2",
                    "description": "오래된 내용입니다.",
                    "pubDate": old_pub,
                },
            ]
        }

        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_response_data
        mock_resp.raise_for_status = MagicMock()

        with patch.dict(os.environ, REQUIRED_VARS, clear=False):
            with patch("requests.get", return_value=mock_resp):
                from collector import collect_naver
                articles = collect_naver("건강기능식품")

        # 48시간 이내 기사 1건만 반환
        assert len(articles) == 1

        article = articles[0]
        assert article.title == "건강기능식품 최신 뉴스"
        assert article.url == "https://example.com/news/1"
        assert article.content == "건기식 관련 최신 내용입니다."
        assert article.source == "naver"
        assert article.published_at == recent_pub

    def test_collect_naver_all_recent(self):
        """모든 기사가 48시간 이내이면 전부 반환되어야 한다."""
        now = datetime.now(timezone.utc)

        mock_response_data = {
            "items": [
                {
                    "title": f"뉴스 {i}",
                    "link": f"https://example.com/news/{i}",
                    "description": f"내용 {i}",
                    "pubDate": _rfc822(now - timedelta(hours=i)),
                }
                for i in range(1, 4)
            ]
        }

        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_response_data
        mock_resp.raise_for_status = MagicMock()

        with patch.dict(os.environ, REQUIRED_VARS, clear=False):
            with patch("requests.get", return_value=mock_resp):
                from collector import collect_naver
                articles = collect_naver("건강기능식품")

        assert len(articles) == 3

    def test_collect_naver_all_old(self):
        """모든 기사가 48시간 초과이면 빈 리스트를 반환해야 한다."""
        now = datetime.now(timezone.utc)

        mock_response_data = {
            "items": [
                {
                    "title": "오래된 뉴스",
                    "link": "https://example.com/old",
                    "description": "오래된 내용",
                    "pubDate": _rfc822(now - timedelta(hours=100)),
                }
            ]
        }

        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_response_data
        mock_resp.raise_for_status = MagicMock()

        with patch.dict(os.environ, REQUIRED_VARS, clear=False):
            with patch("requests.get", return_value=mock_resp):
                from collector import collect_naver
                articles = collect_naver("건강기능식품")

        assert articles == []
