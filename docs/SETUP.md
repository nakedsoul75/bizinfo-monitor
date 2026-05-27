# bizinfo-monitor 셋업 가이드

기업마당(bizinfo.go.kr) 지원사업 공고를 매일 14:00 KST에 자동 모니터링하여
카카오톡 "나에게 보내기"로 HTML 보고서 링크를 받는 시스템.

> **소요 시간**: 처음 셋업 약 20분 (API 발급 자동 승인 가정)
> **운영 비용**: 0원 (공공데이터포털 무료 + GitHub Actions 무료 한도 + 카카오 메모톡 무료)

---

## 0. 준비물

- GitHub 계정 (`nakedsoul75`) — 이미 있음
- 공공데이터포털 계정 (본인인증 필요)
- 카카오 디벨로퍼스 키 (기존 daily-order-report 에서 발급된 값 재사용)

---

## 1. 기업마당 OpenAPI 키 발급 (✅ 완료된 경우 건너뛰기)

### 1-1. 공공데이터포털 회원가입
1. https://www.data.go.kr 접속 → 우상단 **회원가입**
2. 본인인증 (휴대폰 또는 공동인증서)

### 1-2. API 활용신청
1. 다음 페이지 접속 → 우측 **"활용신청"** 버튼
   - https://www.data.go.kr/data/15113297/openapi.do
   - API명: **중소벤처기업부_사업공고**
2. 활용목적 입력 예시:
   > "자사 관련 정부 지원사업 공고를 매일 1회 모니터링하여 사내 알림으로 활용. 비영리 내부 용도."
3. 약관 동의 → 신청
4. 통상 **자동 승인 → 즉시 인증키 발급**

### 1-3. 인증키 확인
1. 우상단 **마이페이지** → **오픈 API** → **개발계정**
2. 신청한 API 클릭 → 일반 인증키(Decoding) 값 복사
   - 형식 예: `cbaec037e913b517d204f083ea57c0af2f8ca21a8882f82e9f51bbee06374bee`

> ⚠️ 인증키는 외부 노출 금지. 분실 시 마이페이지에서 재발급 가능.

---

## 2. GitHub 신규 repo 생성

### 2-1. repo 생성
1. https://github.com/new
2. Repository name: **`bizinfo-monitor`**
3. Owner: `nakedsoul75`
4. **Private** 권장 (Public 시 보고서 URL이 공개됨 — 회사명 노출 우려 시 Private)
5. README 자동 생성 체크 해제 (이미 있음)
6. Create repository

### 2-2. 로컬 git init + push
```powershell
cd C:\Users\naked\Documents\agent\bizinfo-monitor
git init
git add .
git status   # .env 파일이 목록에 없어야 함 (.gitignore 작동 확인)
git commit -m "Initial commit: bizinfo monitor"
git branch -M main
git remote add origin https://github.com/nakedsoul75/bizinfo-monitor.git
git push -u origin main
```

---

## 3. GitHub Pages 활성화

1. https://github.com/nakedsoul75/bizinfo-monitor/settings/pages
2. Source: **Deploy from a branch**
3. Branch: **main** / 폴더: **`/docs`** → Save
4. 1~2분 후 접속 확인:
   - https://nakedsoul75.github.io/bizinfo-monitor/reports/

> Private repo 도 GitHub Pages 사용 가능 (Pro/Team 플랜 또는 무료 한도 내).
> Pages가 안 보이면 repo Settings → Pages 가서 활성화.

---

## 4. GitHub Secrets 등록 (3개)

https://github.com/nakedsoul75/bizinfo-monitor/settings/secrets/actions

→ **New repository secret** 클릭하여 아래 3개 등록:

| Name | Value | 출처 |
|---|---|---|
| `BIZINFO_API_KEY` | 1-3에서 받은 인증키 | 공공데이터포털 |
| `KAKAO_REST_API_KEY` | 기존 값 재사용 | `daily-order-report\.env` 에서 복사 |
| `KAKAO_REFRESH_TOKEN` | 기존 값 재사용 | `daily-order-report\.env` 에서 복사 |

> 카카오 값을 모르면: `C:\Users\naked\Documents\agent\daily-order-report\.env` 파일 열어서 확인.

> (선택) `KAKAO_CLIENT_SECRET` — daily-order-report 에서 설정했다면 동일하게 등록.

---

## 5. 첫 실행 (Mock 테스트)

GitHub Actions 자동 실행 전, 코드 작동을 먼저 검증.

1. https://github.com/nakedsoul75/bizinfo-monitor/actions
2. 왼쪽 메뉴 **Bizinfo Daily Monitor** 클릭
3. 우측 상단 **Run workflow** 드롭다운 → `mock` 을 `true` 로 변경 → **Run workflow**
4. 1~2분 후 실행 완료 시 카톡 알림 도착 확인
5. 알림 링크 클릭 → HTML 보고서 정상 렌더링 확인

> Mock 데이터 5건 중 4건이 매칭되어 보일 것 (콤마나인/팩토리나인/디엘나인/가구 키워드).

---

## 6. 실 운영 시작

위 Mock 테스트가 성공하면 자동으로 매일 14:00 KST 실행됩니다.

다음 14시까지 기다리거나, 즉시 한 번 실 호출:
- Actions → Run workflow → `mock` 을 `false` 로 두고 실행

---

## 7. 키워드 수정

`config.yaml` 파일 편집 → git push → 다음 14시부터 반영.

```yaml
priority_keywords:   # ⭐ 우선 (회사명) — 강조 표시
  - "창대"
  - "디엘나인"
  - "콤마나인"
  - "팩토리나인"
  # 자유 추가

general_keywords:    # 📋 일반 (업종 키워드) — 일반 표시
  - "가구"
  - "인테리어"
  # 자유 추가/삭제
```

---

## 8. 로컬 디버깅

```powershell
cd C:\Users\naked\Documents\agent\bizinfo-monitor
pip install -r requirements.txt

# Mock 데이터로 카톡 발송 없이 HTML만 생성
python src\main.py --mock --no-send --no-cache

# 실 API 호출 (전일 날짜 자동) — 카톡 발송 없이
python src\main.py --no-send --no-cache

# 특정 날짜 조회
python src\main.py --date=2026-05-26 --no-send --no-cache
```

생성된 HTML: `docs\reports\YYYY-MM-DD-bizinfo.html`

---

## 9. 트러블슈팅

| 증상 | 원인 / 해결 |
|---|---|
| `BIZINFO_API_KEY env 변수가 비어있습니다` | GitHub Secret 등록 또는 `.env` 파일 확인 |
| `API error code=...` | 공공데이터포털에서 API 활용신청 상태 / 인증키 유효성 확인 |
| 카톡 미수신 | KAKAO_REFRESH_TOKEN 만료 가능성 — `daily-order-report` 에서 재발급 후 양쪽 동기화 |
| 매칭 0건만 계속 | `config.yaml` 키워드 확인 (회사명 표기 변형 추가) |
| HTML 페이지 404 | GitHub Pages 활성화 확인 (Settings → Pages) |
| 보고서 본문 비어있음 | XML 응답 필드명 다를 가능성 — Actions 로그에서 `body[:300]=` 확인 후 `bizinfo_client._normalize_item` 수정 |

---

## 10. 일일 트래픽

공공데이터포털 본 API 일일 호출 한도: **100건**
- 본 시스템은 하루 1회, 페이지당 100 row → 평균 1~5 호출 사용
- 100건 제한 도달 시 익일 0시 리셋
