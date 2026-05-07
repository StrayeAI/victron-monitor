from __future__ import annotations
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from utils import abs_url, clean_url, extract_price, infer_category, is_generic_category_name, normalize_ws, parse_price, slugify_text
from matcher import safe_match, score

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

SHOPS = [
    {
        "name": "Makspower",
        "start_urls": [
            "https://makspower.no/kategori/kategorier-victron",
            "https://makspower.no/?s=victron",
            "https://makspower.no/produkt/",
        ],
        "allowed": ["makspower.no"],
        "max_pages": 220,
    },
    {
        "name": "Seatronic",
        "start_urls": ["https://seatronic.no/collection/leverandorer/victron-energy.html"],
        "allowed": ["seatronic.no"],
        "max_pages": 55,
    },
    {
        "name": "Sparelys",
        "start_urls": ["https://www.sparelys.no/butikk/victron-energy"],
        "allowed": ["sparelys.no"],
        "max_pages": 45,
    },
    {
        "name": "Batteriimport",
        "start_urls": ["https://www.batteriimport.no/product-category/victron-energy"],
        "allowed": ["batteriimport.no"],
        "max_pages": 45,
    },
    {
        "name": "BatteriButikken",
        "start_urls": ["https://www.batteributikken.com/categories/victron-1"],
        "allowed": ["batteributikken.com"],
        "max_pages": 28,
    },
]

PRICE_FALLBACK_MAX = 100000.0
MIN_VALID_PRICE = 50.0
PRICE_ONLY_RE = re.compile(r"^\s*(?:kr|nok)?\s*\d[\d\s\u00A0.,]*(?:\s*(?:kr|nok|,-|–))?\s*$", re.I)
SCRIPT_PRICE_RE = re.compile(r'"(?:final_price|special_price|regular_price|price|lowPrice|highPrice)"\s*:\s*"?([0-9][0-9\s.,]*)"?', re.I)

def _load_existing_products() -> list:
    from pathlib import Path
    import json
    path = Path(__file__).parent / "data" / "products.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("products", [])
    except Exception:
        return []

def same_domain(url: str, allowed: list[str]) -> bool:
    host = requests.utils.urlparse(url).hostname or ""
    return any(host == d or host.endswith("." + d) for d in allowed)

def is_listing(url: str) -> bool:
    lower = url.lower()
    if "/produkt/" in lower or "/product/" in lower or "/products/" in lower:
        return False
    patterns = ["/kategori/", "/collection/", "/product-category/", "/butikk/", "?s=", "/search", "/collections/", "/categories/", "/shop/"]
    return any(x in lower for x in patterns)

def looks_like_product(url: str) -> bool:
    lower = url.lower()
    if is_listing(url):
        return False
    keywords = [
        "/produkt/",
        "/product/",
        "/products/",
        "victron",
        "ip22",
        "ip43",
        "ip65",
        "ip67",
        "orion",
        "multiplus",
        "quattro",
        "cerbo",
        "bmv",
        "smartsolar",
        "smartsun",
        "easysolar",
        "argofet",
        "skylla",
        "phoenix",
        "blue-smart",
        "smartshunt",
        "lynx",
    ]
    return any(x in lower for x in keywords)

def extract_codes(text: str) -> list[str]:
    import re
    source = (text or "").upper()
    codes = []

    # Victron article numbers are often embedded in URLs/slugs from competitors
    # (e.g. ...-vicbpp900465050). Capture the actual BPP/BAM/BPC/etc. code, not
    # the whole slug/prefix.
    for pattern in [
        r"\b(?:VIC)?((?:BPP|BAM|BPC|ORI|SCC|PIN|PMP|LYN|ASS|SKY|CIN|BAT|ARG)[A-Z0-9\-]{6,})\b",
        r"\b([A-Z]{2,6}[A-Z0-9\-]{5,})\b",
    ]:
        for c in re.findall(pattern, source):
            if any(ch.isdigit() for ch in c) and c not in codes:
                codes.append(c)
    return codes

def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "nb-NO,nb;q=0.9,no;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    })
    retry = Retry(
        total=1,
        connect=1,
        read=1,
        status=1,
        backoff_factor=0.25,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["GET", "HEAD"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

def fetch(session, url: str, timeout: int = 8) -> str | None:
    # Fast mode: one normal TLS attempt first, then one short fallback only for TLS/network trouble.
    for verify in (True, False):
        try:
            r = session.get(url, timeout=timeout, allow_redirects=True, verify=verify)
            if r.status_code >= 400:
                return None
            r.encoding = r.encoding or "utf-8"
            text = r.text or ""
            if text:
                return text
        except requests.exceptions.SSLError:
            if verify:
                continue
        except requests.RequestException:
            return None
        break
    return None

def _valid_price(value: float | None) -> float | None:
    if value is None:
        return None
    value = round(float(value), 2)
    if value <= 0:
        return None
    if value > PRICE_FALLBACK_MAX:
        return 0.0
    return value

def _price_from_raw(raw: object, allow_plain_number: bool = False) -> float | None:
    if raw is None:
        return None
    value = normalize_ws(str(raw))
    if not value:
        return None

    # Plain numeric values are only allowed when they come from a known price
    # field/attribute. Free text must contain a price marker, otherwise product
    # numbers such as BMV-712 become false prices.
    if allow_plain_number and PRICE_ONLY_RE.match(value):
        return _valid_price(parse_price(value))
    return _valid_price(extract_price(value))


def _json_price_candidates(value: object) -> list[float]:
    candidates: list[float] = []

    if isinstance(value, dict):
        for key, item in value.items():
            key_l = str(key).lower()
            if key_l in {"price", "lowprice", "highprice", "saleprice", "special_price", "final_price", "regular_price"}:
                if isinstance(item, dict):
                    for nested_key in ("value", "amount", "price"):
                        price = _price_from_raw(item.get(nested_key), allow_plain_number=True)
                        if price is not None:
                            candidates.append(price)
                else:
                    price = _price_from_raw(item, allow_plain_number=True)
                    if price is not None:
                        candidates.append(price)
            candidates.extend(_json_price_candidates(item))
    elif isinstance(value, list):
        for item in value:
            candidates.extend(_json_price_candidates(item))

    return candidates


def _structured_price_candidates(soup: BeautifulSoup) -> list[float]:
    candidates: list[float] = []

    for script in soup.select('script[type*="ld+json"]'):
        raw = script.string or script.get_text(" ", strip=True)
        if not raw:
            continue
        try:
            candidates.extend(_json_price_candidates(json.loads(raw)))
        except (TypeError, ValueError, json.JSONDecodeError):
            continue

    # Some shops render prices in JavaScript state instead of normal HTML.
    # Keep this narrow: only keys named price/final_price/etc. are accepted.
    for script in soup.select("script"):
        raw = script.string or script.get_text(" ", strip=True)
        if not raw or "price" not in raw.lower():
            continue
        for match in SCRIPT_PRICE_RE.finditer(raw):
            price = _price_from_raw(match.group(1), allow_plain_number=True)
            if price is not None:
                candidates.append(price)

    return candidates


def _extract_price_from_soup(soup: BeautifulSoup, text: str) -> float:
    # Prefer the visible price in the actual product summary. WooCommerce pages
    # often include "related products" further down the same HTML. REV05 picked
    # the lowest .price on the whole page, which made e.g. the 95mm2 shunt cable
    # show 10 kr from a related blade fuse instead of the product price 269 kr.
    primary_selectors = [
        '.summary.entry-summary .price',
        '.entry-summary .price',
        '.product-summary .price',
        '.product-info .price',
        'main .summary .woocommerce-Price-amount',
    ]
    for sel in primary_selectors:
        primary_candidates: list[float] = []
        for node in soup.select(sel):
            # WooCommerce sale prices are rendered as <del>old</del><ins>sale</ins>.
            # Prefer the visible sale price in <ins>; otherwise use the first visible price.
            sale_nodes = node.select("ins .woocommerce-Price-amount, ins .amount, ins") if hasattr(node, "select") else []
            for sale_node in sale_nodes:
                price = _price_from_raw(sale_node.get_text(" ", strip=True), allow_plain_number=False)
                if price is not None:
                    primary_candidates.append(price)
            if not primary_candidates:
                price_nodes = node.select(".woocommerce-Price-amount, .amount") if hasattr(node, "select") else []
                if price_nodes:
                    for price_node in price_nodes:
                        price = _price_from_raw(price_node.get_text(" ", strip=True), allow_plain_number=False)
                        if price is not None:
                            primary_candidates.append(price)
                else:
                    price = _price_from_raw(node.get_text(" ", strip=True), allow_plain_number=False)
                    if price is not None:
                        primary_candidates.append(price)
        if primary_candidates:
            return primary_candidates[0]

    selectors = [
        'meta[property="product:price:amount"]',
        'meta[itemprop="price"]',
        '[itemprop="price"]',
        '[data-price]',
        '[data-product-price]',
        '.price',
        '.product-price',
        '.woocommerce-Price-amount',
        '.money',
    ]
    candidates: list[float] = []
    for sel in selectors:
        for node in soup.select(sel):
            for attr in ("content", "data-price", "data-product-price", "value", "aria-label"):
                price = _price_from_raw(node.get(attr), allow_plain_number=True)
                if price is not None:
                    candidates.append(price)
            price = _price_from_raw(node.get_text(" ", strip=True), allow_plain_number=False)
            if price is not None:
                candidates.append(price)
        if candidates:
            break

    if not candidates:
        candidates.extend(_structured_price_candidates(soup))

    if candidates:
        # Use the first visible product-price candidate from the page order. This
        # is normally the main product price; taking the global minimum can pick
        # unrelated recommendations/accessories rendered below the product.
        return candidates[0]

    fallback = _valid_price(extract_price(text))
    return fallback if fallback is not None else 0.0

def parse_product(shop: str, url: str, html: str) -> dict | None:
    if is_listing(url):
        return None
    soup = BeautifulSoup(html, "html.parser")
    name = None
    h1 = soup.select_one("h1")
    if h1:
        name = normalize_ws(h1.get_text(" ", strip=True))
    if not name and soup.title and soup.title.string:
        name = normalize_ws(soup.title.string)
    if not name or "victron" not in slugify_text(name):
        return None
    low_name = name.lower()
    if "søkeresultat" in low_name or "søkeresultater" in low_name or "search result" in low_name:
        return None
    if is_generic_category_name(name):
        return None
    text = normalize_ws(soup.get_text(" ", strip=True))
    summary_node = soup.select_one('.summary.entry-summary, .entry-summary, .product-summary, .product-info, main')
    product_text = normalize_ws(summary_node.get_text(" ", strip=True)) if summary_node else text
    price = _extract_price_from_soup(soup, text)
    sku_text = " ".join(node.get_text(" ", strip=True) for node in soup.select('.sku, [itemprop="sku"]'))
    # Product pages can include kits/recommended products and their SKUs in the
    # same HTML. Use explicit SKU fields plus codes visible in the product title;
    # do not harvest every code from the full description/package list.
    codes = extract_codes(sku_text + " " + name + " " + url + " " + text)
    return {
        "shop": shop,
        "name": name,
        "url": clean_url(url),
        "price": 0.0 if price is None else price,
        "category": infer_category(name),
        "codes": codes,
    }

def scrape_shop(shop_cfg: dict, progress=None) -> list[dict]:
    session = make_session()
    seen_pages, product_urls, queue = set(), set(), list(shop_cfg["start_urls"])
    while queue and len(seen_pages) < shop_cfg["max_pages"]:
        url = queue.pop(0)
        if url in seen_pages:
            continue
        seen_pages.add(url)
        html = fetch(session, url)
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.select("a[href]"):
            href = a.get("href")
            next_url = abs_url(url, href)
            if not next_url or not same_domain(next_url, shop_cfg["allowed"]):
                continue

            anchor_text = slugify_text(a.get_text(" ", strip=True))
            url_text = slugify_text(next_url)
            relevant = "victron" in anchor_text or "victron" in url_text

            if looks_like_product(next_url) and relevant:
                product_urls.add(next_url)
            elif (is_listing(next_url) or relevant) and next_url not in seen_pages and next_url not in queue and len(queue) < shop_cfg["max_pages"]:
                queue.append(next_url)
        time.sleep(0.08)

    products = []
    for url in sorted(product_urls)[:shop_cfg["max_pages"]]:
        html = fetch(session, url)
        if not html:
            continue
        p = parse_product(shop_cfg["name"], url, html)
        if p:
            products.append(p)
        time.sleep(0.08)

    dedup = {}
    for p in products:
        dedup[(p["shop"], p["url"])] = p
    if progress:
        progress(f'{shop_cfg["name"]}: {len(dedup)} produkter funnet')
    return list(dedup.values())

def _best_offer_per_shop(group: list[dict]) -> list[dict]:
    per_shop = {}
    for item in group:
        existing = per_shop.get(item["shop"])
        price = item.get("price") if item.get("price", 0) >= MIN_VALID_PRICE else float("inf")
        if existing is None:
            per_shop[item["shop"]] = item
            continue
        existing_price = existing.get("price") if existing.get("price", 0) >= MIN_VALID_PRICE else float("inf")
        if (price, -score(item["name"], group[0]["name"])) < (existing_price, -score(existing["name"], group[0]["name"])):
            per_shop[item["shop"]] = item
    return list(per_shop.values())

def _sort_price(item: dict) -> float:
    price = item.get("price")
    return price if price is not None and price >= MIN_VALID_PRICE else float("inf")

def _product_match_items(product: dict) -> list[dict]:
    items: list[dict] = []
    offers = product.get("offers") or []
    if isinstance(offers, list):
        items.extend(o for o in offers if isinstance(o, dict))
    best_offer = product.get("best_offer")
    if isinstance(best_offer, dict):
        items.append(best_offer)

    items.append({
        "shop": product.get("shop") or product.get("best_offer", {}).get("shop"),
        "name": product.get("name", ""),
        "url": product.get("url", ""),
        "price": product.get("price") or product.get("best_offer", {}).get("price", 0),
        "codes": [product.get("sku")] if product.get("sku") else [],
    })

    unique: dict[tuple[str, str], dict] = {}
    for item in items:
        key = (item.get("shop") or "", item.get("url") or item.get("name") or "")
        unique[key] = item
    return list(unique.values())

def _has_similar_current_product(existing_product: dict, current_products: list[dict]) -> bool:
    """Avoid carrying forward stale duplicate rows after a shop changes URLs.

    Makspower has changed some product slugs/group pages. The previous
    dashboard preserved old rows from data/products.json, which could leave a
    dead "Åpne" link even after the scraper found the new product URL.
    """
    existing_items = _product_match_items(existing_product)
    for current_product in current_products:
        for existing_item in existing_items:
            for current_item in _product_match_items(current_product):
                if existing_item.get("shop") and current_item.get("shop") and existing_item.get("shop") != current_item.get("shop"):
                    continue
                try:
                    if safe_match(existing_item, current_item):
                        return True
                except Exception:
                    continue
    return False

def _url_is_definitely_broken(url: str) -> bool:
    if not url:
        return True
    session = make_session()
    for verify in (True, False):
        try:
            response = session.get(url, timeout=10, allow_redirects=True, verify=verify)
        except requests.RequestException:
            continue
        if response.status_code == 404:
            return True
        if response.status_code >= 500:
            return False
        text = (response.text or "")[:20000].lower()
        if "fant ikke siden" in text or "siden ble ikke funnet" in text or "page not found" in text:
            return True
        return False
    # Network/SSL uncertainty should not delete local data.
    return False

def build_products(progress=None) -> dict:
    shops = {shop["name"]: [] for shop in SHOPS}
    successful_shops: list[str] = []

    def run_shop(shop_cfg: dict):
        if progress:
            progress(f'Henter {shop_cfg["name"]} ...')
        try:
            return shop_cfg["name"], scrape_shop(shop_cfg, progress), None
        except Exception as e:
            return shop_cfg["name"], [], e

    # Fetch shops in parallel so one slow store (often BatteriButikken) does not
    # block the whole dashboard for several minutes.
    with ThreadPoolExecutor(max_workers=min(len(SHOPS), 5)) as executor:
        futures = [executor.submit(run_shop, shop) for shop in SHOPS]
        for future in as_completed(futures):
            name, items, error = future.result()
            shops[name] = items
            if items:
                successful_shops.append(name)
            elif error is not None and progress:
                progress(f'{name}: feil under henting')

    # Keep display order stable even though fetching is parallel.
    successful_shops = [shop["name"] for shop in SHOPS if shop["name"] in successful_shops]

    all_items = []
    for items in shops.values():
        all_items.extend(items)

    groups: list[list[dict]] = []
    for item in sorted(all_items, key=lambda x: (0 if x.get("shop") == "Makspower" else 1, _sort_price(x), x.get("name", "").lower())):
        placed = False
        for group in groups:
            if any(safe_match(item, other) for other in group):
                group.append(item)
                placed = True
                break
        if not placed:
            groups.append([item])

    out = []
    skipped_without_makspower = 0
    for group in groups:
        offers = sorted(_best_offer_per_shop(group), key=_sort_price)
        if not offers:
            continue

        makspower_offer = next((o for o in offers if o.get("shop") == "Makspower"), None)
        has_makspower = bool(makspower_offer and makspower_offer.get("price", 0) >= MIN_VALID_PRICE)
        if not has_makspower:
            skipped_without_makspower += 1
        best_offer = offers[0]
        diff = None
        if makspower_offer and best_offer.get("price") is not None and makspower_offer.get("price") is not None:
            if best_offer.get("shop") == "Makspower":
                diff = 0.0
            elif best_offer["price"] >= MIN_VALID_PRICE and makspower_offer["price"] >= MIN_VALID_PRICE:
                diff = round(best_offer["price"] - makspower_offer["price"], 2)

        primary = makspower_offer if has_makspower else offers[0]
        out.append({
            "name": primary["name"],
            "url": primary["url"],
            "category": primary["category"],
            "sku": primary["codes"][0] if primary.get("codes") else None,
            "offers": offers,
            "best_offer": best_offer,
            "diff_vs_makspower": diff,
            "has_competitor_match": any(o["shop"] != "Makspower" for o in offers),
        })

    existing = _load_existing_products()
    existing_by_key = {}
    for p in existing:
        key = (slugify_text(p.get("name", "")), p.get("sku"))
        existing_by_key[key] = p

    current_keys = {(slugify_text(p.get("name", "")), p.get("sku")) for p in out}
    for key, product in existing_by_key.items():
        if key not in current_keys:
            if _has_similar_current_product(product, out):
                continue
            if _url_is_definitely_broken(product.get("url", "")):
                continue
            out.append(product)

    out.sort(key=lambda p: (slugify_text(p.get("name", "")), p.get("sku") or ""))
    matched = sum(1 for p in out if p.get("has_competitor_match"))
    unmatched = len(out) - matched

    source_shops = successful_shops if successful_shops else list(shops.keys())
    return {"products": out, "matched_count": matched, "unmatched_count": unmatched, "skipped_without_makspower": skipped_without_makspower, "source_shops": source_shops}
