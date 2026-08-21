"""
forwarder.py — 슬랙에 보낸 기사를 모아담다 애널리틱스에도 한 부 보관시킨다.

왜: 이 봇은 지금까지 기사를 슬랙에만 뿌리고 **아무것도 저장하지 않아** 매일 시장 정보를
    버리고 있었다. 애널리틱스에 쌓아 두면 원료·기간으로 다시 찾아볼 수 있고,
    신제품 리서치의 근거로도 쓸 수 있다.

원칙 (중요):
  · **슬랙 알림이 본업, 보관은 덤이다.** main.py 는 슬랙 발송(notify) 뒤에 이 함수를 부른다.
  · 여기서 무슨 일이 나도 **절대 예외를 밖으로 던지지 않는다.** 보관이 실패해도 봇은 정상 종료해야 한다.
  · 설정(HFF_NEWS_URL / HFF_NEWS_TOKEN)이 없으면 조용히 건너뛴다 — 예전처럼 그냥 도는 것과 같다.

필요한 환경 변수 (GitHub Secrets):
  HFF_NEWS_URL    받는 주소. 예: https://moadamda-analytics.co.kr/api/hff-news/ingest/<비밀문자열>
  HFF_NEWS_TOKEN  (선택) URL 에 비밀문자열을 안 넣었을 때만 사용. 넣으면 URL 뒤에 붙인다.
"""
import json
import logging
import os
import urllib.error
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

from models import SummarizedArticle

logger = logging.getLogger(__name__)

TIMEOUT_SEC = 10


def _endpoint() -> str | None:
    """받는 주소를 만든다. 설정이 없으면 None(건너뜀)."""
    url = (os.environ.get("HFF_NEWS_URL") or "").strip()
    if not url:
        return None
    token = (os.environ.get("HFF_NEWS_TOKEN") or "").strip()
    if token and not url.rstrip("/").endswith(token):
        url = f"{url.rstrip('/')}/{token}"
    return url


def _flatten(summaries: list[SummarizedArticle]) -> list[dict]:
    """main 기사와 그 보완 기사를 한 줄씩 펼친다(보관은 전부 남긴다)."""
    rows: list[dict] = []

    def add(a: SummarizedArticle, role: str) -> None:
        rows.append(
            {
                "keyword_source": a.keyword_source,
                "headline": a.headline,
                "summary": a.summary,
                "url": a.url,
                "group_id": a.group_id,
                "role": role,
                "relation_label": a.relation_label,
            }
        )

    for article in summaries:
        add(article, article.role or "main")
        for sup in getattr(article, "supplements", None) or []:
            add(sup, "supplement")
    return rows


def forward(summaries: list[SummarizedArticle]) -> None:
    """애널리틱스에 기사를 보낸다. **어떤 경우에도 예외를 던지지 않는다.**"""
    try:
        if not summaries:
            return

        url = _endpoint()
        if not url:
            logger.info("보관 설정(HFF_NEWS_URL) 이 없어 건너뜁니다.")
            return

        payload = {
            "sentAt": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(),
            "articles": _flatten(summaries),
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as res:
            raw = res.read().decode("utf-8", errors="replace")
            logger.info("보관 완료: HTTP %s %s", res.status, raw[:200])

    except urllib.error.HTTPError as e:
        # 주소·비밀문자열이 틀리면 404 가 온다. 알림은 이미 나갔으니 로그만 남긴다.
        logger.error("보관 실패(무시): HTTP %s", e.code)
    except Exception as e:  # noqa: BLE001 - 보관 실패가 봇을 멈추게 하면 안 된다
        logger.error("보관 실패(무시): %s", e)
