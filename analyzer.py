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
    "선택된 기사만 3줄로 핵심을 요약해.\n\n"
    "## 중복 처리 규칙\n"
    "동일한 사건/발표를 다루는 기사가 여러 개 있으면 가장 정보가 풍부한 기사 1개만 선택해.\n\n"
    "## 보완 관계 그룹핑 규칙\n"
    "서로 다른 사건이지만 같은 원료·성분·규제·브랜드 맥락으로 연결되는 기사는 반드시 그룹으로 묶어.\n"
    "그룹핑 기준 (하나라도 해당하면 묶어):\n"
    "  - 같은 원료/성분을 다루는 기사 (예: 콜라겐 신제품 + 콜라겐 규제 완화)\n"
    "  - 같은 규제 이슈를 다루는 기사 (예: 식약처 단속 + 업계 반응)\n"
    "  - 같은 시장 트렌드를 다루는 기사 (예: 혈당관리 제품 출시 + 혈당관리 시장 성장)\n"
    "  - 원인-결과 관계 기사 (예: 연구 결과 발표 + 해당 성분 제품 출시)\n"
    "그룹 내에서 더 중요한 기사가 main, 맥락을 보완하는 기사가 supplement야.\n"
    "완전히 무관한 기사만 group_id를 null로 설정해. 조금이라도 연관되면 묶어."
)

_USER_PROMPT_TEMPLATE = """\
아래 기사 목록을 분석하고, 관련성 있는 기사만 골라 JSON으로 반환해.

각 항목은 반드시 다음 필드를 포함해야 해:
- keyword_source: 키워드 또는 출처 (예: "[건강기능식품/네이버]")
- headline: 핵심 요약 제목 (원문 제목 그대로 또는 간결하게)
- summary: 핵심 내용을 반드시 3개 항목으로 요약. 형식: "• 요약1\n• 요약2\n• 요약3"
- url: 원문 URL
- group_id: 보완 관계 그룹 번호 (정수, 1부터 시작). 독립 기사는 null.
- role: "main" 또는 "supplement"
- relation_label: supplement인 경우 보완 관계 설명 (예: "규제 동향", "시장 반응", "연구 근거"). main이면 null.

중복 기사는 반드시 1개만 포함해. 같은 group_id 내에 main은 반드시 1개여야 해.

응답은 반드시 다음 형식의 JSON 객체로만 반환해:
{{"articles": [...]}}

기사 목록:
{articles_json}
"""


def analyze(articles: list[Article]) -> list[SummarizedArticle]:
    """GPT-4o로 관련성 판단, 중복 제거, 보완 관계 그룹핑 후 요약. 실패 시 예외 발생."""
    if not articles:
        return []

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    # 전체를 한 번에 넘겨 배치 간 중복 누락 방지 (collector에서 최대 50건으로 제한됨)
    results = _analyze_batch(client, articles)
    return _build_groups(results)


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
                group_id=item.get("group_id"),
                role=item.get("role", "main"),
                relation_label=item.get("relation_label"),
            )
        )

    return results


def _build_groups(articles: list[SummarizedArticle]) -> list[SummarizedArticle]:
    """supplement 기사를 main 기사의 supplements 리스트에 붙이고, main/독립 기사만 반환."""
    mains: dict[int, SummarizedArticle] = {}
    supplements: list[SummarizedArticle] = []
    independents: list[SummarizedArticle] = []

    for article in articles:
        if article.group_id is None:
            independents.append(article)
        elif article.role == "main":
            mains[article.group_id] = article
        else:
            supplements.append(article)

    # supplement를 해당 main에 연결
    for sup in supplements:
        if sup.group_id in mains:
            mains[sup.group_id].supplements.append(sup)
        else:
            # main이 없는 supplement는 독립 기사로 처리
            logger.warning("group_id=%s의 main 기사가 없어 독립 기사로 처리: %s", sup.group_id, sup.headline)
            independents.append(sup)

    # 그룹 기사(main) + 독립 기사 순서로 반환
    return list(mains.values()) + independents
