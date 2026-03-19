"""
tests/test_properties.py — 속성 기반 테스트 (Hypothesis)
"""
import importlib
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

import pytest
from hypothesis import given, settings, strategies as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import Article, SummarizedArticle

REQUIRED_VARS = {
    "OPENAI_API_KEY": "test-openai-key",
    "SLACK_BOT_TOKEN": "xoxb-test-token",
    "SLACK_CHANNEL_ID": "C12345678",
    "NAVER_CLIENT_ID": "test-naver-id",
    "NAVER_CLIENT_SECRET": "test-naver-secret",
}

REQUIRED_ENV_VAR_NAMES = [
    "OPENAI_API_KEY",
    "SLACK_BOT_TOKEN",
    "SLACK_CHANNEL_ID",
    "NAVER_CLIENT_ID",
    "NAVER_CLIENT_SECRET",
]


# ---------------------------------------------------------------------------
# Property 1: 48시간 필터링 일관성
# Feature: daily-health-news-slack-bot, Property 1: 48시간 필터링 일관성
# ---------------------------------------------------------------------------

@given(offset_hours=st.integers(min_value=-48, max_value=48))
@settings(max_examples=100)
def test_property1_48h_filter_consistency(offset_hours):
    # Feature: daily-health-news-slack-bot, Property 1: 48시간 필터링 일관성
    """Validates: Requirements 2.1, 2.2, 2.3

    현재 시각 기준 offset_hours 만큼 떨어진 datetime에 대해
    _is_within_48h()가 48시간 이내이면 True, 초과이면 False를 반환해야 한다.
    """
    from collector import _is_within_48h, _now_utc

    now = _now_utc()
    dt = now - timedelta(hours=offset_hours)
    iso_str = dt.isoformat()
    result = _is_within_48h(iso_str)

    diff = now - dt
    if diff <= timedelta(hours=48):
        assert result is True, f"48시간 이내(offset={offset_hours}h)인데 False 반환"
    else:
        assert result is False, f"48시간 초과(offset={offset_hours}h)인데 True 반환"


# ---------------------------------------------------------------------------
# Property 2: 소스 실패 시 부분 수집 보장
# Feature: daily-health-news-slack-bot, Property 2: 소스 실패 시 부분 수집 보장
# ---------------------------------------------------------------------------

_ALL_SOURCES = ["naver", "google_rss", "foreign_rss", "instagram"]

_SOURCE_PATCH_TARGETS = {
    "naver": "collector.collect_naver",
    "google_rss": "collector.collect_google_rss",
    "foreign_rss": "collector.collect_foreign_rss",
    "instagram": "collector.collect_instagram",
}

_DUMMY_ARTICLE = Article(
    title="테스트 기사",
    url="https://example.com",
    content="내용",
    source="naver",
    published_at=None,
)


@given(failing_sources=st.lists(
    st.sampled_from(_ALL_SOURCES),
    min_size=1,
    max_size=3,
    unique=True,
))
@settings(max_examples=100)
def test_property2_partial_collection_on_source_failure(failing_sources):
    # Feature: daily-health-news-slack-bot, Property 2: 소스 실패 시 부분 수집 보장
    """Validates: Requirements 2.5, 2.6

    일부 소스가 예외를 발생시킬 때 collect_all()은 성공한 소스의
    Article을 포함한 목록을 반환해야 한다.
    """
    import collector

    succeeding_sources = [s for s in _ALL_SOURCES if s not in failing_sources]

    patches = {}
    for source in _ALL_SOURCES:
        if source == "naver":
            if source in failing_sources:
                patches["collector.collect_naver"] = MagicMock(side_effect=RuntimeError("naver 실패"))
            else:
                patches["collector.collect_naver"] = MagicMock(return_value=[_DUMMY_ARTICLE])
        elif source == "google_rss":
            if source in failing_sources:
                patches["collector.collect_google_rss"] = MagicMock(side_effect=RuntimeError("google_rss 실패"))
            else:
                patches["collector.collect_google_rss"] = MagicMock(return_value=[_DUMMY_ARTICLE])
        elif source == "foreign_rss":
            if source in failing_sources:
                patches["collector.collect_foreign_rss"] = MagicMock(side_effect=RuntimeError("foreign_rss 실패"))
            else:
                patches["collector.collect_foreign_rss"] = MagicMock(return_value=[_DUMMY_ARTICLE])
        elif source == "instagram":
            if source in failing_sources:
                patches["collector.collect_instagram"] = MagicMock(side_effect=RuntimeError("instagram 실패"))
            else:
                patches["collector.collect_instagram"] = MagicMock(return_value=[_DUMMY_ARTICLE])

    with patch.dict(os.environ, REQUIRED_VARS, clear=False):
        with patch("collector.collect_naver", patches["collector.collect_naver"]):
            with patch("collector.collect_google_rss", patches["collector.collect_google_rss"]):
                with patch("collector.collect_foreign_rss", patches["collector.collect_foreign_rss"]):
                    with patch("collector.collect_instagram", patches["collector.collect_instagram"]):
                        articles = collector.collect_all()

    # 성공한 소스가 있으면 결과 목록이 비어있지 않아야 한다
    # (naver/google_rss는 NAVER_QUERIES/GOOGLE_QUERIES 3개씩 반복 호출됨)
    if succeeding_sources:
        assert len(articles) > 0, (
            f"성공 소스 {succeeding_sources}가 있는데 결과가 비어있음"
        )


# ---------------------------------------------------------------------------
# Property 3: LLM 응답 파싱 결과 구조 완전성
# Feature: daily-health-news-slack-bot, Property 3: LLM 응답 파싱 결과 구조 완전성
# ---------------------------------------------------------------------------

_article_dict_strategy = st.fixed_dictionaries({
    "keyword_source": st.text(min_size=1, max_size=50),
    "headline": st.text(min_size=1, max_size=100),
    "summary": st.text(min_size=1, max_size=300),
    "url": st.text(min_size=1, max_size=200),
})


@given(items=st.lists(_article_dict_strategy, min_size=0, max_size=5))
@settings(max_examples=100, deadline=None)
def test_property3_llm_response_structure_completeness(items):
    # Feature: daily-health-news-slack-bot, Property 3: LLM 응답 파싱 결과 구조 완전성
    """Validates: Requirements 3.3, 3.6

    GPT-4o 응답에서 파싱된 SummarizedArticle 목록의 각 항목은
    keyword_source, headline, summary, url 필드를 모두 포함해야 한다.
    """
    from analyzer import analyze

    mock_response_content = json.dumps({"articles": items}, ensure_ascii=False)

    mock_choice = MagicMock()
    mock_choice.message.content = mock_response_content
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]

    mock_openai_client = MagicMock()
    mock_openai_client.chat.completions.create.return_value = mock_completion

    dummy_articles = [
        Article(title="t", url="u", content="c", source="naver")
    ]

    with patch.dict(os.environ, REQUIRED_VARS, clear=False):
        with patch("analyzer.OpenAI", return_value=mock_openai_client):
            results = analyze(dummy_articles)

    assert len(results) == len(items)
    for result in results:
        assert isinstance(result, SummarizedArticle)
        assert hasattr(result, "keyword_source")
        assert hasattr(result, "headline")
        assert hasattr(result, "summary")
        assert hasattr(result, "url")
        assert result.keyword_source is not None
        assert result.headline is not None
        assert result.summary is not None
        assert result.url is not None


# ---------------------------------------------------------------------------
# Property 4: 본문 메시지 날짜 형식
# Feature: daily-health-news-slack-bot, Property 4: 본문 메시지 날짜 형식
# ---------------------------------------------------------------------------

_DATE_PATTERN = re.compile(r"^\[\d{1,2}/\d{1,2} 건기식 뉴스 봇\]")


@given(date=st.dates())
@settings(max_examples=100)
def test_property4_body_message_date_format(date):
    # Feature: daily-health-news-slack-bot, Property 4: 본문 메시지 날짜 형식
    """Validates: Requirements 4.2

    임의 날짜에 대해 Notifier가 생성하는 본문 메시지 텍스트는
    [M/D 건기식 뉴스 봇] 패턴을 만족해야 한다.
    """
    mock_client = MagicMock()
    mock_client.chat_postMessage.return_value = {"ts": "1234567890.000001"}

    fixed_dt = datetime(date.year, date.month, date.day, 10, 0, 0)

    with patch.dict(os.environ, REQUIRED_VARS, clear=False):
        with patch("notifier.WebClient", return_value=mock_client):
            with patch("notifier.datetime") as mock_dt:
                mock_dt.now.return_value = fixed_dt
                from notifier import notify
                notify([])

    assert mock_client.chat_postMessage.called
    call_kwargs = mock_client.chat_postMessage.call_args[1]
    text = call_kwargs.get("text", "")

    assert _DATE_PATTERN.match(text), (
        f"날짜 {date}에 대한 메시지 '{text}'가 패턴 '[M/D 건기식 뉴스 봇]'을 만족하지 않음"
    )

    # 월/일 값이 실제 날짜와 일치하는지 검증
    expected_prefix = f"[{date.month}/{date.day} 건기식 뉴스 봇]"
    assert text.startswith(expected_prefix), (
        f"기대: '{expected_prefix}', 실제: '{text}'"
    )


# ---------------------------------------------------------------------------
# Property 5: 스레드 메시지 형식 완전성
# Feature: daily-health-news-slack-bot, Property 5: 스레드 메시지 형식 완전성
# ---------------------------------------------------------------------------

_summarized_article_strategy = st.builds(
    SummarizedArticle,
    keyword_source=st.text(min_size=1, max_size=50),
    headline=st.text(min_size=1, max_size=100),
    summary=st.text(min_size=1, max_size=300),
    url=st.text(min_size=1, max_size=200),
)


@given(summaries=st.lists(_summarized_article_strategy, min_size=1, max_size=5))
@settings(max_examples=100)
def test_property5_thread_message_completeness(summaries):
    # Feature: daily-health-news-slack-bot, Property 5: 스레드 메시지 형식 완전성
    """Validates: Requirements 4.3, 4.4

    임의 SummarizedArticle 목록에 대해 각 스레드 메시지는
    keyword_source, headline, summary, url을 모두 포함해야 한다.
    """
    mock_client = MagicMock()
    mock_client.chat_postMessage.return_value = {"ts": "1234567890.000001"}

    with patch.dict(os.environ, REQUIRED_VARS, clear=False):
        with patch("notifier.WebClient", return_value=mock_client):
            from notifier import notify
            notify(summaries)

    # 본문 메시지 1회 + 스레드 메시지 len(summaries)회
    assert mock_client.chat_postMessage.call_count == 1 + len(summaries)

    # 스레드 메시지 검증 (인덱스 1부터)
    all_calls = mock_client.chat_postMessage.call_args_list
    thread_calls = all_calls[1:]

    for i, (call, article) in enumerate(zip(thread_calls, summaries)):
        thread_text = call[1].get("text", "")
        assert article.keyword_source in thread_text, (
            f"스레드 메시지 {i}에 keyword_source '{article.keyword_source}' 없음"
        )
        assert article.headline in thread_text, (
            f"스레드 메시지 {i}에 headline '{article.headline}' 없음"
        )
        assert article.summary in thread_text, (
            f"스레드 메시지 {i}에 summary '{article.summary}' 없음"
        )
        assert article.url in thread_text, (
            f"스레드 메시지 {i}에 url '{article.url}' 없음"
        )


# ---------------------------------------------------------------------------
# Property 6: 필수 환경 변수 누락 시 즉시 종료
# Feature: daily-health-news-slack-bot, Property 6: 필수 환경 변수 누락 시 즉시 종료
# ---------------------------------------------------------------------------

@given(missing_vars=st.sets(
    st.sampled_from(REQUIRED_ENV_VAR_NAMES),
    min_size=1,
))
@settings(max_examples=100)
def test_property6_missing_env_vars_immediate_exit(missing_vars):
    # Feature: daily-health-news-slack-bot, Property 6: 필수 환경 변수 누락 시 즉시 종료
    """Validates: Requirements 5.3

    필수 환경 변수 집합의 임의 부분 집합이 누락된 경우
    validate_env()는 SystemExit을 발생시켜야 하며,
    파이프라인(collect_all, analyze, notify)이 실행되지 않아야 한다.
    """
    env_without_missing = {k: v for k, v in REQUIRED_VARS.items() if k not in missing_vars}

    mock_collect = MagicMock()
    mock_analyze = MagicMock()
    mock_notify = MagicMock()

    if "main" in sys.modules:
        m = importlib.reload(sys.modules["main"])
    else:
        import main as m

    with patch.dict(os.environ, env_without_missing, clear=True):
        with patch.object(m, "collect_all", mock_collect):
            with patch.object(m, "analyze", mock_analyze):
                with patch.object(m, "notify", mock_notify):
                    with pytest.raises(SystemExit):
                        m.validate_env()

    # 파이프라인 함수들이 호출되지 않아야 한다
    mock_collect.assert_not_called()
    mock_analyze.assert_not_called()
    mock_notify.assert_not_called()
