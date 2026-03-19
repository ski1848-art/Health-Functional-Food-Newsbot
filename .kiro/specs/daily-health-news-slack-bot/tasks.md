# Implementation Tasks

## Task List

- [x] 1. 프로젝트 기반 구조 설정
  - [x] 1.1 `requirements.txt` 작성 (openai, slack_sdk, feedparser, requests, apify-client, python-dotenv, hypothesis)
  - [x] 1.2 `models.py` 작성 — `Article`, `SummarizedArticle` dataclass 정의
  - [x] 1.3 `.github/workflows/main.yml` 작성 — cron `0 1 * * *`, env 블록, Python 설치 스텝 포함

- [x] 2. Collector 모듈 구현 (`collector.py`)
  - [x] 2.1 `collect_naver(query)` 구현 — Naver News API 호출, 48시간 필터링
  - [x] 2.2 `collect_google_rss(query)` 구현 — Google News RSS feedparser, 48시간 필터링
  - [x] 2.3 `collect_foreign_rss(feed_urls)` 구현 — 해외 RSS feedparser, 48시간 필터링
  - [x] 2.4 `collect_instagram(accounts)` 구현 — Apify API 또는 Instaloader 연동
  - [x] 2.5 `collect_all()` 구현 — 4개 소스 순차 수집, 소스 실패 시 skip + 로그 기록

- [x] 3. Analyzer 모듈 구현 (`analyzer.py`)
  - [x] 3.1 `SYSTEM_PROMPT` 상수 정의
  - [x] 3.2 `analyze(articles)` 구현 — Article 목록 JSON 직렬화 후 GPT-4o 호출
  - [x] 3.3 GPT-4o 응답 파싱 — `SummarizedArticle` 목록 반환
  - [x] 3.4 LLM API 실패 시 예외 로그 기록 및 상위 전파 처리

- [x] 4. Notifier 모듈 구현 (`notifier.py`)
  - [x] 4.1 `notify(summaries)` 구현 — `[M/D 건기식 뉴스 봇]` 본문 메시지 발송
  - [x] 4.2 `ts` 값으로 각 SummarizedArticle 스레드 발송 구현
  - [x] 4.3 결과 0건 시 "오늘은 주목할 만한 건기식 뉴스가 없습니다." 발송 처리
  - [x] 4.4 Slack API 실패 시 로그 기록 후 종료 처리

- [x] 5. main.py 진입점 구현
  - [x] 5.1 `validate_env()` 구현 — 필수 환경 변수 누락 시 명확한 오류 메시지 출력 후 종료
  - [x] 5.2 `main()` 구현 — `validate_env → collect_all → analyze → notify` 순서 파이프라인

- [x] 6. 단위 테스트 작성 (`tests/test_*.py`)
  - [x] 6.1 `test_validate_env` — 필수 변수 누락 시 SystemExit 발생 검증
  - [x] 6.2 `test_collect_naver_mock` — mock HTTP 응답으로 파싱 및 48시간 필터 검증
  - [x] 6.3 `test_analyze_api_failure` — mock OpenAI 실패 시 예외 전파 검증
  - [x] 6.4 `test_notify_empty_summaries` — 빈 목록 입력 시 "뉴스 없음" 메시지 발송 검증
  - [x] 6.5 `test_notify_slack_failure` — mock Slack 실패 시 로그 기록 후 종료 검증
  - [x] 6.6 `test_pipeline_order` — `main()` mock으로 Collector → Analyzer → Notifier 순서 검증
  - [x] 6.7 `test_workflow_file` — `main.yml` YAML 파싱으로 cron 표현식 및 env 블록 검증

- [x] 7. 속성 기반 테스트 작성 (`tests/test_properties.py`, Hypothesis 사용)
  - [x] 7.1 Property 1 테스트 — 임의 날짜로 48시간 필터링 일관성 검증
    - `# Feature: daily-health-news-slack-bot, Property 1: 48시간 필터링 일관성`
  - [x] 7.2 Property 2 테스트 — 임의 소스 실패 조합으로 부분 수집 보장 검증
    - `# Feature: daily-health-news-slack-bot, Property 2: 소스 실패 시 부분 수집 보장`
  - [x] 7.3 Property 3 테스트 — 임의 LLM 응답으로 SummarizedArticle 구조 완전성 검증
    - `# Feature: daily-health-news-slack-bot, Property 3: LLM 응답 파싱 결과 구조 완전성`
  - [x] 7.4 Property 4 테스트 — 임의 날짜로 본문 메시지 `[M/D 건기식 뉴스 봇]` 형식 검증
    - `# Feature: daily-health-news-slack-bot, Property 4: 본문 메시지 날짜 형식`
  - [x] 7.5 Property 5 테스트 — 임의 SummarizedArticle로 스레드 메시지 형식 완전성 검증
    - `# Feature: daily-health-news-slack-bot, Property 5: 스레드 메시지 형식 완전성`
  - [x] 7.6 Property 6 테스트 — 임의 누락 변수 조합으로 즉시 종료 검증
    - `# Feature: daily-health-news-slack-bot, Property 6: 필수 환경 변수 누락 시 즉시 종료`
