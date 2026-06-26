from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from urllib.parse import quote, urlparse

from app import config
from app.models.schemas import SourceRecord, SourceType, TripRequest


NOTICE = (
    "Browser observed prices only reflect visible text on the opened page. "
    "They do not guarantee live inventory, bookable availability, or final checkout prices."
)

PRICE_PATTERNS = (
    re.compile(r"(?:\u00a5|\uffe5|RMB\s*|CNY\s*)(\d{1,6}(?:,\d{3})*(?:\.\d{1,2})?)", re.IGNORECASE),
    re.compile(r"(\d{1,6}(?:,\d{3})*(?:\.\d{1,2})?)\s*(?:\u5143|\u5757)(?:\u8d77)?"),
    re.compile(r"(?:USD\s*|\$)(\d{1,6}(?:,\d{3})*(?:\.\d{1,2})?)", re.IGNORECASE),
)

LOGIN_KEYWORDS = ("\u767b\u5f55", "\u767b\u9646", "sign in", "login", "\u8d26\u6237", "\u8d26\u53f7")
CAPTCHA_KEYWORDS = (
    "\u9a8c\u8bc1\u7801",
    "captcha",
    "\u4eba\u673a\u9a8c\u8bc1",
    "\u5b89\u5168\u9a8c\u8bc1",
    "\u6ed1\u5757",
    "verify you are human",
)

CTRIP_ENTRY_URLS = (
    "https://trains.ctrip.com/",
    "https://flights.ctrip.com/online/channel/domestic",
    "https://vacations.ctrip.com/",
    "https://www.ctrip.com/",
)


def _normalize_url(url: str) -> str | None:
    value = url.strip()
    if not value:
        return None
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return value


def _is_allowed_url(url: str) -> bool:
    allowed_domains = config.BROWSER_ALLOWED_DOMAINS
    if "*" in allowed_domains:
        return True

    hostname = (urlparse(url).hostname or "").lower()
    if not hostname:
        return False

    return any(
        hostname == domain or hostname.endswith(f".{domain}")
        for domain in allowed_domains
    )


def _parse_amount(value: str) -> float | None:
    try:
        return float(value.replace(",", ""))
    except ValueError:
        return None


def _infer_currency(price_text: str) -> str:
    text = price_text.lower()
    if "$" in text or "usd" in text:
        return "USD"
    return "CNY"


def _infer_category(text: str, url: str) -> str:
    haystack = f"{text} {url}".lower()
    if any(keyword in haystack for keyword in ("hotel", "\u4f4f\u5bbf", "\u9152\u5e97", "\u6c11\u5bbf", "\u5ba2\u6808")):
        return "hotel"
    if any(keyword in haystack for keyword in ("flight", "train", "rail", "\u673a\u7968", "\u822a\u73ed", "\u706b\u8f66", "\u9ad8\u94c1", "\u52a8\u8f66", "12306")):
        return "transport"
    if any(keyword in haystack for keyword in ("ticket", "vacation", "\u95e8\u7968", "\u666f\u533a", "\u666f\u70b9", "\u5165\u56ed", "\u5ea6\u5047")):
        return "ticket"
    return "visible_price"


def _detect_human_blocker(text: str) -> tuple[bool, str | None]:
    normalized = text.lower()
    if config.BROWSER_REQUIRE_HUMAN_ON_CAPTCHA and any(keyword.lower() in normalized for keyword in CAPTCHA_KEYWORDS):
        return True, "captcha_or_human_verification_detected"
    if config.BROWSER_REQUIRE_HUMAN_ON_LOGIN and any(keyword.lower() in normalized for keyword in LOGIN_KEYWORDS):
        return True, "login_may_be_required"
    return False, None


def _extract_price_items(
    *,
    text: str,
    url: str,
    page_title: str,
    observed_at: str,
    max_items: int,
) -> list[dict[str, Any]]:
    if max_items <= 0:
        return []

    compact_text = re.sub(r"\s+", " ", text)[:50000]
    items: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for pattern in PRICE_PATTERNS:
        for match in pattern.finditer(compact_text):
            amount = _parse_amount(match.group(1))
            if amount is None or amount <= 0 or amount > 1_000_000:
                continue

            start = max(0, match.start() - 70)
            end = min(len(compact_text), match.end() + 90)
            context = compact_text[start:end].strip()
            price_text = match.group(0).strip()
            dedupe_key = (price_text, context[:80])
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            category = _infer_category(context, url)
            confidence = 0.74 if category != "visible_price" else 0.62
            if "\u8d77" in context or "from" in context.lower():
                confidence -= 0.08

            items.append(
                {
                    "title": page_title or urlparse(url).netloc,
                    "url": url,
                    "price_text": price_text,
                    "amount": amount,
                    "currency": _infer_currency(price_text),
                    "category": category,
                    "confidence": round(max(confidence, 0.45), 2),
                    "raw_context": context[:220],
                    "observed_at": observed_at,
                    "source_type": SourceType.browser_observed,
                }
            )
            if len(items) >= max_items:
                return items

    return items


def _build_source_records(items: list[dict[str, Any]]) -> list[SourceRecord]:
    records: list[SourceRecord] = []
    for item in items:
        records.append(
            SourceRecord(
                title=f"Browser observed price: {item['price_text']}",
                url=item["url"],
                summary=(
                    f"{item['title']} visible page text contained {item['price_text']} "
                    f"for {item['category']}. {NOTICE}"
                ),
                source_type=SourceType.browser_observed,
                category=item["category"],
            )
        )
    return records


def _build_attempt_source_records(
    *,
    urls: list[str],
    status: str,
    fallback_reason: str | None,
    prepared_actions: list[str] | None = None,
) -> list[SourceRecord]:
    if status == "success":
        return []

    action_summary = ", ".join((prepared_actions or [])[:4]) or "no form action completed"
    reason_text = fallback_reason or "no visible price found"
    records: list[SourceRecord] = []
    for url in urls[:4]:
        records.append(
            SourceRecord(
                title="Browser price observation attempted",
                url=url,
                summary=(
                    f"Browser opened this page and attempted visible-price extraction. "
                    f"Status: {status}; reason: {reason_text}; actions: {action_summary}. {NOTICE}"
                ),
                source_type=SourceType.browser_observed,
                category="browser_attempt",
            )
        )
    return records


def _clean_city(value: str | None) -> str:
    return (value or "").strip()


def _build_ctrip_candidate_urls(request: TripRequest) -> list[str]:
    origin = _clean_city(request.origin_city)
    destination = _clean_city(request.destination)
    start_date = request.start_date.isoformat()
    encoded_origin = quote(origin)
    encoded_destination = quote(destination)

    if origin and destination:
        return [
            (
                "https://trains.ctrip.com/webapp/train/list"
                f"?ticketType=0&dStation={encoded_origin}&aStation={encoded_destination}&dDate={start_date}"
            ),
            "https://flights.ctrip.com/online/channel/domestic",
            f"https://vacations.ctrip.com/list/whole/d-{encoded_destination}.html",
            "https://www.ctrip.com/",
        ]

    return list(CTRIP_ENTRY_URLS)


def _collect_observation_urls(request: TripRequest) -> tuple[list[str], list[str]]:
    manual_urls = [
        url
        for url in (_normalize_url(raw_url) for raw_url in request.price_observation_urls)
        if url is not None
    ]
    generated_urls = _build_ctrip_candidate_urls(request) if request.browser_price_enabled else []

    urls: list[str] = []
    seen: set[str] = set()
    for url in [*manual_urls, *generated_urls]:
        normalized = _normalize_url(url)
        if normalized is None or normalized in seen:
            continue
        seen.add(normalized)
        urls.append(normalized)

    return urls[: config.BROWSER_MAX_URLS], generated_urls


def _try_fill_locator(locator: Any, value: str) -> bool:
    if not value:
        return False
    try:
        target = locator.first
        target.click(timeout=1500)
        target.fill(value, timeout=1500)
        try:
            target.press("Enter", timeout=1000)
        except Exception:
            pass
        return True
    except Exception:
        return False


def _try_fill_by_hints(page: Any, hints: tuple[str, ...], value: str) -> bool:
    for hint in hints:
        candidates = (
            lambda: page.get_by_placeholder(hint, exact=False),
            lambda: page.get_by_label(hint, exact=False),
            lambda: page.locator(f"input[placeholder*='{hint}']"),
            lambda: page.locator(f"xpath=//*[contains(normalize-space(), '{hint}')]/following::input[1]"),
        )
        for build_locator in candidates:
            try:
                if _try_fill_locator(build_locator(), value):
                    return True
            except Exception:
                continue
    return False


def _try_click_search(page: Any) -> bool:
    search_labels = ("\u641c\u7d22", "\u67e5\u8be2", "\u7acb\u5373\u641c\u7d22")
    for label in search_labels:
        candidates = (
            lambda: page.get_by_role("button", name=label, exact=False),
            lambda: page.get_by_text(label, exact=True),
            lambda: page.locator(f"button:has-text('{label}')"),
            lambda: page.locator(f"a:has-text('{label}')"),
        )
        for build_locator in candidates:
            try:
                target = build_locator().first
                target.click(timeout=1500)
                return True
            except Exception:
                continue
    return False


def _prepare_ctrip_page(page: Any, url: str, request: TripRequest) -> list[str]:
    hostname = (urlparse(url).hostname or "").lower()
    if not hostname.endswith("ctrip.com"):
        return []

    origin = _clean_city(request.origin_city)
    destination = _clean_city(request.destination)
    start_date = request.start_date.isoformat()
    actions: list[str] = []

    origin_hints = ("\u51fa\u53d1\u57ce\u5e02", "\u51fa\u53d1\u5730", "\u51fa\u53d1", "from")
    destination_hints = ("\u5230\u8fbe\u57ce\u5e02", "\u76ee\u7684\u5730", "\u5230\u8fbe", "to")
    date_hints = ("\u51fa\u53d1\u65e5\u671f", "\u65e5\u671f", "date")
    keyword_hints = ("\u76ee\u7684\u5730", "\u5173\u952e\u8bcd", "\u60f3\u53bb\u54ea", "keyword", "search")

    if "trains.ctrip.com" in hostname:
        if _try_fill_by_hints(page, origin_hints, origin):
            actions.append("train_origin")
        if _try_fill_by_hints(page, destination_hints, destination):
            actions.append("train_destination")
        if _try_fill_by_hints(page, date_hints, start_date):
            actions.append("train_date")
    elif "flights.ctrip.com" in hostname:
        if _try_fill_by_hints(page, origin_hints, origin):
            actions.append("flight_origin")
        if _try_fill_by_hints(page, destination_hints, destination):
            actions.append("flight_destination")
        if _try_fill_by_hints(page, date_hints, start_date):
            actions.append("flight_date")
    elif "vacations.ctrip.com" in hostname or hostname == "www.ctrip.com":
        if _try_fill_by_hints(page, keyword_hints, destination):
            actions.append("vacation_destination")

    if actions and _try_click_search(page):
        actions.append("search_clicked")
        try:
            page.wait_for_load_state("domcontentloaded", timeout=5000)
        except Exception:
            pass
        try:
            page.wait_for_load_state("networkidle", timeout=7000)
        except Exception:
            pass

    return actions


def observe_browser_prices(request: TripRequest) -> dict[str, Any]:
    urls, generated_urls = _collect_observation_urls(request)

    if not request.browser_price_enabled or not urls:
        return {
            "status": "skipped",
            "items": [],
            "source_records": [],
            "requires_human": False,
            "fallback_reason": "browser_price_not_requested",
            "generated_urls": generated_urls,
            "notice": NOTICE,
            "source_type": SourceType.browser_observed,
        }

    if not config.BROWSER_ENABLED:
        return {
            "status": "skipped",
            "items": [],
            "source_records": [],
            "requires_human": False,
            "fallback_reason": "browser_disabled",
            "generated_urls": generated_urls,
            "notice": NOTICE,
            "source_type": SourceType.browser_observed,
        }

    disallowed_urls = [url for url in urls if not _is_allowed_url(url)]
    urls = [url for url in urls if _is_allowed_url(url)]
    if not urls:
        return {
            "status": "failed",
            "items": [],
            "source_records": [],
            "requires_human": False,
            "fallback_reason": f"browser_domain_not_allowed:{','.join(disallowed_urls[:3])}",
            "generated_urls": generated_urls,
            "notice": NOTICE,
            "source_type": SourceType.browser_observed,
        }

    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        return {
            "status": "failed",
            "items": [],
            "source_records": [],
            "requires_human": False,
            "fallback_reason": f"playwright_unavailable:{exc.__class__.__name__}",
            "generated_urls": generated_urls,
            "notice": NOTICE,
            "source_type": SourceType.browser_observed,
        }

    observed_items: list[dict[str, Any]] = []
    page_errors: list[str] = []
    human_reasons: list[str] = []
    prepared_actions: list[str] = []
    observed_at = datetime.utcnow().isoformat()

    try:
        with sync_playwright() as playwright:
            # Mode 1: connect to already-running Chrome via CDP (preserves login state)
            if config.BROWSER_CDP_URL:
                browser = playwright.chromium.connect_over_cdp(config.BROWSER_CDP_URL)
                context = browser.new_context(
                    locale="zh-CN",
                    viewport={"width": 1365, "height": 900},
                )
                _owns_browser = False
            # Mode 2: launch with persistent user-data dir (cookies/sessions survive restarts)
            elif config.BROWSER_USER_DATA_DIR:
                context = playwright.chromium.launch_persistent_context(
                    user_data_dir=config.BROWSER_USER_DATA_DIR,
                    headless=config.BROWSER_HEADLESS,
                    channel=config.BROWSER_CHANNEL,
                    locale="zh-CN",
                    viewport={"width": 1365, "height": 900},
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--disable-features=IsolateOrigins,site-per-process",
                    ],
                )
                browser = None  # persistent context manages its own browser lifecycle
                _owns_browser = True
            # Mode 3: fresh temporary browser (default)
            else:
                browser = playwright.chromium.launch(
                    headless=config.BROWSER_HEADLESS,
                    channel=config.BROWSER_CHANNEL,
                    args=[
                        "--disable-dev-shm-usage",
                        "--no-sandbox",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-features=IsolateOrigins,site-per-process",
                    ],
                )
                context = browser.new_context(
                    locale="zh-CN",
                    viewport={"width": 1365, "height": 900},
                )
                _owns_browser = True
            for url in urls:
                page = context.new_page()
                try:
                    page.goto(
                        url,
                        wait_until="domcontentloaded",
                        timeout=config.BROWSER_TIMEOUT_SECONDS * 1000,
                    )
                    try:
                        page.wait_for_load_state("networkidle", timeout=5000)
                    except PlaywrightTimeoutError:
                        pass

                    prepared_actions.extend(
                        f"{url}:{action}"
                        for action in _prepare_ctrip_page(page, url, request)
                    )

                    page_title = page.title()
                    body_text = page.locator("body").inner_text(timeout=5000)
                    requires_human, reason = _detect_human_blocker(body_text)
                    if requires_human and reason:
                        if not config.BROWSER_HEADLESS and config.BROWSER_HUMAN_WAIT_SECONDS > 0:
                            page.wait_for_timeout(config.BROWSER_HUMAN_WAIT_SECONDS * 1000)
                            body_text = page.locator("body").inner_text(timeout=5000)
                            requires_human, reason = _detect_human_blocker(body_text)
                        if requires_human and reason:
                            human_reasons.append(f"{url}:{reason}")

                    observed_items.extend(
                        _extract_price_items(
                            text=body_text,
                            url=url,
                            page_title=page_title,
                            observed_at=observed_at,
                            max_items=config.BROWSER_MAX_PRICE_ITEMS - len(observed_items),
                        )
                    )
                except Exception as exc:
                    page_errors.append(f"{url}:{exc.__class__.__name__}")
                finally:
                    page.close()

                if len(observed_items) >= config.BROWSER_MAX_PRICE_ITEMS:
                    break
            context.close()
            if browser is not None and _owns_browser:
                browser.close()
    except Exception as exc:
        source_records = _build_source_records(observed_items)
        if not source_records:
            source_records = _build_attempt_source_records(
                urls=urls,
                status="failed",
                fallback_reason=f"browser_runtime_error:{exc.__class__.__name__}",
                prepared_actions=prepared_actions,
            )
        return {
            "status": "failed",
            "items": observed_items,
            "source_records": source_records,
            "requires_human": bool(human_reasons),
            "fallback_reason": f"browser_runtime_error:{exc.__class__.__name__}",
            "generated_urls": generated_urls,
            "prepared_actions": prepared_actions,
            "notice": NOTICE,
            "source_type": SourceType.browser_observed,
        }

    if observed_items:
        status = "success"
        fallback_reason = ";".join(page_errors[:3]) if page_errors else None
    elif human_reasons:
        status = "requires_human"
        fallback_reason = ";".join(human_reasons[:3])
    else:
        status = "no_price"
        fallback_reason = ";".join(page_errors[:3]) if page_errors else "no_visible_price_found"

    source_records = _build_source_records(observed_items)
    if not source_records:
        source_records = _build_attempt_source_records(
            urls=urls,
            status=status,
            fallback_reason=fallback_reason,
            prepared_actions=prepared_actions,
        )

    return {
        "status": status,
        "items": observed_items,
        "source_records": source_records,
        "requires_human": bool(human_reasons),
        "fallback_reason": fallback_reason,
        "generated_urls": generated_urls,
        "prepared_actions": prepared_actions,
        "notice": NOTICE,
        "source_type": SourceType.browser_observed,
    }
