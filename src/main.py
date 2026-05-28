"""기업마당 모니터링 진입점.

매일 14:00 KST GitHub Actions 에서 실행.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import traceback
from datetime import datetime, timedelta
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import pytz
import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import bizinfo_client, kakao_client, report_builder  # noqa: E402

KST = pytz.timezone("Asia/Seoul")


def load_config() -> dict:
    cfg_path = ROOT / "config.yaml"
    with cfg_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mock", action="store_true", help="Use mock XML fixture (no API call)")
    parser.add_argument("--no-send", action="store_true", help="Don't send Kakao, don't push git")
    parser.add_argument("--no-cache", action="store_true", help="Ignore seen.json (re-emit all)")
    parser.add_argument(
        "--date",
        help="조회 기준일 (YYYY-MM-DD). 미지정 시 어제. --days 와 함께 쓰면 그날까지의 N일.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=0,
        help="조회 일수. --days 20 = 오늘 기준 -20일 ~ 오늘 (총 21일). 0이면 단일일 (기본).",
    )
    parser.add_argument(
        "--slot-suffix",
        default="",
        help="보고서 파일명 suffix (기본 'bizinfo'). 예: --slot-suffix=last20d → 파일명 YYYY-MM-DD-last20d.html",
    )
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    cfg = load_config()

    now_kst = datetime.now(KST)
    today_str = now_kst.strftime("%Y-%m-%d")

    if args.days > 0:
        # 범위 조회 모드
        end_date = args.date or today_str
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        start_dt = end_dt - timedelta(days=args.days)
        start_date = start_dt.strftime("%Y-%m-%d")
        period_label = f"{start_date} ~ {end_date} 등록 공고 (최근 {args.days}일)"
        target_date = end_date  # log 용
        slot_id = args.slot_suffix or f"last{args.days}d"
    elif args.date:
        target_date = args.date
        start_date = end_date = target_date
        period_label = f"{target_date} 등록 공고"
        slot_id = args.slot_suffix or "bizinfo"
    else:
        start, _ = bizinfo_client.yesterday_range_kst(now_kst)
        target_date = start
        start_date = end_date = target_date
        period_label = f"{target_date} 등록 공고 (전일 신규)"
        slot_id = args.slot_suffix or "bizinfo"

    slot_filename_date = today_str
    slot_filename = f"{slot_filename_date}-{slot_id}.html"

    print(f"[BIZINFO] range={start_date}~{end_date} now_kst={now_kst.strftime('%Y-%m-%d %H:%M')} slot={slot_id}")

    # ===== 1. API 호출 또는 mock =====
    errors: list[str] = []
    try:
        if args.mock:
            postings = _load_mock()
            print(f"[MOCK] {len(postings)} postings loaded from fixture")
        else:
            api_key = bizinfo_client.from_env()
            postings, fetch_errors = bizinfo_client.fetch_postings(
                api_key=api_key,
                start_date=start_date,
                end_date=end_date,
                endpoint=cfg["api"]["endpoint"],
                num_of_rows=cfg["api"]["num_of_rows"],
                max_pages=cfg["api"]["max_pages"],
                timeout=cfg["api"]["timeout_seconds"],
            )
            errors.extend(fetch_errors)
            print(f"[LIVE] {len(postings)} postings fetched (errors={len(fetch_errors)})")
            for e in fetch_errors:
                print(f"  [WARN] {e}")
    except Exception as e:
        traceback.print_exc()
        _emergency_kakao(f"🚨 기업마당 모니터링 치명적 오류\n{type(e).__name__}: {e}", args.no_send)
        return 1

    fetched_total = len(postings)

    # ===== 2. 회사명 + 룰 매칭 =====
    matched = bizinfo_client.apply_matching(
        postings,
        priority_keywords=cfg.get("priority_keywords") or [],
        rules=cfg.get("rules") or [],
        case_insensitive=cfg["match"]["case_insensitive"],
        strip_whitespace=cfg["match"]["strip_whitespace"],
        match_fields=cfg["match"].get("fields"),
    )
    print(f"[MATCH] {len(matched)}/{fetched_total} matched (priority+rules)")

    # ===== 3. seen 캐시 적용 (이미 본 공고 제외) =====
    cache_path = ROOT / "data" / "seen.json"
    if args.no_cache:
        new_matched = matched
        seen = set()
    else:
        seen = bizinfo_client.load_seen(cache_path)
        new_matched = bizinfo_client.filter_new(matched, seen)
        print(f"[CACHE] {len(new_matched)} new (filtered {len(matched) - len(new_matched)} already seen)")

    # ===== 4. 보고서 작성 =====
    reports_dir = ROOT / "docs" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / slot_filename

    html = report_builder.format_html_report(
        new_matched,
        fetched_total=fetched_total,
        period_label=period_label,
        generated_at=now_kst.strftime("%Y-%m-%d %H:%M KST"),
        priority_keywords=cfg.get("priority_keywords") or [],
        rules=cfg.get("rules") or [],
        errors=errors,
    )
    report_path.write_text(html, encoding="utf-8")
    print(f"[HTML] Saved: {report_path} ({len(html):,} chars)")

    _update_index(reports_dir)

    # ===== 5. URL 계산 =====
    base_url = os.getenv("REPORT_BASE_URL", "https://nakedsoul75.github.io/bizinfo-monitor/reports")
    report_url = f"{base_url.rstrip('/')}/{slot_filename}"

    # ===== 6. git 푸시 (보고서 + 인덱스 + seen 캐시) =====
    if not args.no_send and not os.getenv("SKIP_GIT_PUSH"):
        # 매칭된 새 공고를 seen에 추가 (commit 전에 저장해야 git add 됨)
        seen.update(p.pblanc_id for p in new_matched if p.pblanc_id)
        bizinfo_client.save_seen(cache_path, seen)
        _git_publish(slot_filename_date)

    # ===== 7. 카카오 발송 =====
    notify_cfg = cfg.get("notify", {})
    if not new_matched and not notify_cfg.get("send_when_empty", True):
        print("[SKIP] 매칭 0건 + send_when_empty=false → 카톡 발송 안 함")
        return 0

    short_msg = report_builder.format_short_kakao(
        new_matched, fetched_total, period_label, report_url, errors=errors,
    )
    print(f"\n{'=' * 50}\n[Kakao Message]\n{'=' * 50}\n{short_msg}\n{'=' * 50}\n")

    if args.no_send or os.getenv("DRY_RUN") == "true":
        print(f"[DRY RUN] Skipping Kakao. URL: {report_url}")
        return 0

    try:
        kc = kakao_client.from_env()
        result = kc.send_text(short_msg, link_url=report_url)
        print(f"[SEND] Kakao response: {result}")
    except Exception as e:
        traceback.print_exc()
        print(f"[ERR] Kakao 발송 실패: {e}")
        return 1

    print(f"[REPORT URL] {report_url}")
    return 0


def _load_mock() -> list:
    """tests/mock_bizinfo.xml 파싱."""
    fixture = ROOT / "tests" / "mock_bizinfo.xml"
    if not fixture.exists():
        raise FileNotFoundError(f"Mock 파일 없음: {fixture}")
    content = fixture.read_bytes()
    postings, _ = bizinfo_client._parse_xml(content)
    return postings


def _update_index(reports_dir: Path) -> None:
    pattern = re.compile(r"^(\d{4}-\d{2}-\d{2})-(\w+)\.html$")
    entries = []
    for f in reports_dir.iterdir():
        m = pattern.match(f.name)
        if m and f.name != "index.html":
            entries.append((m.group(1), m.group(2), f.name))
    entries.sort(key=lambda e: (e[0], e[1]), reverse=True)
    index_html = report_builder.format_index_html(entries)
    (reports_dir / "index.html").write_text(index_html, encoding="utf-8")


def _git_publish(label: str) -> None:
    try:
        subprocess.run(["git", "add", "docs/reports/", "data/seen.json"],
                       cwd=ROOT, check=True, capture_output=True, text=True)
        diff = subprocess.run(["git", "diff", "--cached", "--quiet"],
                              cwd=ROOT, capture_output=True)
        if diff.returncode == 0:
            print("[GIT] No changes to push.")
            return
        subprocess.run(["git", "commit", "-m", f"Bizinfo report: {label}"],
                       cwd=ROOT, check=True, capture_output=True, text=True)
        subprocess.run(["git", "push", "origin", "main"],
                       cwd=ROOT, check=True, capture_output=True, text=True, timeout=60)
        print("[GIT] Pushed to GitHub. Pages will update in 1-2 min.")
    except subprocess.CalledProcessError as e:
        print(f"[GIT WARN] {e.stderr if e.stderr else e}")
    except Exception as e:
        print(f"[GIT WARN] {type(e).__name__}: {e}")


def _emergency_kakao(text: str, no_send: bool) -> None:
    if no_send:
        return
    if not os.getenv("KAKAO_REFRESH_TOKEN"):
        return
    try:
        kakao_client.from_env().send_text(text)
    except Exception:
        pass


if __name__ == "__main__":
    sys.exit(main())
