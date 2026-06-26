"""Browser navigation service — opens MS Edge to assist user browsing.

When a user clicks a button in the frontend (flight / hotel / train),
the backend launches MS Edge as an independent process, navigates to the
matching Ctrip page.  The browser stays open — the user closes it manually.

No Playwright dependency.  No automatic scraping.  No price extraction.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from typing import Any
from urllib.parse import quote

from app import config

logger = logging.getLogger(__name__)

# ── Locate Edge binary ──────────────────────────────────────────────────────

_EDGE_PATHS: tuple[str, ...] = (
    # Windows
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    # macOS
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    # Linux
    "microsoft-edge",
    "microsoft-edge-stable",
)


def _find_edge() -> str | None:
    """Find the MS Edge executable on this machine."""
    # Honour explicit channel config first (allows env override)
    explicit = (config.BROWSER_CHANNEL or "").strip().lower()
    if explicit and explicit != "msedge":
        # e.g. "chrome" or "chromium" — still try Edge, fallback to generic
        pass

    # Check env override
    env_edge = os.getenv("MSEDGE_PATH", "").strip()
    if env_edge and os.path.isfile(env_edge):
        return env_edge

    # Check known install paths
    for candidate in _EDGE_PATHS:
        if shutil.which(candidate) or os.path.isfile(candidate):
            return candidate

    # Fallback: just try "msedge" on PATH
    if shutil.which("msedge"):
        return "msedge"

    return None


# ── URL builders ────────────────────────────────────────────────────────────


def _clean_city(value: str | None) -> str:
    return (value or "").strip()


def build_flight_url(origin: str, destination: str, date: str) -> str:
    encoded_origin = quote(origin)
    encoded_destination = quote(destination)
    return (
        "https://flights.ctrip.com/online/channel/domestic?"
        f"dcity={encoded_origin}&acity={encoded_destination}&ddate={date}"
    )


def build_train_url(origin: str, destination: str, date: str) -> str:
    encoded_origin = quote(origin)
    encoded_destination = quote(destination)
    return (
        "https://trains.ctrip.com/webapp/train/list?"
        f"ticketType=0&dStation={encoded_origin}&aStation={encoded_destination}&dDate={date}"
    )


def build_hotel_url(destination: str, checkin: str, checkout: str) -> str:
    encoded_city = quote(destination)
    return (
        f"https://hotels.ctrip.com/hotel/{encoded_city}?"
        f"checkin={checkin}&checkout={checkout}"
    )


def build_vacation_url(destination: str) -> str:
    encoded_dest = quote(destination)
    return f"https://vacations.ctrip.com/list/whole/d-{encoded_dest}.html"


# ── Main entry point ────────────────────────────────────────────────────────


def navigate_to_ctrip(
    *,
    category: str,
    origin_city: str = "",
    destination: str = "",
    start_date: str = "",
    end_date: str = "",
) -> dict[str, Any]:
    """Launch MS Edge and navigate to the relevant Ctrip page.

    The browser runs as a completely independent process — closing the backend
    does NOT close the browser window.

    Args:
        category: One of "flight", "train", "hotel", "vacation".
        origin_city: Departure city (not used for hotel/vacation).
        destination: Destination city.
        start_date: ISO-format start date.
        end_date: ISO-format end date (used for hotel checkout).

    Returns:
        dict with status, url, and message.
    """
    category = (category or "").lower().strip()

    VALID = ("flight", "train", "hotel", "vacation")
    if category not in VALID:
        return {
            "status": "error",
            "url": None,
            "message": f"不支持的类型：{category}，可选 {' / '.join(VALID)}",
        }

    origin = _clean_city(origin_city)
    dest = _clean_city(destination)

    if category == "flight":
        url = build_flight_url(origin, dest, start_date)
    elif category == "train":
        url = build_train_url(origin, dest, start_date)
    elif category == "hotel":
        checkout = end_date or start_date
        url = build_hotel_url(dest, start_date, checkout)
    else:  # vacation
        url = build_vacation_url(dest)

    edge = _find_edge()
    if edge is None:
        return {
            "status": "error",
            "url": url,
            "message": "未找到 MS Edge 浏览器，请安装 Edge 或设置 MSEDGE_PATH 环境变量。",
        }

    try:
        # CREATE_NEW_PROCESS_GROUP + DETACHED_PROCESS on Windows ensure
        # the browser is completely independent of the backend process.
        flags = 0
        if sys.platform == "win32":
            flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS  # type: ignore[attr-defined]

        subprocess.Popen(
            [edge, url, "--new-window"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
        )
        logger.info("Launched Edge for category=%s url=%s", category, url)
    except Exception as exc:
        logger.exception("Failed to launch Edge")
        return {
            "status": "error",
            "url": url,
            "message": f"Edge 启动失败：{exc}",
        }

    return {
        "status": "opened",
        "url": url,
        "message": f"已在 Edge 浏览器中打开 {category} 页面，请自行查看价格。",
    }
