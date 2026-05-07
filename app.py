from __future__ import annotations
import json
import re
import ssl
import threading
import time
from html import unescape
from pathlib import Path
from urllib.request import Request, urlopen
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

DATA_PATH = Path(__file__).parent / "data" / "products.json"
HTML = r"""
<!doctype html>
<html lang="no">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#06283b">
  <meta name="mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-title" content="Victron Monitor">
  <link rel="manifest" href="/manifest.json">
  <link rel="icon" href="/icons/icon-192.png">
  <link rel="apple-touch-icon" href="/icons/icon-192.png">
  <title>Victron Monitor REV21</title>
  <style>
    :root {
      --bg:#06283b; --panel:#123b5c; --panel2:#0f3452; --head:#3474bc;
      --text:#f3f7fb; --muted:#b7c8d8; --line:#2e5978; --green:#29d99a;
      --red:#ff6969; --blue:#76b7ff; --shadow:0 10px 25px rgba(0,0,0,.25);
    }
    * { box-sizing: border-box; }
    body { margin:0; background:linear-gradient(180deg,#072b3e,#052338); color:var(--text); font-family:Arial, Helvetica, sans-serif; }
    .wrap { max-width:1420px; margin:0 auto; padding:24px; }
    .brand { display:flex; align-items:center; gap:16px; margin-bottom:18px; }
    .brand-logo { background:#fff; border-radius:12px; padding:10px 14px; box-shadow:var(--shadow); display:flex; align-items:center; justify-content:center; min-width:220px; min-height:74px; }
    .brand-logo img { display:block; max-width:210px; max-height:58px; object-fit:contain; }
    .brand-title h1 { margin:0 0 5px 0; font-size:28px; }
    .brand-title div { color:var(--muted); font-size:13px; }
    h2 { margin:32px 0 12px 0; font-size:21px; }
    .controls { display:grid; grid-template-columns:minmax(240px,1fr) 210px 210px 130px; gap:12px; align-items:center; margin-bottom:14px; }
    input, select, button { height:42px; border-radius:7px; border:1px solid #356386; background:#113b5d; color:var(--text); padding:0 14px; font-weight:600; box-shadow:inset 0 0 0 1px rgba(255,255,255,.03); }
    input::placeholder { color:#8faabd; }
    button { background:linear-gradient(180deg,#3f82cf,#2d6caf); cursor:pointer; border-color:#4383c8; }
    button:disabled { opacity:.6; cursor:not-allowed; }
    .meta { color:var(--muted); margin:8px 0 12px 0; font-size:13px; }
    .logbox { max-height:150px; overflow:auto; background:#062237; border:1px solid #244d6d; color:#d9e7f2; border-radius:8px; padding:10px; font-family:Consolas, monospace; font-size:12px; white-space:pre-wrap; }
    .grid { display:grid; grid-template-columns:2fr 1.08fr; gap:24px; align-items:start; }
    table { border-collapse:separate; border-spacing:0; width:100%; background:var(--panel2); box-shadow:var(--shadow); border-radius:8px; overflow:hidden; }
    th { background:var(--head); color:#fff; text-align:left; padding:12px 10px; font-size:13px; position:sticky; top:0; z-index:1; }
    td { border-bottom:1px solid var(--line); padding:11px 10px; vertical-align:top; font-size:13px; }
    tr:last-child td { border-bottom:0; }
    .product { font-weight:800; line-height:1.25; }
    .sku { color:#95bddc; font-size:12px; margin-top:4px; }
    .pill { display:inline-block; background:#4d93df; color:white; padding:4px 9px; border-radius:999px; font-size:11px; font-weight:800; white-space:nowrap; }
    .money { font-weight:900; white-space:nowrap; }
    .makspower-price { color:var(--blue); }
    .best-price { color:var(--green); }
    .worse-price { color:var(--red); }
    .muted { color:var(--muted); }
    .neg { color:var(--green); font-weight:900; white-space:nowrap; }
    .pos { color:var(--red); font-weight:900; white-space:nowrap; }
    a { color:#9fd0ff; text-decoration:none; }
    a:hover { text-decoration:underline; }
    .cards { display:grid; grid-template-columns:1fr; gap:12px; }
    .card { background:var(--panel2); border:1px solid #1f4969; border-radius:8px; padding:18px; box-shadow:var(--shadow); }
    .card h3 { margin:0 0 14px 0; font-size:18px; }
    .card div { color:#d6e4ef; line-height:1.4; }
    .err { margin-top:10px; color:#ff8b8b; white-space:pre-wrap; }
    .details { margin-top:28px; }
    .nowrap { white-space:nowrap; }
    .mobile-products { display:none; }
    .mobile-product-card { background:var(--panel2); border:1px solid #1f4969; border-radius:12px; padding:14px; box-shadow:var(--shadow); }
    .mobile-product-head { display:flex; align-items:flex-start; justify-content:space-between; gap:10px; margin-bottom:12px; }
    .mobile-product-title { font-weight:900; font-size:15px; line-height:1.25; }
    .mobile-price-list { display:grid; gap:8px; margin-top:10px; }
    .mobile-price-row { display:flex; justify-content:space-between; gap:12px; padding:8px 0; border-top:1px solid rgba(255,255,255,.08); }
    .mobile-price-row:first-child { border-top:0; }
    .mobile-shop { color:var(--muted); font-weight:800; }
    .mobile-footer { margin-top:12px; display:grid; gap:6px; color:#d6e4ef; font-size:12px; }
    .best-badge { color:var(--green); font-weight:900; }
    @media (max-width: 900px) { .controls, .grid { grid-template-columns:1fr; } .wrap { padding:14px; } }
    @media (max-width: 760px) {
      body { background:#052338; }
      .wrap { padding:10px; }
      .brand { align-items:flex-start; gap:10px; margin-bottom:12px; }
      .brand-logo { min-width:92px; min-height:46px; padding:6px 8px; border-radius:9px; }
      .brand-logo img { max-width:86px; max-height:34px; }
      .brand-title h1 { font-size:20px; line-height:1.1; }
      .brand-title div { font-size:12px; }
      .controls { position:sticky; top:0; z-index:10; background:rgba(5,35,56,.97); padding:8px 0; gap:8px; }
      input, select, button { width:100%; height:44px; font-size:15px; }
      h2 { font-size:18px; margin:18px 0 10px; }
      .meta { font-size:12px; line-height:1.35; }
      .logbox { max-height:92px; font-size:11px; }
      .price-table, .details { display:none; }
      .mobile-products { display:grid; gap:12px; }
      .cards { grid-template-columns:repeat(2, minmax(0,1fr)); gap:8px; }
      .card { padding:10px; }
      .card h3 { font-size:14px; margin-bottom:8px; }
      .card div { font-size:12px; }
      .pill { font-size:10px; padding:3px 7px; }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="brand">
      <div class="brand-logo"><img src="https://makspower.no/wp-content/uploads/2024/01/makspower-drop-shadow-logo.png" alt="Makspower logo"></div>
      <div class="brand-title"><h1>Victron Monitor REV21</h1><div>Live prissjekk mot Makspower og utvalgte konkurrenter</div></div>
    </div>
    <div class="controls">
      <input id="q" placeholder="Søk etter produkt..." oninput="render()">
      <select id="category" onchange="render()"><option value="">Alle kategorier</option></select>
      <select id="view" onchange="render()">
        <option value="all">Alle produkter</option>
        <option value="matched">Kun med konkurrenttreff</option>
        <option value="cheaper_elsewhere">Billigere enn Makspower</option>
        <option value="makspower_cheapest">Makspower billigst</option>
      </select>
      <button id="refreshBtn" onclick="refreshNow()">Oppdater nå</button>
    </div>
    <div class="meta" id="meta">Laster...</div>
    <div class="logbox" id="log"></div>
    <div class="err" id="err"></div>

    <div class="grid">
      <section>
        <h2>Beste priser</h2>
        <table class="price-table">
          <thead>
            <tr>
              <th>Produkt</th><th>Kategori</th><th>Makspower</th><th>Seatronic</th><th>Sparelys</th><th>Batteriimport</th><th>BatteriButikken</th><th>Makspower sparer</th><th>Billigst</th>
            </tr>
          </thead>
          <tbody id="bestRows"></tbody>
        </table>
        <div id="mobileProducts" class="mobile-products"></div>
      </section>
      <section>
        <h2>Butikker i oversikten</h2>
        <div class="cards" id="shopCards"></div>
      </section>
    </div>

    <section class="details">
      <h2>Prisdetaljer per produkt</h2>
      <table class="details-table">
        <thead>
          <tr>
            <th>Produkt</th><th>Kategori</th><th>Butikk</th><th>Pris</th><th>Mot Makspower</th><th>Lenke</th>
          </tr>
        </thead>
        <tbody id="detailRows"></tbody>
      </table>
    </section>
  </div>

<script>
const WANTED_SHOPS = ['Makspower','Seatronic','Sparelys','Batteriimport','BatteriButikken'];
let DATA = {products: [], source_shops: []};
let categoriesLoaded = false;

function fmtMoney(v) {
  if (v === null || v === undefined || isNaN(Number(v))) return '–';
  const n = Number(v);
  if (n === 0) return '0,00 kr';
  const sign = n < 0 ? '-' : '';
  return sign + Math.abs(n).toLocaleString('nb-NO', {minimumFractionDigits:2, maximumFractionDigits:2}) + ' kr';
}
function diffClass(v) { return Number(v) <= 0 ? 'neg' : 'pos'; }
function esc(s) { return String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function validPrice(v) { return Number(v) >= 50; }
const ACCESSORY_WORDS = ['wall','mount','veggfeste','adapter','boltsett','bolt','bolter','skrue','skruer','screw','screws','cover','deksel','bracket','holder','ramme','feste'];
function normWords(s) { return String(s||'').toLowerCase().replace(/[^a-z0-9æøå]+/g,' ').split(/\s+/).filter(Boolean); }
function accessoryWords(s) {
  const w = new Set(normWords(s));
  const out = new Set(ACCESSORY_WORDS.filter(x => w.has(x)));
  if (w.has('veggfeste')) { out.add('wall'); out.add('mount'); }
  if (w.has('wall') && w.has('mount')) out.add('veggfeste');
  if (w.has('boltsett')) { out.add('bolt'); out.add('bolter'); }
  return out;
}
function hasSharedCode(product, offer) {
  const sku = String(product.sku || '').toUpperCase();
  const codes = (offer.codes || []).map(x => String(x).toUpperCase());
  return !!sku && codes.includes(sku);
}
function offerCompatible(product, offer) {
  if (!offer) return false;
  if (offer.shop === 'Makspower') return true;
  if (hasSharedCode(product, offer)) return true;
  const pa = accessoryWords(product.name);
  const oa = accessoryWords(offer.name);
  if (pa.size !== oa.size) return false;
  if (pa.size && ![...pa].some(x => oa.has(x))) return false;
  return true;
}
function compatibleOffers(product) { return (product.offers || []).filter(o => WANTED_SHOPS.includes(o.shop) && validPrice(o.price) && offerCompatible(product, o)); }
function offerFor(product, shop) { return compatibleOffers(product).find(o => o.shop === shop); }
function makspowerPrice(product) { const o = offerFor(product, 'Makspower'); return o && validPrice(o.price) ? Number(o.price) : null; }
function bestOffer(product) {
  const offers = compatibleOffers(product);
  if (!offers.length) return null;
  return offers.slice().sort((a,b) => Number(a.price)-Number(b.price))[0];
}
function productHasMakspower(product) { return makspowerPrice(product) !== null; }
function productMatches(product) {
  const q = (document.getElementById('q').value || '').toLowerCase();
  const cat = document.getElementById('category').value;
  const view = document.getElementById('view').value;
  if (cat && product.category !== cat) return false;
  if (q && JSON.stringify(product).toLowerCase().indexOf(q) === -1) return false;
  const mp = makspowerPrice(product);
  const best = bestOffer(product);
  if (view === 'matched' && !compatibleOffers(product).some(o => o.shop !== 'Makspower')) return false;
  if (view === 'cheaper_elsewhere' && !(mp !== null && best && best.shop !== 'Makspower' && Number(best.price) < mp)) return false;
  if (view === 'makspower_cheapest') {
    if (mp === null) return false;
    const comp = compatibleOffers(product).filter(o => o.shop !== 'Makspower');
    if (!comp.length) return false;
    const cheapestComp = comp.slice().sort((a,b) => Number(a.price)-Number(b.price))[0];
    if (!(Number(cheapestComp.price) > mp)) return false;
  }
  return true;
}
async function loadData() {
  try {
    const r = await fetch('/api/data?ts=' + Date.now(), {cache:'no-store'});
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const txt = await r.text();
    if (txt.trim().startsWith('<')) throw new Error('Server returnerte HTML i stedet for data. Lukk gamle CMD-vinduer og start REV10/start_all.bat på nytt.');
    DATA = JSON.parse(txt);
    fillCategories();
    render();
  } catch (e) {
    document.getElementById('err').textContent = 'Klarte ikke hente data: ' + e;
  }
}
function fillCategories() {
  if (categoriesLoaded) return;
  const sel = document.getElementById('category');
  const cats = [...new Set((DATA.products || []).map(p => p.category).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'nb'));
  for (const c of cats) {
    const opt = document.createElement('option'); opt.value = c; opt.textContent = c; sel.appendChild(opt);
  }
  categoriesLoaded = true;
}
function render() {
  const st = DATA._status || {};
  document.getElementById('refreshBtn').disabled = !!st.refresh_running;
  const generated = DATA.generated_at ? new Date(DATA.generated_at).toLocaleString('nb-NO') : 'ikke generert ennå';
  const products = (DATA.products || []).filter(productMatches);
  const matched = products.filter(p => compatibleOffers(p).some(o => o.shop !== 'Makspower')).length;
  const skipped = DATA.skipped_without_makspower ? ` Filtrert bort uten Makspower-treff: ${DATA.skipped_without_makspower}.` : '';
  document.getElementById('meta').textContent = `Data sist generert ${generated}. Viser ${products.length} produkter, hvor ${matched} har sikker konkurrentmatch. Butikker: ${WANTED_SHOPS.join(', ')}.${skipped}`;
  document.getElementById('err').textContent = st.last_error || '';
  const logs = (st.log || []).slice(-12).map(x => `[${new Date(x.time).toLocaleTimeString('nb-NO')}] ${x.message}`).join('\n');
  document.getElementById('log').textContent = logs || st.message || 'Klar';
  renderBest(products);
  renderMobileProducts(products);
  renderCards(products);
  renderDetails(products);
}
function shopPriceCell(product, shop) {
  const o = offerFor(product, shop);
  if (!o || !validPrice(o.price)) return '<span class="muted">–</span>';
  return `<a class="money nowrap" href="${esc(o.url || '')}" target="_blank">${fmtMoney(o.price)}</a>`;
}
function makspowerSavings(product) {
  const mp = makspowerPrice(product);
  if (mp === null) return '<span class="muted">–</span>';
  const competitors = WANTED_SHOPS.filter(s => s !== 'Makspower');
  const rows = [];
  for (const shop of competitors) {
    const o = offerFor(product, shop);
    if (!o || !validPrice(o.price)) continue;
    const diff = Number(o.price) - mp;
    if (diff > 0) {
      rows.push('<span class="neg">−' + fmtMoney(diff) + '</span> vs ' + esc(shop));
    } else if (diff < 0) {
      rows.push('<span class="pos">+' + fmtMoney(Math.abs(diff)) + '</span> vs ' + esc(shop));
    }
  }
  return rows.length ? rows.join('<br>') : '<span class="muted">Ingen data</span>';
}

function renderBest(products) {
  const rows = document.getElementById('bestRows'); rows.innerHTML = '';
  const sorted = products.slice().sort((a,b) => {
    const ba = bestOffer(a), bb = bestOffer(b);
    return (ba?.price || 999999999) - (bb?.price || 999999999);
  });
  for (const p of sorted) {
    const mp = makspowerPrice(p);
    const best = bestOffer(p);
    const savings = makspowerSavings(p);
    // Finn billigste pris blant alle butikker med gyldig pris
    const allPrices = WANTED_SHOPS.map(s => offerFor(p, s)).filter(o => o && validPrice(o.price)).map(o => Number(o.price));
    const cheap = allPrices.length ? Math.min(...allPrices) : null;
    const tr = document.createElement('tr');
    tr.innerHTML = `<td><div class=\"product\">${esc(p.name)}</div>${p.sku ? `<div class=\"sku\">${esc(p.sku)}</div>` : ''}</td>
      <td><span class=\"pill\">${esc(p.category || 'Ukjent')}</span></td>
      <td class=\"nowrap\">${shopPriceCell(p, 'Makspower', mp, cheap)}</td>
      <td class=\"nowrap\">${shopPriceCell(p, 'Seatronic', mp, cheap)}</td>
      <td class=\"nowrap\">${shopPriceCell(p, 'Sparelys', mp, cheap)}</td>
      <td class=\"nowrap\">${shopPriceCell(p, 'Batteriimport', mp, cheap)}</td>
      <td class=\"nowrap\">${shopPriceCell(p, 'BatteriButikken', mp, cheap)}</td>
      <td class=\"nowrap\" style=\"font-size:12px\">${savings}</td>
      <td>${best ? esc(best.shop) : '–'}</td>`;
    rows.appendChild(tr);
  }
}
function mobilePriceRow(product, shop) {
  const o = offerFor(product, shop);
  const value = (!o || !validPrice(o.price)) ? '<span class="muted">–</span>' : `<a class="money" href="${esc(o.url || '')}" target="_blank">${fmtMoney(o.price)}</a>`;
  return `<div class="mobile-price-row"><span class="mobile-shop">${esc(shop)}</span><span>${value}</span></div>`;
}
function renderMobileProducts(products) {
  const box = document.getElementById('mobileProducts');
  if (!box) return;
  box.innerHTML = '';
  const sorted = products.slice().sort((a,b) => {
    const ba = bestOffer(a), bb = bestOffer(b);
    return (ba?.price || 999999999) - (bb?.price || 999999999);
  });
  for (const p of sorted) {
    const best = bestOffer(p);
    const div = document.createElement('div');
    div.className = 'mobile-product-card';
    div.innerHTML = `<div class="mobile-product-head">
        <div><div class="mobile-product-title">${esc(p.name)}</div>${p.sku ? `<div class="sku">${esc(p.sku)}</div>` : ''}</div>
        <span class="pill">${esc(p.category || 'Ukjent')}</span>
      </div>
      <div class="mobile-price-list">${WANTED_SHOPS.map(shop => mobilePriceRow(p, shop)).join('')}</div>
      <div class="mobile-footer">
        <div>Billigst: <span class="best-badge">${best ? esc(best.shop) + ' – ' + fmtMoney(best.price) : '–'}</span></div>
        <div>Makspower sparer: ${makspowerSavings(p)}</div>
      </div>`;
    box.appendChild(div);
  }
}
function renderCards(products) {
  const cards = document.getElementById('shopCards'); cards.innerHTML = '';
  for (const shop of WANTED_SHOPS) {
    const offers = [];
    for (const p of products) for (const o of compatibleOffers(p)) if (o.shop === shop) offers.push(o);
    const valid = offers.filter(o => validPrice(o.price));
    const low = valid.length ? Math.min(...valid.map(o => Number(o.price))) : null;
    const div = document.createElement('div'); div.className = 'card';
    div.innerHTML = `<h3>${esc(shop)}</h3><div>Treff i valgt visning: <b>${offers.length}</b><br>Laveste pris: <b>${low === null ? '–' : fmtMoney(low)}</b></div>`;
    cards.appendChild(div);
  }
}
function renderDetails(products) {
  const rows = document.getElementById('detailRows'); rows.innerHTML = '';
  for (const p of products.slice(0, 150)) {
    const mp = makspowerPrice(p);
    const offers = compatibleOffers(p).sort((a,b) => WANTED_SHOPS.indexOf(a.shop)-WANTED_SHOPS.indexOf(b.shop));
    for (const o of offers) {
      const diff = (mp !== null && validPrice(o.price)) ? Number(o.price) - mp : null;
      const tr = document.createElement('tr');
      tr.innerHTML = `<td><div class="product">${esc(p.name)}</div>${p.sku ? `<div class="sku">${esc(p.sku)}</div>` : ''}</td>
        <td>${esc(p.category || '')}</td><td>${esc(o.shop)}</td><td class="nowrap">${fmtMoney(o.price)}</td>
        <td class="${diff === null ? 'muted' : diffClass(diff)}">${diff === null ? '–' : fmtMoney(diff)}</td>
        <td>${o.url ? `<a href="${esc(o.url)}" target="_blank">Åpne</a>` : '–'}</td>`;
      rows.appendChild(tr);
    }
  }
}
async function refreshNow() {
  await fetch('/api/refresh', {method:'POST'});
  setTimeout(loadData, 1000);
}
setInterval(loadData, 3000);
loadData();
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  });
}
</script>
</body>
</html>
"""


MANIFEST = {
    "name": "Victron Monitor",
    "short_name": "Victron",
    "description": "Live prissjekk mot Makspower og utvalgte konkurrenter",
    "start_url": "/",
    "scope": "/",
    "display": "standalone",
    "background_color": "#06283b",
    "theme_color": "#06283b",
    "orientation": "any",
    "icons": [
        {"src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
        {"src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"}
    ]
}

SW = r"""
const CACHE_NAME = 'victron-monitor-rev21-pwa-v1';
const SHELL = ['/', '/manifest.json', '/icons/icon-192.png', '/icons/icon-512.png'];
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(fetch(event.request));
    return;
  }
  event.respondWith(fetch(event.request).then(response => {
    const copy = response.clone();
    caches.open(CACHE_NAME).then(cache => cache.put(event.request, copy));
    return response;
  }).catch(() => caches.match(event.request).then(cached => cached || caches.match('/'))));
});
"""

STATE = {"refresh_running": False, "message": "Klar - trykk Oppdater nå for live prissjekk", "last_error": None, "log": []}
_LOCK = threading.Lock()

EMPTY_DATA = {
    "generated_at": None,
    "source_shops": ["Makspower", "Seatronic", "Sparelys", "Batteriimport", "BatteriButikken"],
    "product_count": 0,
    "matched_count": 0,
    "unmatched_count": 0,
    "skipped_without_makspower": 0,
    "products": [],
}


def now_text():
    return time.strftime("%Y-%m-%d %H:%M:%S")

def log(msg):
    STATE["message"] = msg
    STATE["log"].append({"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "message": msg})
    STATE["log"] = STATE["log"][-80:]
    print(msg)

def strip_tags(value):
    return unescape(re.sub(r"<[^>]+>", " ", value or " "))

def parse_price_text(text):
    text = unescape(text or "").replace("\xa0", " ")
    matches = re.findall(r"(?:kr|nok)\s*([0-9][0-9\s.,]*)|([0-9][0-9\s.,]*)\s*(?:kr|nok|,-)", text, flags=re.I)
    values = []
    for a,b in matches:
        raw = (a or b).replace(" ", "").strip()
        if not raw:
            continue
        if "," in raw and "." in raw:
            pos=max(raw.rfind(","), raw.rfind(".")); raw=re.sub(r"[.,]", "", raw[:pos])+"."+raw[pos+1:]
        elif "," in raw:
            parts=raw.split(","); raw=(parts[0].replace(".","")+"."+parts[1]) if len(parts)==2 and 1<=len(parts[1])<=2 else "".join(parts)
        elif "." in raw:
            parts=raw.split("."); raw=(parts[0].replace(",","")+"."+parts[1]) if len(parts)==2 and 1<=len(parts[1])<=2 else "".join(parts)
        try:
            v=round(float(raw),2)
            if 1 <= v <= 500000:
                values.append(v)
        except Exception:
            pass
    return values[0] if values else None

def fetch_html(url):
    req = Request(url, headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36", "Accept-Language":"nb-NO,nb;q=0.9,en;q=0.7"})
    try:
        with urlopen(req, timeout=15) as r:
            return r.read().decode("utf-8", "ignore")
    except Exception:
        ctx = ssl._create_unverified_context()
        with urlopen(req, timeout=15, context=ctx) as r:
            return r.read().decode("utf-8", "ignore")

def price_from_html(url, html):
    low=url.lower()
    # WooCommerce: use the main product summary when possible, not related products.
    if "makspower.no" in low or "batteriimport.no" in low:
        m=re.search(r'<div[^>]+class="[^"]*(?:summary entry-summary|entry-summary|product-summary|product-info)[^"]*"[^>]*>(.*?)</div>\s*</div>', html, flags=re.I|re.S)
        part=m.group(1) if m else html[:90000]
        m=re.search(r'<p[^>]+class="[^"]*price[^"]*"[^>]*>(.*?)</p>', part, flags=re.I|re.S)
        if m:
            price_html=m.group(1)
            sale=re.search(r'<ins[^>]*>(.*?)</ins>', price_html, flags=re.I|re.S)
            v=parse_price_text(strip_tags(sale.group(1))) if sale else parse_price_text(strip_tags(price_html))
            if v is not None: return v
    # JSON-LD / meta / generic product price candidates.
    for pat in [
        r'"(?:price|lowPrice|highPrice|final_price|regular_price)"\s*:\s*"?([0-9][0-9\s.,]*)"?',
        r'<meta[^>]+(?:property|itemprop)=["\'](?:product:price:amount|price)["\'][^>]+content=["\']([^"\']+)',
        r'<[^>]+class=["\'][^"\']*(?:price|product-price|money|amount)[^"\']*["\'][^>]*>(.*?)</[^>]+>',
    ]:
        for m in re.finditer(pat, html, flags=re.I|re.S):
            v=parse_price_text(strip_tags(m.group(1)))
            if v is not None and v >= 50:
                return v
    return None


def recompute_product(product):
    offers = [o for o in product.get("offers", []) if float(o.get("price") or 0) >= 50]
    offers.sort(key=lambda o: float(o.get("price") or 999999999))
    makspower = next((o for o in offers if o.get("shop") == "Makspower"), None)
    best = offers[0] if offers else None
    product["best_offer"] = best
    product["has_competitor_match"] = any(o.get("shop") != "Makspower" for o in offers)
    if makspower and best:
        product["diff_vs_makspower"] = 0.0 if best.get("shop") == "Makspower" else round(float(best.get("price") or 0) - float(makspower.get("price") or 0), 2)
    else:
        product["diff_vs_makspower"] = None


def recompute_data(data):
    products = data.get("products", [])
    for product in products:
        recompute_product(product)
    data["matched_count"] = sum(1 for p in products if p.get("has_competitor_match"))
    data["unmatched_count"] = len(products) - data["matched_count"]
    data["product_count"] = len(products)


def atomic_write_json(path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)

def refresh_prices():
    if not _LOCK.acquire(blocking=False):
        return
    STATE["refresh_running"] = True
    STATE["last_error"] = None
    changed = 0; checked = 0; failed = 0
    try:
        log("Starter live prissjekk ...")
        data=json.loads(DATA_PATH.read_text(encoding="utf-8"))
        for p in data.get("products", []):
            for o in p.get("offers", []):
                url=o.get("url")
                if not url: continue
                checked += 1
                try:
                    v=price_from_html(url, fetch_html(url))
                    if v is not None and abs(float(o.get("price") or 0)-v) >= 0.01:
                        log(f"Oppdatert {o.get('shop')}: {o.get('name')} {o.get('price')} -> {v}")
                        o["price"] = v
                        changed += 1
                except Exception as e:
                    failed += 1
                if checked % 25 == 0:
                    log(f"Sjekket {checked} priser ...")
        recompute_data(data)
        data["generated_at"] = now_text()
        atomic_write_json(DATA_PATH, data)
        log(f"Live oppdatering ferdig. Sjekket {checked}, endret {changed}, feilet {failed}. Differanser beregnet på nytt.")
    except Exception as e:
        STATE["last_error"] = f"{type(e).__name__}: {e}"
        log("Feil under live oppdatering: " + STATE["last_error"])
    finally:
        STATE["refresh_running"] = False
        _LOCK.release()

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print("[web] " + (fmt % args))

    def send_bytes(self, code, body: bytes, content_type: str):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/health":
            return self.send_bytes(200, b'{"ok":true}', "application/json; charset=utf-8")
        if path == "/manifest.json":
            return self.send_bytes(200, json.dumps(MANIFEST, ensure_ascii=False).encode("utf-8"), "application/manifest+json; charset=utf-8")
        if path == "/sw.js":
            return self.send_bytes(200, SW.encode("utf-8"), "application/javascript; charset=utf-8")
        if path.startswith("/icons/"):
            icon_path = Path(__file__).parent / path.lstrip("/")
            if icon_path.exists():
                return self.send_bytes(200, icon_path.read_bytes(), "image/png")
        if path == "/" or path == "/index.html":
            return self.send_bytes(200, HTML.encode("utf-8"), "text/html; charset=utf-8")
        if path == "/api/data":
            payload = dict(EMPTY_DATA)
            try:
                payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
                payload["_status"] = {"refresh_running": STATE["refresh_running"], "message": STATE["message"], "last_error": STATE["last_error"], "log": STATE["log"]}
            except Exception as e:
                payload["_status"] = {"refresh_running": False, "message": "Datafil kunne ikke leses", "last_error": f"{type(e).__name__}: {e}", "log": []}
            return self.send_bytes(200, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
        return self.send_bytes(404, b"Not found", "text/plain; charset=utf-8")

    def do_POST(self):
        if urlparse(self.path).path == "/api/refresh":
            if not STATE["refresh_running"]:
                threading.Thread(target=refresh_prices, daemon=True).start()
            body = {"ok": True, "message": "Oppdatering startet"}
            return self.send_bytes(200, json.dumps(body, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
        return self.send_bytes(404, b"Not found", "text/plain; charset=utf-8")

AUTO_REFRESH_INTERVAL = 6 * 3600  # 6 timer = 4 ganger daglig

def auto_refresh_loop():
    """Kjører refresh_prices automatisk hver AUTO_REFRESH_INTERVAL."""
    log(f"Auto-oppdatering aktivert — kjører hver {AUTO_REFRESH_INTERVAL // 3600} time(r)")
    while True:
        time.sleep(AUTO_REFRESH_INTERVAL)
        if not STATE["refresh_running"]:
            log("Starter planlagt auto-oppdatering ...")
            threading.Thread(target=refresh_prices, daemon=True).start()

if __name__ == "__main__":
    print("Victron Monitor REV21 starter uten pip/venv")
    print("Apne: http://127.0.0.1:8765")
    print(f"Auto-oppdatering: hver {AUTO_REFRESH_INTERVAL // 3600} time(r)")
    threading.Thread(target=auto_refresh_loop, daemon=True).start()
    import os
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8765"))
    server = ThreadingHTTPServer((host, port), Handler)
    server.serve_forever()
