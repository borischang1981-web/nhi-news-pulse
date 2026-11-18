#!/usr/bin/env python3
"""Public RSS-only collector for NHI News Pulse. Python standard library only.

The collector keeps news metadata (title, short RSS teaser, URL, timestamp), not
full publisher articles. Media reports are NEVER treated as verified facts.
"""
from __future__ import annotations

import concurrent.futures
import hashlib
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'config' / 'feeds.json'
DATA_DIR = ROOT / 'data'
OUT_JSON = DATA_DIR / 'news.json'
OUT_JS = DATA_DIR / 'news.js'
TZ = timezone(timedelta(hours=8))
KEEP_DAYS = 60
MAX_ITEMS = 1200
TIMEOUT = 22
USER_AGENT = 'Mozilla/5.0 (compatible; PersonalNHInewsRSS/1.0; metadata-only feed reader)'

# Rules give a clue for prioritisation. They are not fact-checking, legal analysis or AI.
CATEGORY_RULES = [
    ('健保保費與財務', ['保費', '補充保費', '健保費', '健保財務', '保險費率', '費率', '政府負擔36%', '保險財務', '健保基金']),
    ('投保資格與承保', ['投保資格', '加保', '退保', '納保', '眷屬', '等待期', '健保卡', '停復保', '承保', '投保金額']),
    ('醫療支付與總額', ['健保總額', '支付標準', '點值', '診察費', '醫療支付', '藥事服務費', '醫療費用', '調劑費', '急診分流', 'DRG']),
    ('藥品與特材給付', ['新藥', '藥價', '藥品給付', '藥物給付', '藥品支付', '罕藥', '罕病', '自付差額', '特材', '給付限制', '藥品短缺', '醫材']),
    ('健保資料與資訊安全', ['健保資料', '健康存摺', '資料管理條例', '電子處方箋', '電子病歷', '醫療資安', '資料外洩', '資料治理', '個資', '健康資料']),
    ('代位求償與事故', ['代位求償', '重大醫療事故', '公共安全事故', '醫療事故', '火災', '工安事故', '事故求償', '醫療糾紛']),
    ('移民依親與外籍', ['移民', '外籍', '外國人', '新住民', '依親', '居留', '移工', '外國專業人才', '陸生', '外專法', '國籍']),
    ('勞動薪資與就業', ['最低工資', '基本工資', '薪資調整', '勞工', '勞動', '職災', '就業', '加薪', '育嬰', '工會']),
    ('年金福利與退休', ['年金', '退休', '老農津貼', '社會救助', '所得稅', '稅制', '福利津貼', '少子化']),
    ('高齡與長照', ['長照', '老人福利法', '長者', '高齡', '失智', '失能', '老人', '居家照護', '照護人力']),
    ('地方補助', ['地方政府', '縣政府', '市政府', '市議會', '縣議會', '保費補助', '醫療補助', '地方補助']),
    ('醫療人力與醫院', ['醫師', '護理師', '醫院', '醫事', '藥師', '急診', '病床', '醫療量能', '醫師過勞', '醫院經營']),
    ('公共衛生與疫情', ['流感', '疫苗', '疫情', '傳染病', '疾管署', '腸病毒', '肺炎', '公費藥劑', '疫苗接種']),
    ('立法院修法預算', ['立法院', '立委', '三讀', '修法', '法案', '法條', '總預算', '委員會', '施政報告', '黨團']),
]
DIRECT_TERMS = ['全民健康保險', '健保', '健康保險署', '健保署', '保費', '投保', '納保', '藥事服務費', '給付', '醫療支付', '代位求償', '健保資料']
UPSTREAM_TERMS = ['依親', '居留', '外籍', '新住民', '移工', '外國專業人才', '最低工資', '基本工資', '薪資', '勞動', '退休', '年金', '高齡', '長照', '老農津貼', '老人福利', '地方補助', '幼兒', '兒童', '醫師', '護理', '醫療', '醫院', '藥師', '社會福利', '失智', '醫療事故', '公共安全', '工安', '疫苗', '流感', '三讀', '健康資料']
HIGH_TERMS = ['詐領', '不實', '虛報', '違法', '外洩', '爭議', '弊案', '人命', '死亡', '不副署', '大火', '重大事故', '修法', '遭拒', '取消補助', '濫用', '資料洩漏']
LINK_HINTS = {
    '健保保費與財務': '涉及健保基金收入、保險費負擔及政府預算，需區分基金與公務預算。',
    '投保資格與承保': '可能影響投保身分、承保順位、投保金額或等待期，需核對有效法規及生效日。',
    '醫療支付與總額': '可能涉及支付標準、健保總額、點值與服務量；須確認是否已公告生效。',
    '藥品與特材給付': '可能涉及藥物給付條件、事前審查及健保財務，須核對正式支付公告。',
    '健保資料與資訊安全': '可能涉及資料使用目的、個資及跨系統介接；需區分身分驗證與資料利用。',
    '代位求償與事故': '事故未必符合健保法第95條求償要件，須確認事故類型與責任歸屬。',
    '移民依親與外籍': '居留、依親及勞動身分可能連動健保納保資格及等待期。',
    '勞動薪資與就業': '薪資、受僱身分及最低工資調整可能連動投保金額及保費負擔。',
    '年金福利與退休': '可能影響家庭收入與政府社福預算；不應推論年金金額直接計入健保投保金額。',
    '高齡與長照': '可能影響醫療利用、長照與健保給付的分工，以及高齡人口資源配置。',
    '地方補助': '需釐清中央與地方保費補助權責、對象及是否已正式實施。',
    '醫療人力與醫院': '醫事人力與院所經營可能影響醫療可近性及支付需求，不等於健保支付已調整。',
    '公共衛生與疫情': '可能影響健保門急診或住院利用，但須區分公費防疫與健保給付財源。',
    '立法院修法預算': '須確認提案、審查、三讀、公布及生效等不同法制階段。',
    '其他政策': '需查閱原始內容，再評估是否連動健保制度。'
}
EVENT_RULES = [
    ('老人福利法第22條修法', ['老人福利法', '老福法', '長者健保費', '老人健保費']),
    ('兒童健保費補助', ['兒童健保費', '未滿6歲', '幼兒健保費']),
    ('外籍人士健保資格', ['外籍', '外國人', '等待期', '移工', '依親', '居留']),
    ('健保資料治理', ['健保資料管理', '健康存摺', '資料退出', '醫療資料', '電子處方箋']),
    ('健保代位求償與事故', ['代位求償', '醫療事故', '重大公共安全事故']),
    ('長照政策與財務', ['長照3.0', '長照基金', '長照預算', '長照人力']),
    ('健保財務與費率', ['補充保費', '健保費率', '健保總額', '政府負擔36%']),
]


def plain(s: str) -> str:
    """Strip markup only from a short feed teaser; never fetch the article body."""
    s = re.sub(r'<(?:script|style)\b[^>]*>.*?</(?:script|style)>', '', str(s), flags=re.I | re.S)
    s = re.sub(r'<[^>]+>', ' ', s)
    return re.sub(r'\s+', ' ', html.unescape(s)).strip()[:320]


def extract_date(text: str | None) -> str:
    if not text:
        return ''
    text = text.strip()
    try:
        dt = parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError):
        try:
            dt = datetime.fromisoformat(text.replace('Z', '+00:00'))
        except (TypeError, ValueError):
            return ''
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    return dt.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def child_text(node: ET.Element, local: str) -> str:
    for child in list(node):
        if child.tag.split('}')[-1].lower() == local.lower():
            return ''.join(child.itertext()).strip()
    return ''


def parse_feed(contents: bytes) -> list[dict]:
    root = ET.fromstring(contents)
    items = []
    for node in root.iter():
        tag = node.tag.split('}')[-1].lower()
        if tag not in ('item', 'entry'):
            continue
        title = plain(child_text(node, 'title'))
        if not title:
            continue
        summary = plain(child_text(node, 'description') or child_text(node, 'summary'))
        published = extract_date(child_text(node, 'pubDate') or child_text(node, 'published') or child_text(node, 'updated') or child_text(node, 'date'))
        url = child_text(node, 'link')
        if not url:
            for child in list(node):
                if child.tag.split('}')[-1].lower() == 'link':
                    url = child.attrib.get('href', '')
                    if child.attrib.get('rel') in ('alternate', ''):
                        break
        source = child_text(node, 'source')
        # Some RSS item source is a <source> text node.
        items.append({'title': title, 'summary': summary, 'published': published, 'url': url, 'actual_source': plain(source)})
    return items


def classify(title: str, teaser: str, official: bool) -> tuple[str, str, str, str, int]:
    s = title + ' ' + teaser[:180]
    direct = any(t.lower() in s.lower() for t in DIRECT_TERMS)
    upstream = sum(1 for t in UPSTREAM_TERMS if t.lower() in s.lower())
    if not direct and upstream == 0:
        return '其他政策', '其他政策', '低', LINK_HINTS['其他政策'], 0
    weighted = []
    for i, (category, terms) in enumerate(CATEGORY_RULES):
        score = 0
        for term in terms:
            if term.lower() in title.lower():
                score += 3
            elif term.lower() in s.lower():
                score += 1
        if score:
            weighted.append((score, -i, category))
    category = max(weighted)[2] if weighted else '其他政策'
    topic = ''
    for group, terms in EVENT_RULES:
        if any(term.lower() in title.lower() for term in terms):
            topic = group
            break
    if not topic:
        topic = category
    risk = '高' if any(x in title for x in HIGH_TERMS) else ('中' if direct or upstream >= 2 else '低')
    score = (8 if direct else 0) + min(6, upstream * 2)
    return category, topic, risk, LINK_HINTS[category], score


def request_one(source: dict) -> tuple[dict, list[dict], str]:
    url = source.get('url', '')
    if source.get('type') == 'query':
        q = urllib.parse.quote(source['query'])
        url = f'https://news.google.com/rss/search?q={q}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant'
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'application/rss+xml,application/atom+xml,application/xml,text/xml,*/*'})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as rsp:
            payload = rsp.read(3 * 1024 * 1024)
        items = parse_feed(payload)
        return source, items, ''
    except Exception as exc:
        return source, [], f'{type(exc).__name__}: {str(exc)[:150]}'


def normalize_title(s: str) -> str:
    # Google News may suffix publisher. Keep only for dedup, never change display title.
    s = re.sub(r'\s+-\s+[^-]{1,45}$', '', s).strip()
    return re.sub(r'\W+', '', s, flags=re.UNICODE).lower()


def load_previous() -> list[dict]:
    if not OUT_JSON.exists():
        return []
    try:
        d = json.loads(OUT_JSON.read_text(encoding='utf-8'))
        return d.get('records', []) if isinstance(d, dict) else []
    except (OSError, ValueError):
        return []


def main() -> int:
    sources = json.loads(CONFIG.read_text(encoding='utf-8'))['sources']
    existing = load_previous()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=KEEP_DAYS)
    status = []
    fresh = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for src, rows, error in pool.map(request_one, sources):
            status.append({'name': src['name'], 'count': len(rows), 'error': error})
            print(f"{src['name']}: {len(rows)} items" + (' ERROR ' + error if error else ''))
            for r in rows:
                if not r['url'].startswith(('https://', 'http://')):
                    continue
                if not r['published']:
                    # No valid date = no reliable daily briefing; do not fabricate.
                    continue
                try:
                    pub = datetime.fromisoformat(r['published'].replace('Z', '+00:00'))
                except ValueError:
                    continue
                if pub < cutoff or pub > now + timedelta(days=1):
                    continue
                cat, topic, risk, linkage, relevance = classify(r['title'], r['summary'], src['official'])
                if relevance < 2:
                    continue
                actual_source = r['actual_source'] if src['type'] == 'query' and r['actual_source'] else src['name']
                # Strip common Google News headline suffix when it matches source label.
                title = r['title']
                if src['type'] == 'query' and r['actual_source'] and title.endswith(' - ' + r['actual_source']):
                    title = title[:-(len(r['actual_source']) + 3)]
                key = normalize_title(title)
                item_id = hashlib.sha256((key + '|' + actual_source).encode('utf-8')).hexdigest()[:20]
                fresh.append({
                    'id': 'rss-' + item_id, 'title': title, 'source': actual_source,
                    'publisher_feed': src['name'], 'source_kind': '官方RSS' if src['official'] else ('新聞RSS' if src['type'] == 'rss' else 'Google新聞索引'),
                    'published': r['published'], 'captured': now.isoformat().replace('+00:00', 'Z'),
                    'url': r['url'], 'summary': r['summary'], 'category': cat, 'topic': topic,
                    'risk': risk, 'verification': '待查證', 'response': '待評估',
                    'law': '', 'stakeholders': '', 'linkage': linkage,
                    'analysis': '系統規則初判；尚未閱讀全文或核對官方原文。', 'note': '', 'draft': ''
                })
    # Prefer direct publisher feeds when same title is in multiple feeds.
    merged = {r['id']: r for r in existing if isinstance(r, dict) and 'id' in r}
    for r in fresh:
        if r['id'] not in merged:
            merged[r['id']] = r
        elif r['source_kind'] in ('官方RSS', '新聞RSS') and merged[r['id']].get('source_kind') == 'Google新聞索引':
            merged[r['id']] = r
    valid = []
    for r in merged.values():
        try:
            p = datetime.fromisoformat(r.get('published', '').replace('Z', '+00:00'))
            if p >= cutoff:
                valid.append(r)
        except (ValueError, TypeError):
            continue
    valid.sort(key=lambda x: x.get('published', ''), reverse=True)
    data = {'generated_at': now.isoformat().replace('+00:00', 'Z'), 'records': valid[:MAX_ITEMS], 'source_status': status,
            'notice': 'RSS metadata only; no full-text scraping or automatic fact-checking.'}
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    OUT_JS.write_text('window.NHI_FEED = ' + json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/') + ';\n', encoding='utf-8')
    print(f'Saved {len(data["records"])} records to {OUT_JSON}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
