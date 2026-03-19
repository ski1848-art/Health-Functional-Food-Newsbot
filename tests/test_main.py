"""
tests/test_main.py — main.py 단위 테스트
"""
import importlib
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

REQUIRED_VARS = {
    "OPENAI_API_KEY": "test-openai-key",
    "SLACK_BOT_TOKEN": "xoxb-test-token",
    "SLACK_CHANNEL_ID": "C12345678",
    "NAVER_CLIENT_ID": "test-naver-id",
    "NAVER_CLIENT_SECRET": "test-naver-secret",
}


def _get_main_module():
    """main 모듈을 강제 재로드하여 반환."""
    if "main" in sys.modules:
        return importlib.reload(sys.modules["main"])
    import main as m
    return m


class TestValidateEnv:
    """6.1 test_validate_env — 필수 변수 누락 시 SystemExit 발생 검증"""

    def test_all_vars_present_no_exit(self):
        """모든 필수 환경 변수가 있을 때 SystemExit이 발생하지 않아야 한다."""
        with patch.dict(os.environ, REQUIRED_VARS, clear=False):
            m = _get_main_module()
            m.validate_env()  # 예외 없이 정상 실행

    def test_missing_openai_key_raises_system_exit(self):
        """OPENAI_API_KEY 누락 시 SystemExit이 발생해야 한다."""
        env = {k: v for k, v in REQUIRED_VARS.items() if k != "OPENAI_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            m = _get_main_module()
            with pytest.raises(SystemExit):
                m.validate_env()

    def test_missing_slack_bot_token_raises_system_exit(self):
        """SLACK_BOT_TOKEN 누락 시 SystemExit이 발생해야 한다."""
        env = {k: v for k, v in REQUIRED_VARS.items() if k != "SLACK_BOT_TOKEN"}
        with patch.dict(os.environ, env, clear=True):
            m = _get_main_module()
            with pytest.raises(SystemExit):
                m.validate_env()

    def test_missing_slack_channel_id_raises_system_exit(self):
        """SLACK_CHANNEL_ID 누락 시 SystemExit이 발생해야 한다."""
        env = {k: v for k, v in REQUIRED_VARS.items() if k != "SLACK_CHANNEL_ID"}
        with patch.dict(os.environ, env, clear=True):
            m = _get_main_module()
            with pytest.raises(SystemExit):
                m.validate_env()

    def test_missing_naver_client_id_raises_system_exit(self):
        """NAVER_CLIENT_ID 누락 시 SystemExit이 발생해야 한다."""
        env = {k: v for k, v in REQUIRED_VARS.items() if k != "NAVER_CLIENT_ID"}
        with patch.dict(os.environ, env, clear=True):
            m = _get_main_module()
            with pytest.raises(SystemExit):
                m.validate_env()

    def test_missing_naver_client_secret_raises_system_exit(self):
        """NAVER_CLIENT_SECRET 누락 시 SystemExit이 발생해야 한다."""
        env = {k: v for k, v in REQUIRED_VARS.items() if k != "NAVER_CLIENT_SECRET"}
        with patch.dict(os.environ, env, clear=True):
            m = _get_main_module()
            with pytest.raises(SystemExit):
                m.validate_env()

    def test_all_vars_missing_raises_system_exit(self):
        """모든 필수 환경 변수 누락 시 SystemExit이 발생해야 한다."""
        with patch.dict(os.environ, {}, clear=True):
            m = _get_main_module()
            with pytest.raises(SystemExit):
                m.validate_env()


class TestPipelineOrder:
    """6.6 test_pipeline_order — collect_all → analyze → notify 순서 검증"""

    def test_pipeline_order(self):
        """main()이 collect_all → analyze → notify 순서로 호출되어야 한다."""
        call_order = []

        mock_articles = [MagicMock()]
        mock_summaries = [MagicMock()]

        def mock_collect_all():
            call_order.append("collect_all")
            return mock_articles

        def mock_analyze(articles):
            call_order.append("analyze")
            assert articles is mock_articles
            return mock_summaries

        def mock_notify(summaries):
            call_order.append("notify")
            assert summaries is mock_summaries

        with patch.dict(os.environ, REQUIRED_VARS, clear=False):
            m = _get_main_module()
            with patch.object(m, "collect_all", side_effect=mock_collect_all):
                with patch.object(m, "analyze", side_effect=mock_analyze):
                    with patch.object(m, "notify", side_effect=mock_notify):
                        with patch.object(m, "load_dotenv"):
                            m.main()

        assert call_order == ["collect_all", "analyze", "notify"]

    def test_pipeline_call_counts(self):
        """main()에서 각 함수가 정확히 1번씩 호출되어야 한다."""
        mock_collect = MagicMock(return_value=[])
        mock_analyze = MagicMock(return_value=[])
        mock_notify = MagicMock()

        with patch.dict(os.environ, REQUIRED_VARS, clear=False):
            m = _get_main_module()
            with patch.object(m, "collect_all", mock_collect):
                with patch.object(m, "analyze", mock_analyze):
                    with patch.object(m, "notify", mock_notify):
                        with patch.object(m, "load_dotenv"):
                            m.main()

        assert mock_collect.call_count == 1
        assert mock_analyze.call_count == 1
        assert mock_notify.call_count == 1
