import json
import logging
import os

from openai import OpenAI

from models import Article, SummarizedArticle

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "너는 건강기능식품 산업 전문 애널리스트야. "
    "입력된 기사들을 분석해서, 건기식 브랜드 '모아담다'의 비즈니스, 경쟁사 동향, "
    "식약처 규제, 신원료 트렌드 등 실무적으로 가치 있는 정보만 필터링해. "
    "광고성 기사나 무관한 내용은 버려. "
    "선택된 기사만 3줄로 핵심을 요약해."
)

_USER_PROMPT_TEMPLATE = """\
아래 기사 목록을 분석하고, 관련성 있는 기사만 골라 JSON 배열로 반환해.
각 항목은 반드시 다음 필드를 포함해야 해:
- keyword_source: 키워드 또는 출처 (예: "[건강기능식품/네이버]")
- headline: 핵심 요약 제목 (원문 제목 그대로 또는 간결하게)
- summary: 핵심 내용을 반드시 3개 항목으로 요약. 형식: "• 요약1\n• 요약2\n• 요약3"
- url: 원문 URL

응답은 반드시 다음 형식의 JSON 객체로만 반환해:
{{"articles": [...]}}

기사 목록:
{articles_json}
"""


def analyze(articles: list[Article]) -> list[SummarizedArticle]:
    """GPT-4o로 관련성 판단 및 요약. 실패 시 예외 발생."""
    if not articles:
        return []

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    # 배치 크기 20건으로 나눠서 처리
    BATCH_SIZE = 20
    all_results: list[SummarizedArticle] = []

    for i in range(0, len(articles), BATCH_SIZE):
        batch = articles[i:i + BATCH_SIZE]
        results = _analyze_batch(client, batch)
        all_results.extend(results)

    return all_results


def _analyze_batch(client: OpenAI, articles: list[Article]) -> list[SummarizedArticle]:
    """배치 단위로 GPT-4o 호출."""

    articles_data = [
        {
            "idx": i,
            "title": a.title,
            "url": a.url,
            "source": a.source,
        }
        for i, a in enumerate(articles)
    ]
    articles_json = json.dumps(articles_data, ensure_ascii=False, indent=2)
    user_prompt = _USER_PROMPT_TEMPLATE.format(articles_json=articles_json)

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
    except Exception as e:
        logger.error("GPT-4o API 호출 실패: %s", e)
        raise

    raw = response.choices[0].message.content
    try:
        parsed = json.loads(raw)
        items = parsed.get("articles", [])
    except (json.JSONDecodeError, AttributeError) as e:
        logger.error("GPT-4o 응답 파싱 실패: %s\n응답 내용: %s", e, raw)
        raise

    results: list[SummarizedArticle] = []
    for item in items:
        missing = [f for f in ("keyword_source", "headline", "summary", "url") if f not in item]
        if missing:
            logger.error("SummarizedArticle 필드 누락 %s: %s", missing, item)
            raise ValueError(f"GPT-4o 응답 항목에 필수 필드 누락: {missing}")
        results.append(
            SummarizedArticle(
                keyword_source=item["keyword_source"],
                headline=item["headline"],
                summary=item["summary"],
                url=item["url"],
            )
        )

    return results
