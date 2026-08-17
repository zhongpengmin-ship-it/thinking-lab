from urllib.request import Request, urlopen
from urllib.parse import quote
from xml.etree import ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
import json, re, html
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data" / "news.json"
UA = {"User-Agent": "Mozilla/5.0 ThinkingLab/4.0"}

# V4 principle:
# Do not pretend to "pick the best 3". Build a broad, fresh, high-quality radar
# and let the reader decide what deserves attention.

QUERIES = {
    "world": [
        'Reuters global economy trade geopolitics',
        'Reuters China economy trade Europe United States Asia',
        'Reuters global markets inflation central banks trade',
        'Reuters supply chain shipping tariffs global economy',
        'IMF World Bank UNCTAD global economy trade'
    ],
    "energy": [
        'Reuters Asia energy transition renewable energy grid',
        'Reuters oil LNG electricity Asia energy security',
        'IEA Asia energy transition oil gas electricity',
        'IRENA Asia Pacific renewable energy',
        'ADB energy transition Asia climate energy',
        'ASEAN Centre for Energy energy transition',
        'Asia grid storage batteries green steel hydrogen Reuters'
    ],
    "asia": [
        'Reuters ASEAN RCEP APEC trade Asia regional cooperation',
        'Reuters Asia trade supply chain investment ASEAN',
        'APEC trade investment regional economic integration',
        'ASEAN economic integration trade digital economy',
        'ADB Asian economic integration regional cooperation',
        'UNESCAP Asia trade regional cooperation',
        'RCEP trade investment Asia'
    ]
}

PREFERRED = {
    "Reuters": 20, "Financial Times": 18, "Bloomberg": 18, "Nikkei Asia": 17,
    "The Economist": 16, "International Energy Agency": 20, "IEA": 20,
    "IRENA": 20, "Asian Development Bank": 20, "ADB": 20, "IMF": 20,
    "World Bank": 20, "UNCTAD": 19, "ESCAP": 19, "APEC": 20, "ASEAN": 20,
    "ASEAN Centre for Energy": 20, "Channel News Asia": 15,
    "South China Morning Post": 13, "World Economic Forum": 12
}
BLOCKED = (
    "britannica","wikipedia","haver analytics","opengov asia",
    "thailand business news","biometric update","economy.ac"
)

def fetch(query):
    url = "https://news.google.com/rss/search?q=" + quote(query) + "&hl=en-US&gl=US&ceid=US:en"
    root = ET.fromstring(urlopen(Request(url, headers=UA), timeout=30).read())
    out = []
    for item in root.findall("./channel/item")[:35]:
        raw = html.unescape(item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = item.findtext("pubDate") or ""
        src = item.find("source")
        source = (src.text or "").strip() if src is not None else ""
        title = raw
        if not source and " - " in raw:
            title, source = raw.rsplit(" - ", 1)
        try: dt = parsedate_to_datetime(pub).astimezone(timezone.utc)
        except: dt = None
        out.append({"title": title, "link": link, "source": source, "dt": dt})
    return out

def score_source(source):
    s = (source or "").lower()
    if any(x in s for x in BLOCKED): return -999
    score = 4
    for name, weight in PREFERRED.items():
        if name.lower() in s: score = max(score, weight)
    return score

def norm_title(title):
    return re.sub(r"\W+", " ", title.lower()).strip()

def collect(category, days=14, limit=18):
    raw = []
    for q in QUERIES[category]:
        try: raw += fetch(q)
        except Exception as e: print("feed error", category, e)

    now = datetime.now(timezone.utc)
    candidates = []
    seen = set()

    for x in raw:
        if not x["dt"]: continue
        age = (now - x["dt"]).total_seconds()/86400
        if age < 0 or age > days: continue
        base = score_source(x["source"])
        if base < 0: continue

        key = norm_title(x["title"])
        fuzzy = " ".join(key.split()[:10])
        if key in seen or fuzzy in seen: continue
        seen.add(key); seen.add(fuzzy)

        # Freshness helps ordering, but does not eliminate useful items from the last 2 weeks.
        freshness = max(0, 8 - age)
        score = base + freshness
        candidates.append({
            "title": x["title"], "link": x["link"], "source": x["source"],
            "published": x["dt"].strftime("%Y-%m-%d"),
            "category": category, "_score": score
        })

    candidates.sort(key=lambda z: z["_score"], reverse=True)
    for x in candidates: x.pop("_score", None)
    return candidates[:limit]

QUESTIONS = [
    "今天哪一条信息让你觉得：事情可能没有我原来想得那么简单？",
    "今天看到的变化里，哪些是周期性的，哪些可能是结构性的？",
    "如果站在利益受损方的角度，今天最重要的一条新闻会被怎样解释？",
    "今天哪一条信息可以和你过去读过的另一个问题连接起来？",
    "今天读到的内容里，哪些是事实，哪些其实已经包含了作者的判断？",
    "如果必须反驳自己对今天最重要新闻的第一反应，最强论据是什么？"
]

now = datetime.now(timezone.utc)
data = {
    "generated_at": now.strftime("%Y-%m-%d %H:%M UTC"),
    "date_display": now.strftime("%A · %d %B %Y"),
    "world": collect("world", 14, 18),
    "energy": collect("energy", 14, 18),
    "asia": collect("asia", 14, 18),
    "question": QUESTIONS[now.toordinal() % len(QUESTIONS)]
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
