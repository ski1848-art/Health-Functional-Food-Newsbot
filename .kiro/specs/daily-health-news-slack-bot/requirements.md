# Requirements Document

## Introduction

'모아담다(moadamda.com)' 건강기능식품 브랜드를 위한 일일 건기식 뉴스 요약 슬랙 봇.
매일 KST 오전 10시에 GitHub Actions를 통해 자동 실행되며, 국내외 뉴스·SNS 포스팅을 수집하고 LLM이 브랜드 관련성과 시장 중요도를 판단하여 유의미한 정보만 슬랙 채널에 요약 발송한다.

## Glossary

- **Bot**: 일일 건기식 뉴스 요약 슬랙 봇 전체 시스템
- **Scheduler**: GitHub Actions Cron Job 기반 실행 트리거
- **Collector**: 뉴스·RSS·SNS 데이터를 수집하는 모듈
- **Analyzer**: OpenAI GPT-4o를 활용하여 기사 관련성을 판단하고 요약하는 LLM 모듈
- **Notifier**: slack_sdk를 통해 슬랙 채널에 메시지를 발송하는 모듈
- **Article**: 수집된 개별 뉴스 기사, RSS 항목, 또는 SNS 포스팅 단위
- **Thread**: 슬랙 채널 본문 메시지에 연결된 스레드 메시지 묶음
- **KST**: 한국 표준시 (UTC+9)

---

## Requirements

### Requirement 1: 스케줄 기반 자동 실행

**User Story:** 담당자로서, 매일 아침 별도 조작 없이 뉴스 봇이 자동 실행되기를 원한다. 그래야 업무 시작 전 최신 건기식 동향을 슬랙에서 바로 확인할 수 있다.

#### Acceptance Criteria

1. THE Scheduler SHALL GitHub Actions Cron 표현식 `0 1 * * *`(UTC)으로 Bot을 매일 실행한다.
2. WHEN Scheduler가 Bot을 실행할 때, THE Bot SHALL KST 기준 오전 10시에 해당하는 시점에 전체 파이프라인(수집 → 분석 → 발송)을 순서대로 실행한다.
3. THE Scheduler SHALL GitHub Actions workflow 파일(`.github/workflows/main.yml`)로 정의된다.

---

### Requirement 2: 다중 소스 뉴스 수집

**User Story:** 분석가로서, 국내외 다양한 채널의 건기식 관련 정보를 한 곳에서 받아보고 싶다. 그래야 시장 전반의 동향을 놓치지 않을 수 있다.

#### Acceptance Criteria

1. WHEN Collector가 실행될 때, THE Collector SHALL 네이버 뉴스 API를 통해 검색어 `건강기능식품`, `모아담다`, `식약처`로 최근 48시간 이내 발행된 Article을 수집한다.
2. WHEN Collector가 실행될 때, THE Collector SHALL 구글 뉴스 RSS 피드를 통해 동일 검색어로 최근 48시간 이내 발행된 Article을 수집한다.
3. WHEN Collector가 실행될 때, THE Collector SHALL 해외 영양학 저널 및 건기식 관련 RSS 피드(예: NutraIngredients, Examine.com)에서 최근 48시간 이내 발행된 Article을 수집한다.
4. WHEN Collector가 실행될 때, THE Collector SHALL Apify API 또는 Instaloader를 통해 인스타그램 계정 `@dailybeauty.drop`, `@kodeok.kr`의 최신 포스팅을 수집한다.
5. IF 특정 소스 수집이 실패할 경우, THEN THE Collector SHALL 해당 소스를 건너뛰고 나머지 소스 수집을 계속 진행한다.
6. IF 특정 소스 수집이 실패할 경우, THEN THE Collector SHALL 실패한 소스명과 오류 내용을 로그에 기록한다.

---

### Requirement 3: LLM 기반 관련성 판단 및 요약

**User Story:** 브랜드 담당자로서, 광고성·무관한 기사는 걸러지고 실무적으로 가치 있는 정보만 받아보고 싶다. 그래야 정보 과부하 없이 핵심 인사이트에 집중할 수 있다.

#### Acceptance Criteria

1. WHEN Analyzer가 수집된 Article 목록을 수신할 때, THE Analyzer SHALL 지정된 시스템 프롬프트를 사용하여 OpenAI GPT-4o 모델에 Article을 전달한다.
2. THE Analyzer SHALL 시스템 프롬프트로 다음 내용을 사용한다: "너는 건강기능식품 산업 전문 애널리스트야. 입력된 기사들을 분석해서, 건기식 브랜드 '모아담다'의 비즈니스, 경쟁사 동향, 식약처 규제, 신원료 트렌드 등 실무적으로 가치 있는 정보만 필터링해. 광고성 기사나 무관한 내용은 버려. 선택된 기사만 3줄로 핵심을 요약해."
3. WHEN Analyzer가 LLM 응답을 수신할 때, THE Analyzer SHALL 유의미하다고 판단된 Article만 추출하여 요약 결과 목록을 반환한다.
4. WHEN 해외 영어 Article이 포함될 때, THE Analyzer SHALL LLM을 통해 해당 Article을 한국어로 번역하여 요약한다.
5. IF LLM API 호출이 실패할 경우, THEN THE Analyzer SHALL 오류를 로그에 기록하고 Notifier 실행을 중단한다.
6. WHEN Analyzer가 Article을 요약할 때, THE Analyzer SHALL 각 Article에 대해 키워드/출처, 핵심 요약 제목, 3줄 이내 본문 요약, 원문 URL을 포함한 구조화된 결과를 반환한다.

---

### Requirement 4: 슬랙 채널 메시지 발송

**User Story:** 팀원으로서, 슬랙에서 날짜별로 정리된 뉴스 요약을 스레드 형태로 받아보고 싶다. 그래야 채널이 지저분해지지 않고 필요한 기사만 클릭해서 읽을 수 있다.

#### Acceptance Criteria

1. WHEN Notifier가 실행될 때, THE Notifier SHALL slack_sdk의 `chat.postMessage`를 사용하여 지정된 슬랙 채널에 본문 메시지를 발송한다.
2. THE Notifier SHALL 본문 메시지 텍스트를 `[M/D 건기식 뉴스 봇]` 형식으로 구성한다 (예: `[10/24 건기식 뉴스 봇]`).
3. WHEN 본문 메시지 발송이 완료될 때, THE Notifier SHALL 반환된 `ts` 값을 사용하여 각 요약 Article을 해당 메시지의 스레드에 개별 메시지로 발송한다.
4. THE Notifier SHALL 각 스레드 메시지를 다음 형식으로 구성한다:
   - 첫 번째 줄: `[키워드/출처] 기사 또는 포스팅 핵심 요약 제목`
   - 본문: AI가 3줄 이내로 요약한 내용
   - 마지막 줄: 원문 URL 하이퍼링크
5. IF Analyzer가 유의미한 Article을 0건 반환할 경우, THEN THE Notifier SHALL 본문 메시지에 "오늘은 주목할 만한 건기식 뉴스가 없습니다." 메시지를 발송한다.
6. IF 슬랙 API 호출이 실패할 경우, THEN THE Notifier SHALL 오류를 로그에 기록하고 재시도 없이 종료한다.

---

### Requirement 5: 환경 변수 기반 시크릿 관리

**User Story:** 개발자로서, API 키와 토큰이 코드에 하드코딩되지 않기를 원한다. 그래야 보안 사고 없이 오픈소스로 관리할 수 있다.

#### Acceptance Criteria

1. THE Bot SHALL 모든 API 키 및 토큰(OpenAI API Key, Slack Bot Token, Slack Channel ID, Naver Client ID/Secret, Apify API Key)을 환경 변수로만 참조한다.
2. THE Scheduler SHALL GitHub Actions Secrets에 저장된 값을 workflow 파일의 `env` 블록을 통해 런타임 환경 변수로 주입한다.
3. IF 필수 환경 변수가 누락된 경우, THEN THE Bot SHALL 명확한 오류 메시지를 출력하고 즉시 종료한다.

---

### Requirement 6: 의존성 및 코드 구조

**User Story:** 개발자로서, 프로젝트를 즉시 실행 가능한 형태로 받아보고 싶다. 그래야 별도 설정 없이 바로 배포할 수 있다.

#### Acceptance Criteria

1. THE Bot SHALL `requirements.txt` 파일에 모든 Python 의존성 패키지와 버전을 명시한다.
2. THE Bot SHALL Python 3.10 이상 버전에서 실행 가능한 `main.py` 단일 진입점 파일을 제공한다.
3. THE Bot SHALL `.github/workflows/main.yml` 파일에 GitHub Actions workflow 전체 설정을 포함한다.
4. WHEN `main.py`가 실행될 때, THE Bot SHALL Collector → Analyzer → Notifier 순서로 파이프라인을 실행한다.
