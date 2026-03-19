"""
main.py — 일일 건기식 뉴스 슬랙 봇 진입점
"""
import logging
import os
import sys

from dotenv import load_dotenv

from collector import collect_all
from analyzer import analyze
from notifier import notify

REQUIRED_ENV_VARS = [
    "OPENAI_API_KEY",
    "SLACK_BOT_TOKEN",
    "SLACK_CHANNEL_ID",
    "NAVER_CLIENT_ID",
    "NAVER_CLIENT_SECRET",
]


def validate_env() -> None:
    """필수 환경 변수 존재 여부 검사. 누락 시 오류 메시지 출력 후 종료."""
    missing = [var for var in REQUIRED_ENV_VARS if not os.environ.get(var)]
    if missing:
        print(f"필수 환경 변수가 누락되었습니다: {', '.join(missing)}")
        sys.exit(1)


def main() -> None:
    load_dotenv()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    validate_env()

    articles = collect_all()
    summaries = analyze(articles)
    notify(summaries)


if __name__ == "__main__":
    main()
