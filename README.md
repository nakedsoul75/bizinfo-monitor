# bizinfo-monitor

기업마당(bizinfo.go.kr)의 중소벤처기업부 사업공고 OpenAPI를 매일 1회 호출하여,
지정 키워드(창대 · 디엘나인 · 콤마나인 · 팩토리나인 등) 매칭 공고를 HTML 보고서로 정리해
**매일 14:00 KST 카카오톡으로 발송**.

## 구성

| 구성요소 | 역할 | 비용 |
|---|---|---|
| 공공데이터포털 OpenAPI | 사업공고 조회 | 무료 (일일 100건) |
| 카카오톡 메모톡 API | 본인에게 알림 | 무료 |
| GitHub Actions | 매일 14:00 cron | 무료 (월 2,000분 내) |
| GitHub Pages | HTML 보고서 호스팅 | 무료 |

## 발송 시각 & 정책

- **시각**: 매일 14:00 KST (UTC 05:00)
- **조회 범위**: 전일 등록된 신규 공고
- **매칭**: `config.yaml` 의 우선/일반 키워드와 부분 일치 (대소문자·공백 무시)
- **중복 회피**: 한 번 알린 공고는 `data/seen.json` 에 ID 캐시하여 재알림 안 함

## 디렉터리

```
bizinfo-monitor/
├── .github/workflows/bizinfo.yml   # 매일 14:00 cron
├── src/
│   ├── main.py                     # 진입점
│   ├── bizinfo_client.py           # API 호출 + XML 파싱 + 매칭 + 캐시
│   ├── report_builder.py           # HTML / 카톡 단문 빌더
│   └── kakao_client.py             # 카카오 메모톡
├── docs/
│   ├── index.html                  # Pages 홈 → reports/ 리다이렉트
│   ├── reports/                    # 일별 HTML 보고서
│   └── SETUP.md                    # 상세 셋업 가이드
├── data/
│   └── seen.json                   # 본 공고 ID 캐시 (commit 됨)
├── tests/
│   └── mock_bizinfo.xml            # 로컬 테스트용 XML 픽스처
├── config.yaml                     # 키워드·매칭·알림 정책
├── .env.example
├── .gitignore                      # .env 보호
├── requirements.txt
└── README.md
```

## 셋업

[docs/SETUP.md](docs/SETUP.md) — 단계별 가이드 (20분).

## 로컬 디버깅

```powershell
pip install -r requirements.txt
python src\main.py --mock --no-send --no-cache    # Mock + 발송 없이 HTML만
python src\main.py --no-send --no-cache           # 실 API + 발송 없이
python src\main.py --date=2026-05-26 --no-send    # 특정 날짜
```

## 키워드 수정

`config.yaml` 편집 → git push → 다음 14시부터 반영.

## 보고서

- 인덱스: https://nakedsoul75.github.io/bizinfo-monitor/reports/
- 매일 새 파일: `YYYY-MM-DD-bizinfo.html`

## 출처

- [공공데이터포털 — 중소벤처기업부 사업공고 OpenAPI](https://www.data.go.kr/data/15113297/openapi.do)
- 본 데이터는 공공데이터 자유이용 라이선스에 따라 활용
