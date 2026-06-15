from dataclasses import dataclass, field
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
    group_id: Optional[int] = None        # 보완 관계 그룹 ID (None이면 독립 기사)
    role: str = "main"                    # "main" | "supplement"
    relation_label: Optional[str] = None  # 보완 기사 관계 설명 (예: "규제 동향", "시장 반응")
    supplements: list["SummarizedArticle"] = field(default_factory=list)  # 보완 기사 목록 (main만 사용)
