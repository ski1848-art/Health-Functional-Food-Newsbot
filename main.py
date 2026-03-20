"""
main.py — 일일 건기식 뉴스 슬랙 봇 진입점
"""
import logging
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import holidays
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


def is_holiday_or_weekend() -> bool:
    """오늘이 주말 또는 한국 공휴일이면 True 반환."""
    tz = ZoneInfo("Asia/Seoul")
    today = datetime.now(tz).date()

    if today.weekday() >= 5:  # 5=토, 6=일
        logging.info("오늘은 주말(%s)입니다. 실행을 건너뜁니다.", today.strftime("%A"))
        return True

    kr_holidays = holidays.KR(years=today.year)
    if today in kr_holidays:
        logging.info("오늘은 공휴일(%s)입니다. 실행을 건너뜁니다.", kr_holidays[today])
        return True

    return False


def main() -> None:
    load_dotenv()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if is_holiday_or_weekend():
        sys.exit(0)

    validate_env()

    articles = collect_all()
    summaries = analyze(articles)
    notify(summaries)


if __name__ == "__main__":
    main()
