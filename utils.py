from __future__ import annotations
import re
from urllib.parse import urljoin, urlparse, urlunparse

# Match only numbers that are explicitly marked as prices.
# The old pattern made the currency part optional, so model names such as
# "BMV-712" could be interpreted as 712 kr when a page did not render its
# price in plain text.
PRICE_RE = re.compile(
    r"""
    (?:\b(?:kr|nok)\s*([0-9][0-9\s\u00A0.,]*))
    |
    (?:([0-9][0-9\s\u00A0.,]*)\s*(?:kr|nok|,-|–))
    """,
    re.I | re.X,
)

def normalize_ws(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "")).strip()

def clean_url(url: str) -> str:
    parsed = urlparse(url)
    query = "&".join(p for p in parsed.query.split("&") if p and not p.lower().startswith("utm_"))
    return urlunparse(parsed._replace(fragment="", query=query))

def abs_url(base: str, href: str | None) -> str | None:
    if not href:
        return None
    href = href.strip()
    if href.startswith(("javascript:", "mailto:", "tel:")):
        return None
    return clean_url(urljoin(base, href))

def slugify_text(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9/+. -]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value

def parse_price(text: str | None) -> float | None:
    if not text:
        return None
    raw = normalize_ws(str(text)).replace("\u00A0", " ").replace("kr", "").replace(",-", "").replace("–", "").strip()
    raw = re.sub(r"[^\d.,\s]", "", raw).replace(" ", "")
    if not raw or raw.count(",") + raw.count(".") > 4:
        return None
    if "," in raw and "." in raw:
        pos = max(raw.rfind(","), raw.rfind("."))
        decimals = raw[pos+1:]
        if 1 <= len(decimals) <= 2:
            raw = re.sub(r"[.,]", "", raw[:pos]) + "." + decimals
        else:
            raw = re.sub(r"[.,]", "", raw)
    elif "," in raw:
        parts = raw.split(",")
        if len(parts) == 2 and 1 <= len(parts[1]) <= 2:
            raw = parts[0].replace(".", "") + "." + parts[1]
        elif all(len(p) == 3 for p in parts[1:]):
            raw = "".join(parts)
        else:
            return None
    elif "." in raw:
        parts = raw.split(".")
        if len(parts) == 2 and 1 <= len(parts[1]) <= 2:
            raw = parts[0].replace(",", "") + "." + parts[1]
        elif all(len(p) == 3 for p in parts[1:]):
            raw = "".join(parts)
        else:
            return None
    try:
        value = round(float(raw), 2)
    except ValueError:
        return None
    return value if 1 <= value <= 500000 else None

def extract_price(text: str) -> float | None:
    """
    Extract a marked price from text.

    Only numbers with a price marker (``kr``, ``NOK``, ``,-`` or ``–``) are
    considered. This prevents product/model numbers like ``BMV-712`` or
    ``12V`` from being mistaken for prices.
    """
    values = []
    for m in PRICE_RE.finditer(text or ""):
        raw = m.group(1) or m.group(2)
        p = parse_price(raw)
        if p is not None:
            values.append(p)
    if not values:
        return None
    return max(values)

def is_generic_category_name(name: str) -> bool:
    n = slugify_text(name)
    generic = {
        "victron invertere", "victron inverter", "victron lithium",
        "victron lithium bms", "victron phoenix 12v", "victron phoenix 24v",
        "victron phoenix 48v", "victron ip65", "victron ip67", "victron ip22", "victron ip43"
    }
    return n in generic

def infer_category(name: str) -> str:
    n = slugify_text(name)
    rules = [
        ("IP22", ["ip22"]),
        ("IP43", ["ip43"]),
        ("IP65", ["ip65"]),
        ("IP67", ["ip67"]),
        ("DC-DC", ["orion", "dc-dc"]),
        ("Inverter / lader", ["multiplus", "quattro"]),
        ("Inverter", ["phoenix inverter", "inverter"]),
        ("GX / overvåking", ["cerbo", "gx"]),
        ("Batterimonitor", ["bmv", "smartshunt", "batterimonitor"]),
        ("Solcelleregulator", ["smartsolar", "mppt"]),
    ]
    for category, needles in rules:
        if any(x in n for x in needles):
            return category
    return "Annet"
