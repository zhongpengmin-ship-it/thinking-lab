from urllib.request import Request, urlopen
from urllib.parse import quote
from xml.etree import ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
import json, re, html
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data" / "news.json"
UA = {"User-Agent": "Mozilla/5.0 ThinkingLab/3.0"}

QUERIES = {
    "world": [
        'Reuters global economy trade geopolitics Asia',
        'Reuters world economy markets trade Asia',
        '"global economy" IMF World Bank UNCTAD',
        'international trade geopolitics Reuters Bloomberg FT',
        'Asia economy Reuters Bloomberg FT'
    ],
    "energy": [
        '"energy transition" Asia ASEAN IEA IRENA',
        'renewable energy grid storage Asia ASEAN',
        'energy security Asia IEA Reuters',
        'clean energy Asia Pacific Reuters Bloomberg',
        'ASEAN energy transition renewable electricity'
    ],
    "asia": [
        'RCEP ASEAN APEC trade regional cooperation',
        '"Asian economic integration" trade investment',
        'Asia supply chain regional cooperation trade Reuters',
        'ASEAN trade digital economy regional integration',
        'APEC trade investment regional cooperation'
    ]
}

SOURCE_WEIGHTS = {
    "Reuters": 14,
    "Financial Times": 13,
    "Bloomberg": 13,
    "The Economist": 11,
    "Nikkei Asia": 11,
    "International Energy Agency": 14,
    "IEA": 14,
    "IRENA": 13,
    "Asian Development Bank": 14,
    "ADB": 14,
    "IMF": 14,
    "World Bank": 14,
    "UNCTAD": 13,
    "ESCAP": 13,
    "United Nations": 11,
    "APEC": 13,
    "ASEAN": 13,
    "ASEAN Centre for Energy": 13,
    "Channel News Asia": 10,
    "South China Morning Post": 9,
    "World Economic Forum": 8
}

BLOCKED = (
    "britannica",
    "wikipedia",
    "haver analytics",
    "opengov asia",
    "thailand business news"
)

def fetch(query):
    url = (
        "https://news.google.com/rss/search?q="
        + quote(query)
        + "&hl=en-US&gl=US&ceid=US:en"
    )
    req = Request(url, headers=UA)
    xml = urlopen(req, timeout=30).read()
    root = ET.fromstring(xml)

    results = []
    for item in root.findall("./channel/item")[:30]:
        raw_title = html.unescape(item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = item.findtext("pubDate") or ""

        src = item.find("source")
        source = (src.text or "").strip() if src is not None else ""

        title = raw_title
        if not source and " - " in raw_title:
            title, source = raw_title.rsplit(" - ", 1)

        try:
            dt = parsedate_to_datetime(pub).astimezone(timezone.utc)
        except Exception:
            dt = None

        results.append({
            "title": title,
            "link": link,
            "source": source,
            "dt": dt
        })
    return results

def source_score(source):
    s = (source or "").lower()

    if any(x in s for x in BLOCKED):
        return -100

    score = 3
    for name, weight in SOURCE_WEIGHTS.items():
        if name.lower() in s:
            score = max(score, weight)
    return score

def dedupe(items):
    seen = set()
    out = []

    for x in items:
        key = re.sub(r"\W+", " ", x["title"].lower()).strip()

        # Also remove near-duplicates by first 9 normalized words.
        short_key = " ".join(key.split()[:9])

        if key in seen or short_key in seen:
            continue

        seen.add(key)
        seen.add(short_key)
        out.append(x)

    return out

def rank(items, category, max_age_days):
    now = datetime.now(timezone.utc)
    ranked = []

    for x in items:
        if not x["dt"]:
            continue

        age_days = (now - x["dt"]).total_seconds() / 86400
        if age_days < 0 or age_days > max_age_days:
            continue

        score = source_score(x["source"])
        if score < 0:
            continue

        # Strong freshness bonus.
        if age_days <= 1:
            score += 6
        elif age_days <= 2:
            score += 4
        elif age_days <= 3:
            score += 3
        elif age_days <= 5:
            score += 1

        y = dict(x)
        y["score"] = score
        y["category"] = category
        y["published"] = y["dt"].strftime("%Y-%m-%d")
        del y["dt"]
        ranked.append(y)

    ranked.sort(key=lambda z: z["score"], reverse=True)

    for x in ranked:
        x.pop("score", None)

    return dedupe(ranked)

def gather_raw(category):
    raw = []
    for q in QUERIES[category]:
        try:
            raw.extend(fetch(q))
        except Exception as e:
            print("feed error:", category, q, e)
    return raw

def gather_world():
    raw = gather_raw("world")

    # First choice: last 72 hours.
    recent = rank(raw, "World", 3)

    if len(recent) >= 3:
        return recent[:3]

    # Fallback: expand to 7 days only to fill missing slots.
    wider = rank(raw, "World", 7)
    links = {x["link"] for x in recent}
    for x in wider:
        if x["link"] not in links:
            recent.append(x)
            links.add(x["link"])
        if len(recent) >= 3:
            break

    return recent[:3]

def gather_professional(category):
    raw = gather_raw(category)
    ranked = rank(raw, category.capitalize(), 7)
    return ranked[:12]

QUESTIONS = [
    "今天哪一条信息真正改变了既有趋势，而不只是延续了趋势？",
    "如果从利益受损方的角度看，今天最重要的一项政策会被怎样解释？",
    "今天读到的内容里，哪些是事实，哪些其实已经包含了因果判断？",
    "谁从今天最重要的变化中获益，谁承担成本？这种分配可持续吗？",
    "今天看到的是短期冲击，还是长期结构性变化？你凭什么判断？",
    "如果你必须反驳自己对今天最重要新闻的第一反应，最强论据是什么？"
]

now = datetime.now(timezone.utc)

data = {
    "generated_at": now.strftime("%Y-%m-%d %H:%M UTC"),
    "date_display": now.strftime("%A · %d %B %Y"),
    "world": gather_world(),
    "energy": gather_professional("energy"),
    "asia": gather_professional("asia"),
    "question": QUESTIONS[now.toordinal() % len(QUESTIONS)]
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(
    json.dumps(data, ensure_ascii=False, indent=2),
    encoding="utf-8"
)
