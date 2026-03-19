from dataclasses import dataclass
from typing import Optional


@dataclass
class Article:
    title: str
    url: str
    content: str          # 본문 또는 요약 텍스트
    source: str           # 'naver', 'google_rss', 'foreign_rss', 'instagram'
    published_at: Optional[str] = None  # ISO 8601 또는 원본 문자열


@dataclass
class SummarizedArticle:
    keyword_source: str   # "[키워드/출처]"
    headline: str         # 핵심 요약 제목
    summary: str          # 3줄 이내 본문 요약
    url: str              # 원문 URL
