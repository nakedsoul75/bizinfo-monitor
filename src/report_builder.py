"""기업마당 모니터링 보고서 빌더 — HTML / 카카오톡 단문."""
from __future__ import annotations

import html
import re
from datetime import datetime

from src.bizinfo_client import Posting


# ===== 텍스트 헬퍼 =====

def _esc(s: str) -> str:
    return html.escape(s or "", quote=True)


def _clean(s: str, max_len: int = 220) -> str:
    """HTML 태그·과도한 공백 제거 + 길이 컷."""
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > max_len:
        s = s[: max_len - 1].rstrip() + "…"
    return s


def _highlight_keywords(text: str, keywords: list[str]) -> str:
    """매칭 키워드를 <mark>로 강조 (case-insensitive)."""
    esc = _esc(text)
    for kw in sorted(keywords, key=len, reverse=True):
        if not kw:
            continue
        esc = re.sub(
            f"({re.escape(_esc(kw))})",
            r'<mark>\1</mark>',
            esc,
            flags=re.IGNORECASE,
        )
    return esc


def _dday_badge(days: int | None) -> str:
    if days is None:
        return '<span class="badge badge-gray">마감일 미상</span>'
    if days < 0:
        return f'<span class="badge badge-gray">마감 ({-days}일 경과)</span>'
    if days == 0:
        return '<span class="badge badge-red">D-DAY</span>'
    if days <= 7:
        return f'<span class="badge badge-red">D-{days}</span>'
    if days <= 30:
        return f'<span class="badge badge-orange">D-{days}</span>'
    return f'<span class="badge badge-blue">D-{days}</span>'


# ===== 카카오톡 단문 =====

def format_short_kakao(
    matched: list[Posting],
    fetched_total: int,
    period_label: str,
    report_url: str,
    errors: list[str] | None = None,
) -> str:
    """카톡 알림용 단문 (4000자 미만)."""
    priority = [p for p in matched if p.is_priority]
    general = [p for p in matched if not p.is_priority]

    header = f"🏛️ 기업마당 모니터링 — {period_label}\n"
    header += f"  • 신규 등록 공고 전체 {fetched_total}건 조회 → 매칭 {len(matched)}건"

    body = ""
    if priority:
        body += f"\n\n⭐ 우선 — {len(priority)}건"
        for p in priority[:5]:
            dday = p.days_to_deadline
            dday_str = f"D-{dday}" if dday is not None and dday >= 0 else (f"마감 {-dday}일 경과" if dday is not None else "마감미상")
            tag = _short_tag(p)
            body += f"\n  · [{dday_str}]{tag} {p.title[:55]}"

    if general:
        body += f"\n\n📋 일반 — {len(general)}건"
        for p in general[:5]:
            tag = _short_tag(p)
            body += f"\n  ·{tag} {p.title[:55]}"

    if not matched:
        body = "\n\n오늘 매칭된 공고가 없습니다."

    footer = f"\n\n🔗 상세 보고서 (링크·요약·키워드 강조 포함):\n{report_url}"

    if errors:
        footer += "\n\n⚠️ 오류:"
        for e in errors[:2]:
            footer += f"\n  · {e[:120]}"

    return header + body + footer


def _short_tag(p: Posting) -> str:
    """카톡 단문용 매칭 태그 (회사명 또는 룰 라벨 첫 1~2개)."""
    tags = []
    if p.matched_priority:
        tags.append("회사명")
    for r in p.matched_rules[:2]:
        tags.append(r["label"])
    if not tags:
        return ""
    return " [" + "·".join(tags[:2]) + "]"


# ===== HTML 보고서 =====

def format_html_report(
    matched: list[Posting],
    fetched_total: int,
    period_label: str,
    *,
    generated_at: str,
    priority_keywords: list[str],
    rules: list[dict],
    errors: list[str] | None = None,
) -> str:
    """전체 HTML 보고서 — GitHub Pages 게시용."""
    priority = sorted(
        [p for p in matched if p.is_priority],
        key=lambda p: (p.days_to_deadline if p.days_to_deadline is not None else 9999),
    )
    general = sorted(
        [p for p in matched if not p.is_priority],
        key=lambda p: (p.days_to_deadline if p.days_to_deadline is not None else 9999),
    )

    cards_priority = "\n".join(_card_html(p, "priority") for p in priority) or _empty_state("우선 매칭 공고 없음")
    cards_general = "\n".join(_card_html(p, "general") for p in general) or _empty_state("일반 매칭 공고 없음")

    kw_chips_priority = " ".join(f'<span class="chip chip-priority">{_esc(k)}</span>' for k in priority_keywords)
    rule_rows = "\n".join(_rule_row_html(r) for r in rules) or '<div class="rule-empty">등록된 룰 없음</div>'

    error_section = ""
    if errors:
        items = "".join(f"<li>{_esc(e)}</li>" for e in errors)
        error_section = f'<section class="errors"><h3>⚠️ 오류 / 경고</h3><ul>{items}</ul></section>'

    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>기업마당 모니터링 — {_esc(period_label)}</title>
<style>
{_CSS}
</style>
</head>
<body>
<div class="wrap">

  <header class="hd">
    <div class="hd-row">
      <h1>🏛️ 기업마당 모니터링</h1>
      <div class="hd-meta">{_esc(generated_at)}</div>
    </div>
    <div class="hd-period">조회 기간: <b>{_esc(period_label)}</b> (공고 등록일 기준)</div>
  </header>

  <section class="summary">
    <div class="kpi">
      <div class="kpi-label">조회된 신규 공고</div>
      <div class="kpi-value">{fetched_total}<span class="kpi-unit">건</span></div>
    </div>
    <div class="kpi kpi-hl">
      <div class="kpi-label">⭐ 우선 (회사명)</div>
      <div class="kpi-value">{len(priority)}<span class="kpi-unit">건</span></div>
    </div>
    <div class="kpi">
      <div class="kpi-label">📋 일반 (업종)</div>
      <div class="kpi-value">{len(general)}<span class="kpi-unit">건</span></div>
    </div>
  </section>

  <section class="kw">
    <h3>적용 키워드 · 룰</h3>
    <div class="kw-row"><b class="kw-tag">⭐ 회사명</b> {kw_chips_priority}</div>
    <div class="rule-list">
      {rule_rows}
    </div>
  </section>

  <section>
    <h2 class="sec-title">⭐ 우선 매칭 ({len(priority)})</h2>
    {cards_priority}
  </section>

  <section>
    <h2 class="sec-title">📋 일반 매칭 ({len(general)})</h2>
    {cards_general}
  </section>

  {error_section}

  <footer class="ft">
    <div>출처: <a href="https://www.bizinfo.go.kr" target="_blank">기업마당 (bizinfo.go.kr)</a> · 공공데이터포털 OpenAPI</div>
    <div>매일 14:00 KST 자동 발송 · <a href="./">이전 보고서 인덱스</a></div>
  </footer>

</div>
</body>
</html>"""


def _card_html(p: Posting, kind: str) -> str:
    dday = _dday_badge(p.days_to_deadline)
    highlight_terms = p.all_matched_terms
    title_hl = _highlight_keywords(p.title or "(제목 없음)", highlight_terms)
    summary_hl = _highlight_keywords(_clean(p.summary, 280), highlight_terms)
    target_hl = _highlight_keywords(_clean(p.target, 120), highlight_terms) if p.target else ""

    chips = []
    for kw in p.matched_priority:
        chips.append(f'<span class="chip chip-priority" title="회사명 매칭">⭐ {_esc(kw)}</span>')
    for r in p.matched_rules:
        cls = "chip-rule-priority" if r["priority"] else "chip-rule"
        terms_str = ", ".join(r.get("terms", []))
        chips.append(
            f'<span class="chip {cls}" title="룰 매칭: {_esc(terms_str)}">{_esc(r["label"])}</span>'
        )
    matched_chips = " ".join(chips)

    url = p.url or "https://www.bizinfo.go.kr"
    if url and not url.startswith("http"):
        # 상대 경로면 bizinfo 도메인 prefix
        url = "https://www.bizinfo.go.kr" + (url if url.startswith("/") else "/" + url)

    target_row = f'<div class="row"><span class="row-label">대상</span><span class="row-val">{target_hl}</span></div>' if target_hl else ""
    org_row = f'<div class="row"><span class="row-label">기관</span><span class="row-val">{_esc(p.org)}</span></div>' if p.org else ""
    period_row = ""
    if p.start_date or p.end_date:
        period_row = f'<div class="row"><span class="row-label">신청기간</span><span class="row-val">{_esc(p.start_date)} ~ {_esc(p.end_date)}</span></div>'

    return f"""<article class="card card-{kind}">
  <div class="card-top">
    <div class="card-badges">{dday}</div>
    <div class="card-keywords">{matched_chips}</div>
  </div>
  <h3 class="card-title"><a href="{_esc(url)}" target="_blank" rel="noopener">{title_hl}</a></h3>
  <div class="card-summary">{summary_hl}</div>
  <div class="card-meta">
    {target_row}
    {org_row}
    {period_row}
  </div>
  <div class="card-actions">
    <a class="btn" href="{_esc(url)}" target="_blank" rel="noopener">공고 원문 보기 →</a>
  </div>
</article>"""


def _empty_state(msg: str) -> str:
    return f'<div class="empty">{_esc(msg)}</div>'


def _rule_row_html(rule: dict) -> str:
    """적용 룰 표시 — 라벨 + 타입(AND/OR/구문) + terms + exclude."""
    label = rule.get("label", rule.get("id", ""))
    rtype = (rule.get("type") or "any").lower()
    type_label = {"all": "AND", "any": "OR", "phrase": "구문"}.get(rtype, rtype.upper())
    terms = rule.get("terms") or []
    exclude = rule.get("exclude") or []
    star = "⭐ " if rule.get("priority") else ""
    cls = "chip-rule-priority" if rule.get("priority") else "chip-rule"

    terms_html = " ".join(f'<code class="term">{_esc(t)}</code>' for t in terms)
    exclude_html = ""
    if exclude:
        ex_html = " ".join(f'<code class="term term-ex">{_esc(t)}</code>' for t in exclude)
        exclude_html = f' <span class="ex-label">제외:</span> {ex_html}'

    return f"""<div class="rule-row">
  <span class="chip {cls}">{star}{_esc(label)}</span>
  <span class="rule-type">{type_label}</span>
  {terms_html}{exclude_html}
</div>"""


# ===== 인덱스 페이지 =====

def format_index_html(entries: list[tuple[str, str, str]]) -> str:
    """reports/ 폴더 인덱스. entries: list of (date, slot, filename)."""
    items = "\n".join(
        f'<li><a href="{_esc(name)}">{_esc(d)} — {_esc(s)}</a></li>'
        for d, s, name in entries
    )
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>기업마당 모니터링 — 보고서 목록</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, "Pretendard", "Segoe UI", sans-serif; max-width: 720px; margin: 40px auto; padding: 0 20px; color: #1a1a1a; }}
h1 {{ font-size: 1.6em; }}
ul {{ list-style: none; padding: 0; }}
li {{ padding: 12px 16px; border-bottom: 1px solid #eee; }}
li:hover {{ background: #f7f7f7; }}
a {{ color: #2563eb; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
.empty {{ color: #999; padding: 24px; text-align: center; }}
</style>
</head>
<body>
<h1>🏛️ 기업마당 모니터링 — 보고서 목록</h1>
<p>최신순. 매일 14:00 KST 자동 갱신.</p>
<ul>
{items if entries else '<li class="empty">아직 보고서가 없습니다.</li>'}
</ul>
</body>
</html>"""


# ===== CSS (HTML 보고서용) =====

_CSS = """
* { box-sizing: border-box; }
body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Pretendard", "Segoe UI", "Noto Sans KR", sans-serif; background: #f4f5f7; color: #1a1a1a; line-height: 1.55; }
.wrap { max-width: 880px; margin: 0 auto; padding: 24px 16px 80px; }

.hd { background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 100%); color: #fff; padding: 24px 28px; border-radius: 12px; margin-bottom: 16px; }
.hd h1 { margin: 0; font-size: 1.5em; }
.hd-row { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; }
.hd-meta { opacity: 0.85; font-size: 0.85em; }
.hd-period { margin-top: 8px; font-size: 0.95em; opacity: 0.9; }

.summary { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 20px; }
.kpi { background: #fff; padding: 18px 20px; border-radius: 10px; border: 1px solid #e5e7eb; }
.kpi-hl { border-color: #fbbf24; background: linear-gradient(180deg, #fffbeb 0%, #fff 100%); }
.kpi-label { font-size: 0.82em; color: #6b7280; margin-bottom: 4px; }
.kpi-value { font-size: 1.8em; font-weight: 700; }
.kpi-unit { font-size: 0.55em; font-weight: 400; color: #6b7280; margin-left: 4px; }
@media (max-width: 560px) { .summary { grid-template-columns: 1fr; } }

.kw { background: #fff; padding: 14px 18px; border-radius: 10px; border: 1px solid #e5e7eb; margin-bottom: 24px; }
.kw h3 { margin: 0 0 10px; font-size: 0.95em; color: #374151; }
.kw-row { margin: 6px 0; font-size: 0.88em; }
.kw-tag { display: inline-block; min-width: 36px; color: #6b7280; margin-right: 8px; }
.chip { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 0.78em; margin: 2px; background: #f3f4f6; color: #4b5563; }
.chip-priority { background: #fef3c7; color: #92400e; font-weight: 600; }
.chip-general { background: #dbeafe; color: #1e40af; }
.chip-rule { background: #ede9fe; color: #5b21b6; }
.chip-rule-priority { background: #fee2e2; color: #991b1b; font-weight: 600; }
.chip-empty { color: #999; font-style: italic; background: transparent; }

.rule-list { margin-top: 10px; display: flex; flex-direction: column; gap: 6px; }
.rule-row { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; padding: 6px 10px; background: #fafaf9; border-radius: 6px; font-size: 0.82em; }
.rule-type { font-size: 0.72em; font-weight: 700; color: #6b7280; padding: 1px 6px; background: #e5e7eb; border-radius: 4px; }
.term { font-size: 0.85em; color: #374151; background: #fff; padding: 1px 6px; border: 1px solid #e5e7eb; border-radius: 4px; font-family: ui-monospace, "SFMono-Regular", Menlo, monospace; }
.term-ex { color: #b91c1c; background: #fef2f2; border-color: #fecaca; }
.ex-label { font-size: 0.78em; color: #b91c1c; font-weight: 600; margin-left: 4px; }
.rule-empty { color: #999; font-style: italic; padding: 8px; }

.sec-title { margin: 32px 0 14px; font-size: 1.15em; padding-bottom: 8px; border-bottom: 2px solid #e5e7eb; }

.card { background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; padding: 18px 20px; margin-bottom: 14px; transition: box-shadow 0.15s; }
.card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.06); }
.card-priority { border-left: 4px solid #f59e0b; }
.card-general { border-left: 4px solid #3b82f6; }
.card-top { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 8px; }
.card-title { margin: 6px 0 10px; font-size: 1.05em; line-height: 1.4; }
.card-title a { color: #1a1a1a; text-decoration: none; }
.card-title a:hover { color: #2563eb; text-decoration: underline; }
.card-summary { color: #4b5563; font-size: 0.93em; margin-bottom: 12px; }
.card-meta { font-size: 0.85em; color: #6b7280; border-top: 1px dashed #e5e7eb; padding-top: 10px; margin-top: 10px; }
.row { display: flex; gap: 10px; margin: 3px 0; }
.row-label { min-width: 56px; color: #9ca3af; font-size: 0.85em; }
.row-val { flex: 1; }
.card-actions { margin-top: 12px; }
.btn { display: inline-block; padding: 7px 14px; background: #2563eb; color: #fff; text-decoration: none; border-radius: 6px; font-size: 0.88em; }
.btn:hover { background: #1d4ed8; }

.badge { display: inline-block; padding: 3px 9px; border-radius: 5px; font-size: 0.78em; font-weight: 600; }
.badge-red { background: #fee2e2; color: #b91c1c; }
.badge-orange { background: #ffedd5; color: #c2410c; }
.badge-blue { background: #dbeafe; color: #1e40af; }
.badge-gray { background: #f3f4f6; color: #6b7280; }

mark { background: #fef08a; color: inherit; padding: 0 2px; border-radius: 2px; font-weight: 600; }

.empty { background: #fff; border: 1px dashed #d1d5db; padding: 24px; text-align: center; color: #9ca3af; border-radius: 10px; }

.errors { background: #fef2f2; border: 1px solid #fecaca; border-radius: 10px; padding: 14px 18px; margin-top: 20px; }
.errors h3 { margin: 0 0 8px; color: #b91c1c; font-size: 0.95em; }
.errors ul { margin: 0; padding-left: 20px; font-size: 0.85em; color: #7f1d1d; }

.ft { margin-top: 40px; padding-top: 16px; border-top: 1px solid #e5e7eb; font-size: 0.82em; color: #6b7280; text-align: center; }
.ft div { margin: 4px 0; }
.ft a { color: #2563eb; }
"""
