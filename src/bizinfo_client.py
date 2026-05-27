"""기업마당 (공공데이터포털) 중소벤처기업부 사업공고 API 클라이언트.

API: https://www.data.go.kr/data/15113297/openapi.do
End Point: https://apis.data.go.kr/1421000/mssBizService_v2/getbizList_v2
일일 트래픽: 100건 — 페이지네이션 시 주의
"""
from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import requests


@dataclass
class Posting:
    """API 응답 1건을 정규화한 객체. 응답 필드명은 향후 실제 호출로 검증 필요."""
    pblanc_id: str               # 공고 ID (중복 회피 키)
    title: str                   # 공고명 (pblancNm)
    summary: str                 # 사업개요 (bsnsSumryCn)
    target: str                  # 신청대상 (trgetNm)
    org: str                     # 접수/시행 기관
    url: str                     # 상세 공고 URL
    start_date: str              # 신청 시작일 (pblancBgngDt)
    end_date: str                # 신청 마감일 (pblancEndDt)
    registered_at: str           # 공고 등록일시 (creatPnttm)
    raw: dict[str, Any] = field(default_factory=dict)  # 원본 보존
    # 매칭 결과 (후처리에서 채움)
    matched_priority: list[str] = field(default_factory=list)
    matched_general: list[str] = field(default_factory=list)

    @property
    def is_priority(self) -> bool:
        return bool(self.matched_priority)

    @property
    def all_matched(self) -> list[str]:
        return self.matched_priority + self.matched_general

    @property
    def days_to_deadline(self) -> int | None:
        """마감까지 D-day. 파싱 실패 시 None."""
        if not self.end_date:
            return None
        for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y.%m.%d"):
            try:
                end = datetime.strptime(self.end_date[:10], fmt)
                today = datetime.now()
                return (end.date() - today.date()).days
            except ValueError:
                continue
        return None


# ===== API 호출 =====

def fetch_postings(
    api_key: str,
    start_date: str,
    end_date: str,
    *,
    endpoint: str = "https://apis.data.go.kr/1421000/mssBizService_v2/getbizList_v2",
    num_of_rows: int = 100,
    max_pages: int = 5,
    timeout: int = 30,
) -> tuple[list[Posting], list[str]]:
    """기업마당 사업공고 조회. (postings, errors) 반환.

    startDate / endDate 는 공고등록일 기준 (입력 형식 YYYY-MM-DD).
    """
    errors: list[str] = []
    postings: list[Posting] = []

    for page in range(1, max_pages + 1):
        params = {
            "serviceKey": api_key,
            "pageNo": page,
            "numOfRows": num_of_rows,
            "startDate": start_date,
            "endDate": end_date,
        }
        try:
            resp = requests.get(endpoint, params=params, timeout=timeout)
            resp.raise_for_status()
        except requests.RequestException as e:
            errors.append(f"page={page}: {type(e).__name__}: {str(e)[:200]}")
            break

        try:
            page_postings, total_count = _parse_xml(resp.content)
        except Exception as e:
            errors.append(f"page={page} XML parse: {type(e).__name__}: {str(e)[:200]}")
            # 본문 일부 로깅 (필드명 디버깅용)
            errors.append(f"  body[:300]={resp.text[:300]}")
            break

        if not page_postings:
            break

        postings.extend(page_postings)

        if len(postings) >= total_count or len(page_postings) < num_of_rows:
            break

    return postings, errors


def _parse_xml(content: bytes) -> tuple[list[Posting], int]:
    """공공데이터포털 표준 응답 XML 파싱.

    응답 구조 (추정 — 실제 호출 후 검증):
    <response>
      <header><resultCode>00</resultCode><resultMsg>OK</resultMsg></header>
      <body>
        <items><item>...</item><item>...</item></items>
        <numOfRows>100</numOfRows><pageNo>1</pageNo><totalCount>123</totalCount>
      </body>
    </response>
    """
    root = ET.fromstring(content)

    # 에러 응답 처리 — 공공데이터포털 표준
    result_code = _findtext(root, ".//resultCode") or _findtext(root, ".//cmmMsgHeader/returnReasonCode")
    if result_code and result_code not in ("00", "0"):
        msg = _findtext(root, ".//resultMsg") or _findtext(root, ".//cmmMsgHeader/returnAuthMsg") or ""
        raise RuntimeError(f"API error code={result_code} msg={msg}")

    total = int(_findtext(root, ".//totalCount") or "0")

    items: list[Posting] = []
    for item in root.iter("item"):
        raw = {child.tag: (child.text or "").strip() for child in item}
        items.append(_normalize_item(raw))

    return items, total


def _normalize_item(raw: dict[str, str]) -> Posting:
    """원본 필드명이 변동 가능하므로 후보 키를 모두 시도."""
    def pick(*keys: str) -> str:
        for k in keys:
            if k in raw and raw[k]:
                return raw[k]
        return ""

    pid = pick("pblancId", "pblnId", "id")
    if not pid:
        # ID가 없으면 URL이나 제목으로 폴백 식별자 생성
        pid = pick("pblancUrl", "url") or pick("pblancNm", "title") or ""

    return Posting(
        pblanc_id=pid,
        title=pick("pblancNm", "title", "bsnsTtl"),
        summary=pick("bsnsSumryCn", "summary", "cn"),
        target=pick("trgetNm", "target", "applcntTrget"),
        org=pick("rceptInsttNm", "excInsttNm", "jrsdInsttNm", "org"),
        url=pick("pblancUrl", "url", "detailUrl"),
        start_date=pick("reqstBgngDt", "pblancBgngDt", "startDate"),
        end_date=pick("reqstEndDt", "pblancEndDt", "endDate"),
        registered_at=pick("creatPnttm", "registeredAt", "regDate"),
        raw=raw,
    )


def _findtext(root: ET.Element, path: str) -> str:
    el = root.find(path)
    return (el.text or "").strip() if el is not None and el.text else ""


# ===== 키워드 매칭 =====

def filter_by_keywords(
    postings: list[Posting],
    priority_keywords: list[str],
    general_keywords: list[str],
    *,
    case_insensitive: bool = True,
    strip_whitespace: bool = True,
    match_fields: list[str] | None = None,
) -> list[Posting]:
    """키워드 매칭. 매칭된 공고만 반환 (matched_priority / matched_general 채워서)."""
    matched: list[Posting] = []
    for p in postings:
        text_blob = _build_text_blob(p, match_fields, strip_whitespace)
        haystack = text_blob.lower() if case_insensitive else text_blob

        for kw in priority_keywords:
            needle = kw.lower() if case_insensitive else kw
            if needle and needle in haystack:
                p.matched_priority.append(kw)

        for kw in general_keywords:
            needle = kw.lower() if case_insensitive else kw
            if needle and needle in haystack:
                p.matched_general.append(kw)

        if p.is_priority or p.matched_general:
            matched.append(p)

    return matched


def _build_text_blob(p: Posting, fields: list[str] | None, strip_ws: bool) -> str:
    """매칭 대상 필드들을 하나의 문자열로 결합."""
    if fields:
        parts = [p.raw.get(f, "") for f in fields]
    else:
        parts = [p.title, p.summary, p.target, p.org]
    blob = " ".join(parts)
    if strip_ws:
        # 띄어쓰기·줄바꿈 제거해서 "콤마 나인" → "콤마나인" 도 매칭
        return "".join(blob.split())
    return blob


# ===== 중복 회피 (seen 캐시) =====

def load_seen(cache_path: Path) -> set[str]:
    if not cache_path.exists():
        return set()
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        return set(data.get("seen", []))
    except (json.JSONDecodeError, OSError):
        return set()


def save_seen(cache_path: Path, seen: set[str], *, keep_last: int = 5000) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    # 최근 N건만 보존 (무한 증가 방지)
    items = list(seen)[-keep_last:]
    cache_path.write_text(
        json.dumps({"seen": items, "updated_at": datetime.now().isoformat()}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def filter_new(postings: list[Posting], seen: set[str]) -> list[Posting]:
    """이미 본 공고는 제외."""
    return [p for p in postings if p.pblanc_id and p.pblanc_id not in seen]


# ===== 기간 헬퍼 =====

def yesterday_range_kst(now_kst: datetime) -> tuple[str, str]:
    """전일 0시 ~ 23:59 (등록일 기준)."""
    y = now_kst - timedelta(days=1)
    s = y.strftime("%Y-%m-%d")
    return s, s


# ===== env 헬퍼 =====

def from_env() -> str:
    key = os.environ.get("BIZINFO_API_KEY", "").strip()
    if not key:
        raise RuntimeError("BIZINFO_API_KEY env 변수가 비어있습니다. .env 또는 GitHub Secret 확인.")
    return key
