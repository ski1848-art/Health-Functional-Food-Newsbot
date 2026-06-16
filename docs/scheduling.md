# 발송 시각 정밀 제어 — 외부 스케줄러 설정 가이드

## 배경

GitHub Actions의 `schedule`(cron)은 **정시 실행을 보장하지 않는다.** 무료 러너는
정각·30분대에 전 세계 작업이 몰려 큐가 밀리고, 저활동 레포는 후순위라 수십 분~수시간
지연된다. 실제로 이 봇은 `KST 09:30` 설정인데 5월 내내 **오후 1시대**에 발송됐다
(UTC 00:30 예약 → 실제 04:3x 실행, 약 4시간 지연).

정확한 시각(평일 점심 **12:30 KST**)에 발송하려면, **외부 스케줄러가 정시에
GitHub의 `workflow_dispatch` API를 호출**하게 한다. GitHub schedule 지연을 우회한다.

---

## 설정 단계

### 1. GitHub Personal Access Token(PAT) 발급

1. GitHub → 우상단 프로필 → **Settings**
2. 좌측 맨 아래 **Developer settings**
3. **Personal access tokens → Fine-grained tokens → Generate new token**
4. 설정:
   - **Token name**: `newsbot-scheduler`
   - **Expiration**: 원하는 기간 (만료되면 갱신 필요 — 캘린더에 기록 권장)
   - **Repository access**: Only select repositories → `Health-Functional-Food-Newsbot`
   - **Permissions** → Repository permissions → **Actions: Read and write**
5. **Generate token** → 토큰 문자열 복사 (이 화면을 벗어나면 다시 못 봄)

> ⚠️ 이 토큰은 비밀번호와 같다. 외부 노출 금지. 아래 cron-job.org에만 입력한다.

### 2. cron-job.org 가입 및 작업 생성 (무료)

1. https://cron-job.org 가입
2. **Create cronjob**
3. **Common 탭**
   - Title: `건기식 뉴스봇`
   - URL: `https://api.github.com/repos/ski1848-art/Health-Functional-Food-Newsbot/actions/workflows/main.yml/dispatches`
   - Schedule: **Time zone = Asia/Seoul**, 요일 = Mon~Fri, 시각 = **12:30**
4. **Advanced 탭**
   - Request method: **POST**
   - Headers (각 줄 추가):
     - `Accept: application/vnd.github+json`
     - `Authorization: Bearer <1단계에서 복사한 토큰>`
     - `X-GitHub-Api-Version: 2022-11-28`
   - Request body: `{"ref":"main"}`
5. **Create** 저장

### 3. 테스트

- cron-job.org에서 방금 만든 작업 → **Test run**(또는 Run now)
- GitHub 레포 → Actions 탭에 `Daily Health News Slack Bot`이 **workflow_dispatch**로
  즉시 실행되면 성공. 슬랙 발송도 확인.

### 4. (작동 확인 후) GitHub schedule 제거

외부 스케줄러가 정상 작동하면, `main.yml`의 `schedule` 블록을 제거해 **중복 발송을 막는다.**
`main.yml`에서 아래를 삭제:

```yaml
  schedule:
    - cron: '30 0 * * 1-5'
```

(`workflow_dispatch:`는 외부 스케줄러가 호출하므로 **반드시 유지**)

> 이 작업(코드 수정 + 테스트)은 개발 담당자에게 요청하면 된다.

---

## 주의사항

- **PAT 만료**: 만료되면 cron-job.org 호출이 401로 실패 → 발송 안 됨. 만료 전 갱신.
- **보안**: PAT는 cron-job.org에만 입력. fine-grained + Actions 권한 + 단일 레포로 범위가
  최소화돼 있어 유출 시 피해는 제한적이나, 노출되면 즉시 GitHub에서 revoke.
- **현재 백업**: 외부 셋업 전까지는 GitHub schedule(KST 09:30 설정, 실제 오후 1시대 발송)이
  백업으로 동작한다. 마침 희망 시간대(점심~오후 1시)와 근사하다.
