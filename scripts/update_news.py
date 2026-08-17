from urllib.request import Request, urlopen
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree as ET
from html.parser import HTMLParser
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import json, re, html
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data" / "news.json"
UA = {"User-Agent": "Mozilla/5.0 (compatible; ThinkingLab/2.0; personal research reader)"}
NOW = datetime.now(timezone.utc)

# ---------------------------------------------------------------------
# 1. DIRECT SOURCES ONLY. No Google News.
# ---------------------------------------------------------------------

RSS_SOURCES = [
    # World
    {"cat":"world","source":"BBC Business","url":"https://feeds.bbci.co.uk/news/business/rss.xml","lang":"EN"},
    {"cat":"world","source":"BBC World","url":"https://feeds.bbci.co.uk/news/world/rss.xml","lang":"EN"},
    {"cat":"world","source":"BBC Technology","url":"https://feeds.bbci.co.uk/news/technology/rss.xml","lang":"EN"},
    {"cat":"world","source":"BIS","url":"https://www.bis.org/doclist/rss_all_categories.rss","lang":"EN"},
    {"cat":"world","source":"WTO","url":"https://www.wto.org/library/rss/latest_news_e.xml","lang":"EN"},

    # Energy / Asia
    {"cat":"energy","source":"IRENA","url":"https://www.irena.org/rssfeed/News","lang":"EN"},
]

PAGE_SOURCES = [
    # World / economy / analysis
    {"cat":"world","source":"Project Syndicate","url":"https://www.project-syndicate.org/","lang":"EN",
     "allow":("/commentary/","/onpoint/","/say-more/")},
    {"cat":"world","source":"The Economist","url":"https://www.economist.com/","lang":"EN",
     "allow":("/finance-and-economics/","/business/","/international/","/china/","/asia/","/united-states/","/science-and-technology/")},
    {"cat":"world","source":"IMF","url":"https://www.imf.org/en/News","lang":"EN",
     "allow":("/en/news/articles/","/en/news/press-releases/","/en/news/speeches/")},
    {"cat":"world","source":"World Bank","url":"https://www.worldbank.org/en/news","lang":"EN",
     "allow":("/en/news/press-release/","/en/news/statement/","/en/news/feature/","/en/news/speech/")},
    {"cat":"world","source":"OECD","url":"https://www.oecd.org/en/about/news.html","lang":"EN",
     "allow":("/en/about/news/","/en/blogs/","/en/publications/")},
    {"cat":"world","source":"UNCTAD","url":"https://unctad.org/unctad-news","lang":"EN",
     "allow":("/news/","/press-material/")},
    {"cat":"world","source":"FT中文网","url":"https://www.ftchinese.com/","lang":"中文",
     "allow":("/story/","/interactive/")},
    {"cat":"world","source":"财新","url":"https://www.caixin.com/","lang":"中文",
     "allow":("/2026-","finance.caixin.com/2026-","economy.caixin.com/2026-","international.caixin.com/2026-")},
    {"cat":"world","source":"第一财经","url":"https://www.yicai.com/","lang":"中文",
     "allow":("/news/","/video/")},

    # Energy
    {"cat":"energy","source":"IEA","url":"https://www.iea.org/news","lang":"EN",
     "allow":("/news/","/commentaries/")},
    {"cat":"energy","source":"IRENA","url":"https://www.irena.org/News","lang":"EN",
     "allow":("/News/articles/","/News/pressreleases/")},
    {"cat":"energy","source":"ADB","url":"https://www.adb.org/news","lang":"EN",
     "allow":("/news/")},
    {"cat":"energy","source":"ASEAN Centre for Energy","url":"https://aseanenergy.org/","lang":"EN",
     "allow":("/post/","/news/","/publications/")},

    # Asia
    {"cat":"asia","source":"ADB","url":"https://www.adb.org/news","lang":"EN",
     "allow":("/news/")},
    {"cat":"asia","source":"ASEAN","url":"https://asean.org/category/news/","lang":"EN",
     "allow":("/2026/","/post/","/news/")},
    {"cat":"asia","source":"APEC","url":"https://www.apec.org/press/news-releases","lang":"EN",
     "allow":("/press/news-releases/")},
    {"cat":"asia","source":"ESCAP","url":"https://www.unescap.org/news","lang":"EN",
     "allow":("/news/")},
    {"cat":"asia","source":"Nikkei Asia","url":"https://asia.nikkei.com/","lang":"EN",
     "allow":("/Economy/","/Politics/","/Business/","/Spotlight/","/Trade/")},

    # Ideas & Trends
    {"cat":"ideas","source":"Project Syndicate","url":"https://www.project-syndicate.org/","lang":"EN",
     "allow":("/commentary/","/onpoint/","/say-more/")},
    {"cat":"ideas","source":"The Economist","url":"https://www.economist.com/","lang":"EN",
     "allow":("/science-and-technology/","/culture/","/business/","/finance-and-economics/","/international/")},
]

# ---------------------------------------------------------------------
# 2. Editorial rules
# ---------------------------------------------------------------------

# World Radar is about world economy + major international developments with economic significance.
MACRO_KW = (
    "econom","growth","gdp","inflation","interest rate","central bank","fed","ecb","boj",
    "currency","dollar","yuan","yen","bond","debt","fiscal","budget","tax","tariff",
    "trade","export","import","market","stocks","equity","bank","finance","investment",
    "industry","manufactur","supply chain","shipping","commodity","oil","gas","energy",
    "semiconductor","chip","technology","artificial intelligence"," ai ","productivity",
    "labor market","employment","unemployment","wage","housing","consumption","retail",
    "经济","增长","国内生产总值","通胀","利率","央行","汇率","美元","人民币","日元","债券",
    "债务","财政","预算","税","关税","贸易","出口","进口","市场","股市","银行","金融","投资",
    "产业","制造","供应链","航运","大宗商品","石油","天然气","能源","半导体","芯片","人工智能",
    "生产率","就业","工资","房地产","消费","零售"
)

GEOPOL_ECON_KW = (
    "sanction","geopolit","trade war","economic security","national security","military drills",
    "war","conflict","ceasefire","peace plan","diplom","alliance","nato","iran","israel",
    "middle east","russia","ukraine","china","united states","european union","india","japan","korea",
    "制裁","地缘","经贸摩擦","经济安全","国家安全","军演","战争","冲突","停火","和平方案",
    "外交","联盟","北约","伊朗","以色列","中东","俄罗斯","乌克兰","中国","美国","欧盟","印度","日本","韩国"
)

POLICY_KW = (
    "policy","regulation","government","election","reform","subsidy","industrial policy",
    "competition","antitrust","climate policy","carbon price","digital regulation",
    "政策","监管","政府","选举","改革","补贴","产业政策","竞争","反垄断","气候政策","碳价","数字监管"
)

WORLD_DROP = (
    "football","soccer","tennis","cricket","celebrity","actor","actress","museum","painting",
    "sexual assault","murder","pubs","restaurant","fashion","royal family","lottery","zoo",
    "wedding","statue","landslide","record rains","weather warning","flooding","tourism fee",
    "camera after shopper","shopper ousted","gym","pilates","twitch users outraged",
    "电影","明星","足球","网球","餐厅","时尚","旅游费","博物馆","雕像","鹅腿阿姨",
    "纪念江泽民","诞辰100周年","半年报","净利润同比","营业收入","业绩快报","战地记者们如何看"
)

ENERGY_KW = (
    "energy","electric","power","renewable","solar","wind","grid","battery","storage","oil","gas",
    "lng","hydrogen","steel","climate","carbon","mineral","transition","能源","电力","可再生",
    "光伏","风电","电网","储能","石油","天然气","氢","钢铁","矿产","转型"
)

ASIA_KW = (
    "asia","asian","asean","apec","rcep","china","japan","korea","india","pacific","trade",
    "investment","supply chain","regional","integration","亚洲","亚太","东盟","贸易","投资",
    "供应链","区域","一体化","中国","日本","韩国","印度"
)

IDEAS_KW = (
    "ai","artificial intelligence","society","science","technology","culture","work","democracy",
    "education","climate","future","人工智能","社会","科技","文化","教育","未来"
)

MAX_AGE = {
    "world": 21,
    "energy": 30,
    "asia": 30,
    "ideas": 45,
}

# ---------------------------------------------------------------------
# 3. HTTP + parsing
# ---------------------------------------------------------------------

def get(url, timeout=15):
    req = Request(url, headers=UA)
    with urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "ignore")

def parse_date_string(s):
    if not s:
        return None
    s = html.unescape(s).strip()
    try:
        return parsedate_to_datetime(s).astimezone(timezone.utc)
    except Exception:
        pass
    # ISO variants
    m = re.search(r"(20\d{2})-(\d{2})-(\d{2})", s)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
        except Exception:
            pass
    return None

def date_from_url(url):
    # YYYY-MM-DD, YYYY/MM/DD
    m = re.search(r"(20\d{2})[-/](0?[1-9]|1[0-2])[-/](0?[1-9]|[12]\d|3[01])", url)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
        except Exception:
            pass

    # Project Syndicate often encodes YYYY-MM only.
    m = re.search(r"-(20\d{2})-(0?[1-9]|1[0-2])(?:\b|/)", url)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1, tzinfo=timezone.utc)
        except Exception:
            pass
    return None

def published_date_from_html(text, url=""):
    patterns = [
        r'<meta[^>]+property=["\']article:published_time["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']article:published_time["\']',
        r'<meta[^>]+name=["\']date["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+name=["\']publish(?:ed)?date["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+itemprop=["\']datePublished["\'][^>]+content=["\']([^"\']+)',
        r'"datePublished"\s*:\s*"([^"]+)"',
        r'"dateCreated"\s*:\s*"([^"]+)"',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            d = parse_date_string(m.group(1))
            if d:
                return d
    return date_from_url(url)

class LinkParser(HTMLParser):
    def __init__(self, base):
        super().__init__()
        self.base = base
        self.current = None
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            d = dict(attrs)
            href = d.get("href", "")
            if href:
                self.current = [urljoin(self.base, href), []]

    def handle_data(self, data):
        if self.current:
            self.current[1].append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.current:
            title = " ".join(" ".join(self.current[1]).split())
            if title:
                self.links.append((title, self.current[0]))
            self.current = None

# ---------------------------------------------------------------------
# 4. Source extraction
# ---------------------------------------------------------------------

def valid_article_url(source_def, link):
    low = link.lower()
    allow = source_def.get("allow", ())
    if allow and not any(a.lower() in low for a in allow):
        return False

    reject = (
        "/topic/","/topics/","/category/","/categories/","/tag/","/tags/",
        "/publications-search","/search","/about","/contact","/privacy","/terms",
        "/subscribe","/login","/account","/authors/","/events/","/home"
    )
    if any(x in low for x in reject):
        return False

    # Explicit known junk
    if source_def["source"] == "第一财经" and "/brief/" in low:
        return False
    if source_def["source"] == "财新" and "mini.caixin.com" in low:
        return False
    if source_def["source"] == "World Bank" and "/ext/" in low:
        return False

    return True

def page_candidates(source_def):
    text = get(source_def["url"])
    p = LinkParser(source_def["url"])
    p.feed(text)

    seen = set()
    out = []
    for title, link in p.links:
        title = re.sub(r"\s+", " ", title).strip()
        if len(title) < 24 or len(title) > 220:
            continue
        if title.startswith("http://") or title.startswith("https://"):
            continue
        if not valid_article_url(source_def, link):
            continue

        key = " ".join(re.sub(r"\W+", " ", title.lower()).split()[:12])
        if not key or key in seen:
            continue
        seen.add(key)
        out.append((title, link))

        if len(out) >= 18:
            break
    return out

def enrich_candidate(source_def, title, link):
    try:
        article_html = get(link, timeout=12)
        dt = published_date_from_html(article_html, link)
    except Exception:
        dt = date_from_url(link)

    # STRICT: if no reliable date, do not admit into a daily/weekly radar.
    if not dt:
        return None

    age_days = (NOW - dt).total_seconds() / 86400
    if age_days < -1 or age_days > MAX_AGE[source_def["cat"]]:
        return None

    return {
        "category": source_def["cat"],
        "source": source_def["source"],
        "title": title,
        "link": link,
        "published": dt.strftime("%Y-%m-%d"),
        "language": source_def["lang"],
    }

def scrape_page_source(source_def):
    try:
        candidates = page_candidates(source_def)
    except Exception as e:
        return [], f"landing page failed: {str(e)[:80]}"

    items = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futures = [ex.submit(enrich_candidate, source_def, t, l) for t, l in candidates]
        for fut in as_completed(futures):
            try:
                x = fut.result()
                if x:
                    items.append(x)
            except Exception:
                pass

    items.sort(key=lambda x: x["published"], reverse=True)
    return items, f"ok {len(items)}"

def parse_rss(source_def):
    text = get(source_def["url"])
    root = ET.fromstring(text)
    nodes = root.findall(".//item")
    if not nodes:
        nodes = root.findall(".//{http://www.w3.org/2005/Atom}entry")

    out = []
    for n in nodes[:60]:
        def val(names):
            for name in names:
                e = n.find(name)
                if e is not None and e.text:
                    return html.unescape(e.text).strip()
            return ""

        title = val(["title","{http://www.w3.org/2005/Atom}title"])
        link = val(["link"])
        if not link:
            e = n.find("{http://www.w3.org/2005/Atom}link")
            if e is not None:
                link = e.attrib.get("href", "")

        ds = val([
            "pubDate","date","{http://purl.org/dc/elements/1.1/}date",
            "{http://www.w3.org/2005/Atom}updated","{http://www.w3.org/2005/Atom}published"
        ])
        dt = parse_date_string(ds)
        if not title or not link or not dt:
            continue

        age = (NOW - dt).total_seconds() / 86400
        if age < -1 or age > MAX_AGE[source_def["cat"]]:
            continue

        out.append({
            "category": source_def["cat"],
            "source": source_def["source"],
            "title": re.sub(r"<.*?>","",title).strip(),
            "link": link,
            "published": dt.strftime("%Y-%m-%d"),
            "language": source_def["lang"],
        })
    return out

# ---------------------------------------------------------------------
# 5. Editorial relevance
# ---------------------------------------------------------------------

def contains_any(text, words):
    t = " " + text.lower() + " "
    return any(w in t for w in words)

def relevant(x, cat):
    title = x["title"]
    t = " " + title.lower() + " "

    if cat == "world":
        if contains_any(title, WORLD_DROP):
            return False

        # Major institutions / analysis outlets still need substantive economic or geopolitical relevance.
        institutional = x["source"] in (
            "Project Syndicate","The Economist","IMF","World Bank","OECD","BIS","WTO","UNCTAD"
        )

        macro = contains_any(title, MACRO_KW)
        policy = contains_any(title, POLICY_KW)
        geop = contains_any(title, GEOPOL_ECON_KW)

        # Core rule: economic/market/policy content always qualifies.
        if macro or policy:
            return True

        # Geopolitical news qualifies only if it is a major state-to-state / war / sanctions / diplomacy issue.
        if geop:
            major_terms = (
                "sanction","war","conflict","ceasefire","peace plan","military drills","trade war",
                "iran","israel","middle east","russia","ukraine","china","united states",
                "european union","india","japan","korea",
                "制裁","战争","冲突","停火","和平方案","军演","中东","俄罗斯","乌克兰",
                "中国","美国","欧盟","印度","日本","韩国"
            )
            return any(k in t for k in major_terms)

        # Opinion/analysis pieces without a clear economic or geopolitical hook do not enter World Radar.
        if institutional:
            return False

        return False

    if cat == "energy":
        return contains_any(title, ENERGY_KW)

    if cat == "asia":
        return contains_any(title, ASIA_KW)

    if cat == "ideas":
        return contains_any(title, IDEAS_KW)

    return True

# ---------------------------------------------------------------------
# 6. Dedupe + balanced assembly
# ---------------------------------------------------------------------

def dedupe(items):
    seen = set()
    out = []
    for x in sorted(items, key=lambda z: z["published"], reverse=True):
        key = " ".join(re.sub(r"\W+"," ",x["title"].lower()).split()[:11])
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(x)
    return out

def interleave_by_source(items, source_order, source_caps, limit):
    groups = {}
    for x in items:
        groups.setdefault(x["source"], []).append(x)

    for s in groups:
        groups[s].sort(key=lambda x: x["published"], reverse=True)

    cursors = {s:0 for s in source_order}
    used = {s:0 for s in source_order}
    out = []
    seen = set()

    while len(out) < limit:
        progressed = False
        for s in source_order:
            if used[s] >= source_caps.get(s, 0):
                continue
            arr = groups.get(s, [])
            while cursors[s] < len(arr):
                x = arr[cursors[s]]
                cursors[s] += 1
                key = " ".join(re.sub(r"\W+"," ",x["title"].lower()).split()[:11])
                if key in seen:
                    continue
                seen.add(key)
                out.append(x)
                used[s] += 1
                progressed = True
                break
            if len(out) >= limit:
                break
        if not progressed:
            break

    return out[:limit]

WORLD_ORDER = [
    "BBC Business","Project Syndicate","FT中文网","BBC World","IMF","财新",
    "The Economist","WTO","第一财经","World Bank","BBC Technology","BIS","OECD","UNCTAD"
]
WORLD_CAPS = {
    "BBC Business":6,"BBC World":4,"BBC Technology":3,
    "Project Syndicate":6,"The Economist":5,
    "IMF":4,"World Bank":4,"OECD":4,"BIS":4,"WTO":4,"UNCTAD":4,
    "FT中文网":6,"财新":6,"第一财经":5
}

# ---------------------------------------------------------------------
# 7. Run
# ---------------------------------------------------------------------

buckets = {"world":[],"energy":[],"asia":[],"ideas":[]}
status = []

# RSS first
for s in RSS_SOURCES:
    try:
        items = [x for x in parse_rss(s) if relevant(x, s["cat"])]
        buckets[s["cat"]].extend(items)
        status.append([s["source"], "ok", len(items)])
    except Exception as e:
        status.append([s["source"], "failed", str(e)[:100]])

# Direct pages
for s in PAGE_SOURCES:
    items, st = scrape_page_source(s)
    items = [x for x in items if relevant(x, s["cat"])]
    buckets[s["cat"]].extend(items)
    status.append([s["source"], st, len(items)])

# Cross-feed genuinely relevant World items into specialist channels
for x in list(buckets["world"]):
    if relevant(x, "energy"):
        y = dict(x); y["category"] = "energy"; buckets["energy"].append(y)
    if relevant(x, "asia"):
        y = dict(x); y["category"] = "asia"; buckets["asia"].append(y)
    if relevant(x, "ideas"):
        y = dict(x); y["category"] = "ideas"; buckets["ideas"].append(y)

world = interleave_by_source(
    dedupe(buckets["world"]), WORLD_ORDER, WORLD_CAPS, 40
)

# Other channels: diversity cap of 6 per source
def balanced_generic(items, limit=28, per_source=6):
    items = dedupe(items)
    groups = {}
    for x in items:
        groups.setdefault(x["source"], []).append(x)
    order = list(groups.keys())
    caps = {s:per_source for s in order}
    return interleave_by_source(items, order, caps, limit)

energy = balanced_generic(buckets["energy"], 28, 6)
asia = balanced_generic(buckets["asia"], 28, 6)
ideas = balanced_generic(buckets["ideas"], 18, 5)

data = {
    "generated_at": NOW.strftime("%Y-%m-%d %H:%M UTC"),
    "date_display": NOW.strftime("%A · %d %B %Y"),
    "world": world,
    "energy": energy,
    "asia": asia,
    "ideas": ideas,
    "source_status": status,
    "question": "今天哪一条信息改变、挑战或复杂化了你原来的判断？为什么？"
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
