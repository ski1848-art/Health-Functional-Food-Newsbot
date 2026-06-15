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


class TestBuildGroups:
    """_build_groups — 보완관계 그룹핑 로직 단위 테스트"""

    def _article(self, headline, group_id=None, role="main", relation_label=None):
        from models import SummarizedArticle

        return SummarizedArticle(
            keyword_source="[건기식/네이버]",
            headline=headline,
            summary="• 요약1\n• 요약2\n• 요약3",
            url=f"https://example.com/{headline}",
            group_id=group_id,
            role=role,
            relation_label=relation_label,
        )

    def test_independent_articles_pass_through(self):
        """group_id가 모두 None이면 전부 독립 기사로 그대로 반환된다."""
        from analyzer import _build_groups

        articles = [self._article("A"), self._article("B")]
        result = _build_groups(articles)

        assert len(result) == 2
        assert all(not a.supplements for a in result)

    def test_supplement_attached_to_main(self):
        """같은 group_id의 supplement는 main의 supplements에 붙고, 최상위엔 main만 남는다."""
        from analyzer import _build_groups

        main = self._article("메인기사", group_id=1, role="main")
        sup = self._article("보완기사", group_id=1, role="supplement", relation_label="규제 동향")
        result = _build_groups([main, sup])

        assert len(result) == 1
        assert result[0].headline == "메인기사"
        assert len(result[0].supplements) == 1
        assert result[0].supplements[0].headline == "보완기사"
        assert result[0].supplements[0].relation_label == "규제 동향"

    def test_orphan_supplement_becomes_independent(self):
        """main이 없는 supplement는 누락되지 않고 독립 기사로 처리된다."""
        from analyzer import _build_groups

        orphan = self._article("고아보완", group_id=99, role="supplement")
        result = _build_groups([orphan])

        assert len(result) == 1
        assert result[0].headline == "고아보완"

    def test_mixed_groups_and_independents(self):
        """그룹 기사와 독립 기사가 섞여 있어도 모두 반환된다 (supplement만 main 안으로)."""
        from analyzer import _build_groups

        main = self._article("메인", group_id=1, role="main")
        sup = self._article("보완", group_id=1, role="supplement")
        indep = self._article("독립", group_id=None)
        result = _build_groups([main, sup, indep])

        assert len(result) == 2
        assert {a.headline for a in result} == {"메인", "독립"}
        main_result = next(a for a in result if a.headline == "메인")
        assert len(main_result.supplements) == 1

    def test_duplicate_main_same_group_id_keeps_both(self):
        """같은 group_id에 main이 2개 와도 어느 기사도 소실되지 않는다 (리뷰 #1)."""
        from analyzer import _build_groups

        main1 = self._article("메인1", group_id=1, role="main")
        main2 = self._article("메인2", group_id=1, role="main")
        result = _build_groups([main1, main2])

        assert len(result) == 2
        assert {a.headline for a in result} == {"메인1", "메인2"}

    def test_unknown_role_not_silently_dropped(self):
        """role이 'MAIN'처럼 대소문자/예상 밖 값이어도 기사가 소실되지 않는다 (리뷰 #3)."""
        from analyzer import _build_groups

        upper = self._article("대문자메인", group_id=1, role="MAIN")
        weird = self._article("이상한롤", group_id=2, role="primary")
        result = _build_groups([upper, weird])

        headlines = {a.headline for a in result}
        assert "대문자메인" in headlines  # MAIN → main으로 정규화
        assert "이상한롤" in headlines    # 미지의 role → 독립 기사로 보존

    def test_coerce_group_id_normalizes_types(self):
        """_coerce_group_id는 문자열 숫자를 int로, 변환 불가/None은 None으로 정규화한다 (리뷰 #2)."""
        from analyzer import _coerce_group_id

        assert _coerce_group_id("1") == 1
        assert _coerce_group_id(1) == 1
        assert _coerce_group_id(None) is None
        assert _coerce_group_id("abc") is None
