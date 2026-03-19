"""
Collector 모듈 — 다중 소스에서 건기식 관련 Article 수집
"""
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

import feedparser
import requests

from models import Article

logger = logging.getLogger(__name__)

# 기본 검색어 (모아담다 제외 — 유관 건기식 기사 수집 목적)
# 제품군: 건강/면역, 다이어트, 피부&항산화, 모로실/혈당관리
NAVER_QUERIES = [
    # 카테고리
    "건강기능식품", "식약처",
    # 건강/면역
    "홍삼 건강기능식품", "오메가3 건강기능식품", "코엔자임Q10",
    # 다이어트
    "가르시니아 다이어트", "시서스 다이어트", "체중관리 건강기능식품",
    # 피부&항산화
    "콜라겐 건강기능식품", "히알루론산 건강기능식품", "글루타치온", "루테인 건강기능식품",
    # 모로실/혈당
    "모로실", "혈당관리 건강기능식품", "바나바잎", "여주 혈당",
]

# 구글 뉴스 RSS 검색어
GOOGLE_QUERIES = [
    "건강기능식품", "식약처",
    "모로실 다이어트", "혈당관리 건기식",
    "콜라겐 건강기능식품", "글루타치온 피부",
    "가르시니아 시서스", "홍삼 건강기능식품",
]

# 1차 키워드 필터 — 제목에 하나라도 포함되면 통과 (모아담다 제외)
RELEVANCE_KEYWORDS = [
    # 카테고리
    "건강기능식품", "건기식", "식약처", "원료", "규제", "임상",
    "영양", "기능성", "인증", "허가", "성분", "보충제",
    # 건강/면역 원료
    "프로바이오틱스", "유산균", "오메가", "비타민", "홍삼", "인삼",
    "EPA", "DHA", "마그네슘", "아연", "철분", "엽산",
    "코엔자임", "CoQ10", "밀크씨슬", "NAD", "NMN",
    # 다이어트 원료
    "가르시니아", "시서스", "카르니틴", "CLA", "공액리놀레산",
    "히비스커스", "카테킨", "녹차추출물", "난소화성말토덱스트린",
    "다이어트", "체중관리",
    # 피부&항산화 원료
    "콜라겐", "히알루론산", "루테인", "아스타잔틴", "글루타치온",
    "세라마이드", "펩타이드", "레스베라트롤", "엘라스틴",
    "피부미용", "항산화",
    # 혈당관리 원료
    "모로실", "바나바잎", "코로솔산", "여주", "베르베린",
    "계피추출물", "크롬", "혈당", "혈압", "콜레스테롤",
    # 기타
    "강황", "커큐민", "눈건강", "장건강", "면역",
    # 영문
    "supplement", "nutraceutical", "probiotic", "collagen", "morosil",
]

# 해외 RSS 피드 기본 URL
DEFAULT_FOREIGN_FEEDS = [
    "https://www.nutraingredients-asia.com/rss/news",
    "https://www.nutraingredients.com/rss/news",
]

# 인스타그램 기본 계정
DEFAULT_INSTAGRAM_ACCOUNTS = ["dailybeauty.drop", "kodeok.kr"]

# KST 기준 24시간
HOURS_24 = timedelta(hours=24)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    """다양한 날짜 문자열을 UTC datetime으로 파싱."""
    if not dt_str:
        return None
    formats = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(dt_str, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


def _is_within_24h(published_at: Optional[str]) -> bool:
    """published_at 문자열이 현재 기준 24시간 이내인지 확인."""
    if not published_at:
        return False  # 날짜 없으면 제외
    dt = _parse_datetime(published_at)
    if dt is None:
        return False  # 파싱 실패하면 제외
    return (_now_utc() - dt) <= HOURS_24


def _entry_pub_date(entry) -> Optional[str]:
    """feedparser entry에서 날짜 문자열 추출. published_parsed 우선 사용."""
    import time as time_module
    # feedparser가 파싱한 struct_time 사용 (가장 정확)
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            try:
                dt = datetime(*t[:6], tzinfo=timezone.utc)
                return dt.isoformat()
            except Exception:
                pass
    return entry.get("published") or entry.get("updated")


def _is_relevant(title: str) -> bool:
    """제목에 관련 키워드가 포함되어 있는지 확인."""
    title_lower = title.lower()
    return any(kw.lower() in title_lower for kw in RELEVANCE_KEYWORDS)


def deduplicate(articles: list[Article]) -> list[Article]:
    """URL 기준 중복 제거."""
    seen = set()
    result = []
    for a in articles:
        if a.url not in seen:
            seen.add(a.url)
            result.append(a)
    return result


def collect_naver(query: str) -> list[Article]:
    """Naver News API로 검색어에 해당하는 24시간 이내 Article 수집."""
    client_id = os.environ.get("NAVER_CLIENT_ID", "")
    client_secret = os.environ.get("NAVER_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        logger.warning("NAVER_CLIENT_ID 또는 NAVER_CLIENT_SECRET 환경 변수가 없습니다. Naver 수집을 건너뜁니다.")
        return []

    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
    }
    params = {"query": query, "display": 20, "sort": "date"}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        logger.error("Naver API 호출 실패 (query=%s): %s", query, e)
        return []

    articles = []
    for item in data.get("items", []):
        pub_date = item.get("pubDate")
        if not _is_within_24h(pub_date):
            continue
        title = item.get("title", "").replace("<b>", "").replace("</b>", "")
        articles.append(Article(
            title=title,
            url=item.get("link", item.get("originallink", "")),
            content=item.get("description", "").replace("<b>", "").replace("</b>", ""),
            source="naver",
            published_at=pub_date,
        ))

    return articles


def collect_google_rss(query: str) -> list[Article]:
    """Google News RSS 피드에서 검색어에 해당하는 48시간 이내 Article 수집."""
    feed_url = (
        f"https://news.google.com/rss/search"
        f"?q={requests.utils.quote(query)}&hl=ko&gl=KR&ceid=KR:ko"
    )

    try:
        feed = feedparser.parse(feed_url)
        if feed.bozo and feed.bozo_exception:
            raise feed.bozo_exception
    except Exception as e:
        logger.error("Google RSS 파싱 실패 (query=%s): %s", query, e)
        return []

    articles = []
    for entry in feed.entries[:20]:  # 검색어당 최대 20건
        pub_date = _entry_pub_date(entry)
        if not _is_within_24h(pub_date):
            continue
        articles.append(Article(
            title=entry.get("title", ""),
            url=entry.get("link", ""),
            content=entry.get("summary", ""),
            source="google_rss",
            published_at=pub_date,
        ))

    return articles


def collect_foreign_rss(feed_urls: list[str] = None) -> list[Article]:
    """해외 RSS 피드에서 48시간 이내 Article 수집."""
    if feed_urls is None:
        feed_urls = DEFAULT_FOREIGN_FEEDS

    articles = []
    for url in feed_urls:
        try:
            feed = feedparser.parse(url)
            if feed.bozo and feed.bozo_exception:
                raise feed.bozo_exception
        except Exception as e:
            logger.error("해외 RSS 파싱 실패 (url=%s): %s", url, e)
            continue

        for entry in feed.entries:
            pub_date = _entry_pub_date(entry)
            if not _is_within_24h(pub_date):
                continue
            articles.append(Article(
                title=entry.get("title", ""),
                url=entry.get("link", ""),
                content=entry.get("summary", ""),
                source="foreign_rss",
                published_at=pub_date,
            ))

    return articles


def collect_instagram(accounts: list[str] = None) -> list[Article]:
    """Apify API를 통해 인스타그램 계정의 최신 포스팅 수집."""
    if accounts is None:
        accounts = DEFAULT_INSTAGRAM_ACCOUNTS

    api_key = os.environ.get("APIFY_API_KEY", "")
    if not api_key:
        logger.info("APIFY_API_KEY 없음. Instagram 수집을 건너뜁니다.")
        return []

    try:
        from apify_client import ApifyClient
        client = ApifyClient(api_key)

        run_input = {
            "directUrls": [f"https://www.instagram.com/{acc}/" for acc in accounts],
            "resultsType": "posts",
            "resultsLimit": 10,
        }

        run = client.actor("apify/instagram-scraper").call(run_input=run_input)
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    except Exception as e:
        logger.error("Instagram(Apify) 수집 실패: %s", e)
        return []

    articles = []
    for item in items:
        pub_date = item.get("timestamp") or item.get("taken_at_timestamp")
        if pub_date and isinstance(pub_date, (int, float)):
            pub_date = datetime.fromtimestamp(pub_date, tz=timezone.utc).isoformat()
        if not _is_within_24h(pub_date):
            continue
        articles.append(Article(
            title=item.get("caption", "")[:100] or "(Instagram 포스팅)",
            url=item.get("url") or item.get("shortCode", ""),
            content=item.get("caption", ""),
            source="instagram",
            published_at=pub_date,
        ))

    return articles


def collect_all() -> list[Article]:
    """4개 소스에서 순차 수집. 각 소스 실패 시 skip + 로그 기록."""
    all_articles: list[Article] = []

    # 1. Naver News API
    for query in NAVER_QUERIES:
        try:
            articles = collect_naver(query)
            all_articles.extend(articles)
            logger.info("Naver 수집 완료 (query=%s): %d건", query, len(articles))
        except Exception as e:
            logger.error("Naver 소스 실패 (query=%s): %s", query, e)

    # 2. Google News RSS
    for query in GOOGLE_QUERIES:
        try:
            articles = collect_google_rss(query)
            all_articles.extend(articles)
            logger.info("Google RSS 수집 완료 (query=%s): %d건", query, len(articles))
        except Exception as e:
            logger.error("Google RSS 소스 실패 (query=%s): %s", query, e)

    # 3. 해외 RSS
    try:
        articles = collect_foreign_rss()
        all_articles.extend(articles)
        logger.info("해외 RSS 수집 완료: %d건", len(articles))
    except Exception as e:
        logger.error("해외 RSS 소스 실패: %s", e)

    # 4. Instagram
    try:
        articles = collect_instagram()
        all_articles.extend(articles)
        logger.info("Instagram 수집 완료: %d건", len(articles))
    except Exception as e:
        logger.error("Instagram 소스 실패: %s", e)

    logger.info("전체 수집 완료: 총 %d건", len(all_articles))

    # 중복 제거 + 키워드 필터링 + 최대 50건 제한
    all_articles = deduplicate(all_articles)
    all_articles = [a for a in all_articles if _is_relevant(a.title)]
    all_articles = all_articles[:50]
    logger.info("필터링 후: %d건", len(all_articles))

    return all_articles
