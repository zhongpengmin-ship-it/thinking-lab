from urllib.request import Request, urlopen
from urllib.parse import urljoin
from xml.etree import ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
import json, re, html
from pathlib import Path

OUT=Path(__file__).resolve().parents[1]/"data"/"news.json"
UA={"User-Agent":"Mozilla/5.0 (compatible; ThinkingLab/1.0; personal RSS reader)"}

# DIRECT SOURCES ONLY — no Google News.
RSS = [
 # World / economy / analysis
 ("world","BBC World","https://feeds.bbci.co.uk/news/world/rss.xml","EN"),
 ("world","BBC Business","https://feeds.bbci.co.uk/news/business/rss.xml","EN"),
 ("world","BBC Technology","https://feeds.bbci.co.uk/news/technology/rss.xml","EN"),
 ("world","BIS","https://www.bis.org/doclist/rss_all_categories.rss","EN"),
 ("world","WTO","https://www.wto.org/library/rss/latest_news_e.xml","EN"),
 # Energy
 ("energy","IRENA","https://www.irena.org/rssfeed/News","EN"),
 ("energy","BIS","https://www.bis.org/doclist/rss_all_categories.rss","EN"),
 # Asia
 ("asia","WTO","https://www.wto.org/library/rss/latest_news_e.xml","EN"),
]

# For sources without a dependable public RSS endpoint, read their own public
# latest/news pages directly and collect article links. Failures are isolated.
PAGES = [
 ("world","Project Syndicate","https://www.project-syndicate.org/","EN"),
 ("world","The Economist","https://www.economist.com/","EN"),
 ("world","IMF","https://www.imf.org/en/News","EN"),
 ("world","World Bank","https://www.worldbank.org/en/news","EN"),
 ("world","OECD","https://www.oecd.org/en/about/news.html","EN"),
 ("world","UNCTAD","https://unctad.org/unctad-news","EN"),
 ("world","FT中文网","https://www.ftchinese.com/","中文"),
 ("world","财新","https://www.caixin.com/","中文"),
 ("world","第一财经","https://www.yicai.com/","中文"),
 ("energy","IEA","https://www.iea.org/news","EN"),
 ("energy","IRENA","https://www.irena.org/News","EN"),
 ("energy","ADB","https://www.adb.org/news","EN"),
 ("energy","ASEAN Centre for Energy","https://aseanenergy.org/news-clipping/","EN"),
 ("asia","ADB","https://www.adb.org/news","EN"),
 ("asia","ASEAN","https://asean.org/category/news/","EN"),
 ("asia","APEC","https://www.apec.org/press/news-releases","EN"),
 ("asia","ESCAP","https://www.unescap.org/news","EN"),
 ("asia","Nikkei Asia","https://asia.nikkei.com/","EN"),
 ("ideas","Project Syndicate","https://www.project-syndicate.org/","EN"),
 ("ideas","The Economist","https://www.economist.com/","EN"),
]

KEYWORDS={
"energy":("energy","electric","power","renewable","solar","wind","grid","battery","oil","gas","lng",
          "hydrogen","steel","climate","carbon","mineral","transition","能源","电力","可再生","光伏","储能","石油","天然气","氢"),
"asia":("asia","asian","asean","apec","rcep","china","japan","korea","india","pacific","trade","investment",
        "supply chain","regional","integration","亚洲","亚太","东盟","贸易","投资","供应链","区域"),
"ideas":("ai","artificial intelligence","society","science","technology","culture","work","democracy","education",
         "climate","future","人工智能","社会","科技","文化","教育")
}

def get(url):
    req=Request(url,headers=UA)
    with urlopen(req,timeout=25) as r:
        return r.read().decode("utf-8","ignore")

def parse_date(s):
    if not s:return None
    try:return parsedate_to_datetime(s).astimezone(timezone.utc)
    except: pass
    for fmt in ("%Y-%m-%d","%Y-%m-%dT%H:%M:%S%z","%Y-%m-%dT%H:%M:%SZ"):
        try:
            d=datetime.strptime(s[:25],fmt)
            return d.replace(tzinfo=d.tzinfo or timezone.utc).astimezone(timezone.utc)
        except: pass
    return None

def rss_items(cat,source,url,lang):
    text=get(url); root=ET.fromstring(text); out=[]
    nodes=root.findall(".//item")
    if not nodes: nodes=root.findall(".//{http://www.w3.org/2005/Atom}entry")
    for n in nodes[:60]:
        def val(names):
            for name in names:
                e=n.find(name)
                if e is not None and e.text:return html.unescape(e.text).strip()
            return ""
        title=val(["title","{http://www.w3.org/2005/Atom}title"])
        link=val(["link"])
        if not link:
            e=n.find("{http://www.w3.org/2005/Atom}link")
            if e is not None:link=e.attrib.get("href","")
        ds=val(["pubDate","date","{http://purl.org/dc/elements/1.1/}date",
                "{http://www.w3.org/2005/Atom}updated","{http://www.w3.org/2005/Atom}published"])
        if title and link:out.append(item(cat,source,title,link,parse_date(ds),lang))
    return out

class LinkParser(HTMLParser):
    def __init__(self,base):
        super().__init__();self.base=base;self.a=None;self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag=="a":
            d=dict(attrs);href=d.get("href","")
            if href:self.a=[urljoin(self.base,href),[]]
    def handle_data(self,data):
        if self.a:self.a[1].append(data)
    def handle_endtag(self,tag):
        if tag=="a" and self.a:
            text=" ".join(" ".join(self.a[1]).split())
            if text:self.links.append((text,self.a[0]))
            self.a=None

def page_items(cat,source,url,lang):
    text=get(url);p=LinkParser(url);p.feed(text);out=[];seen=set()
    host=re.sub(r"^https?://(www\.)?","",url).split("/")[0]
    for title,link in p.links:
        if len(title)<28 or len(title)>220:continue
        if host not in link:continue
        low=link.lower()
        if any(x in low for x in ("login","subscribe","privacy","terms","about","contact","newsletter","#")):continue
        key=re.sub(r"\W+"," ",title.lower()).strip()
        if key in seen:continue
        seen.add(key)
        out.append(item(cat,source,title,link,None,lang))
        if len(out)>=35:break
    return out

def item(cat,source,title,link,dt,lang):
    return {"category":cat,"source":source,"title":re.sub("<.*?>","",title).strip(),
            "link":link,"published":dt.strftime("%Y-%m-%d") if dt else "",
            "language":lang}

def relevant(x,cat):
    if cat=="world":return True
    s=x["title"].lower()
    return any(k in s for k in KEYWORDS.get(cat,()))

def dedupe(arr,limit):
    seen=set();out=[]
    # dated items first; undated direct-page items follow
    arr.sort(key=lambda x:x.get("published",""),reverse=True)
    for x in arr:
        key=" ".join(re.sub(r"\W+"," ",x["title"].lower()).split()[:10])
        if key in seen:continue
        seen.add(key);out.append(x)
        if len(out)>=limit:break
    return out

buckets={"world":[],"energy":[],"asia":[],"ideas":[]}
status=[]
for cat,source,url,lang in RSS:
    try:
        got=rss_items(cat,source,url,lang);buckets[cat]+=got;status.append([source,"ok",len(got)])
    except Exception as e:status.append([source,"failed",str(e)[:80]])
for cat,source,url,lang in PAGES:
    try:
        got=[x for x in page_items(cat,source,url,lang) if relevant(x,cat)]
        buckets[cat]+=got;status.append([source,"ok",len(got)])
    except Exception as e:status.append([source,"failed",str(e)[:80]])

# Cross-feed useful institutional items into specialist channels.
for x in buckets["world"][:]:
    if relevant(x,"energy"): buckets["energy"].append(dict(x,category="energy"))
    if relevant(x,"asia"): buckets["asia"].append(dict(x,category="asia"))
    if relevant(x,"ideas"): buckets["ideas"].append(dict(x,category="ideas"))


# ---- Balanced editorial assembly ----
WORLD_KEEP = (
 "econom","market","trade","tariff","inflation","interest rate","central bank","fed","ecb",
 "currency","dollar","yuan","yen","bond","debt","growth","gdp","investment","industry",
 "manufactur","supply chain","shipping","oil","gas","energy","climate","technology"," ai ",
 "artificial intelligence","chip","semiconductor","sanction","geopolit","war","conflict",
 "diplom","election","government","policy","china","united states","europe","india","japan",
 "经济","市场","贸易","关税","通胀","利率","央行","汇率","债务","增长","投资","产业","供应链",
 "能源","人工智能","芯片","地缘","政策","中国","美国","欧洲","印度","日本"
)
WORLD_DROP = (
 "football","soccer","tennis","cricket","celebrity","actor","actress","museum","painting",
 "sexual assault","murder","killed in crash","pubs","restaurant","fashion","royal family",
 "sports","lottery","zoo","wedding","电影","明星","足球","网球","餐厅","时尚"
)

def world_relevant(x):
    # Institutional and analysis sources are intentionally broader.
    if x["source"] in ("Project Syndicate","The Economist","IMF","World Bank","OECD","BIS","WTO","UNCTAD",
                       "FT中文网","财新","第一财经"):
        return True
    s=(" "+x["title"].lower()+" ")
    if any(k in s for k in WORLD_DROP): return False
    return any(k in s for k in WORLD_KEEP)

def unique_extend(dst, items, n, seen):
    added=0
    for x in items:
        key=" ".join(re.sub(r"\W+"," ",x["title"].lower()).split()[:10])
        if not key or key in seen: continue
        seen.add(key); dst.append(x); added+=1
        if added>=n: break

def balanced_world(items, limit=40):
    groups={}
    for x in items:
        if world_relevant(x): groups.setdefault(x["source"],[]).append(x)
    for g in groups.values():
        g.sort(key=lambda x:x.get("published",""), reverse=True)

    # Deliberately reserve room for each editorial role.
    quotas=[
      ("BBC World",5),("BBC Business",6),("BBC Technology",3),
      ("Project Syndicate",5),("The Economist",5),
      ("IMF",3),("World Bank",3),("OECD",3),("BIS",3),("WTO",3),("UNCTAD",3),
      ("FT中文网",4),("财新",4),("第一财经",4)
    ]
    out=[]; seen=set()
    for source,n in quotas:
        unique_extend(out, groups.get(source,[]), n, seen)

    # Fill remaining slots round-robin, not with one dominant source.
    sources=[s for s,_ in quotas]
    idx={s:0 for s in sources}
    while len(out)<limit:
        progressed=False
        for s in sources:
            arr=groups.get(s,[])
            while idx[s]<len(arr):
                x=arr[idx[s]]; idx[s]+=1
                before=len(out); unique_extend(out,[x],1,seen)
                if len(out)>before:
                    progressed=True; break
            if len(out)>=limit: break
        if not progressed: break
    return out[:limit]

def balanced_channel(items, limit, per_source=6):
    groups={}
    for x in items: groups.setdefault(x["source"],[]).append(x)
    for g in groups.values(): g.sort(key=lambda x:x.get("published",""),reverse=True)
    out=[];seen=set()
    # first pass guarantees diversity
    for s in groups:
        unique_extend(out,groups[s],min(per_source,limit),seen)
    # second pass fills any remaining room
    for s in groups:
        if len(out)>=limit: break
        unique_extend(out,groups[s],limit-len(out),seen)
    return out[:limit]

world_final=balanced_world(buckets["world"],40)
energy_final=balanced_channel(buckets["energy"],24,5)
asia_final=balanced_channel(buckets["asia"],24,5)
ideas_final=balanced_channel(buckets["ideas"],16,4)

now=datetime.now(timezone.utc)
data={
 "generated_at":now.strftime("%Y-%m-%d %H:%M UTC"),
 "date_display":now.strftime("%A · %d %B %Y"),
 "world":world_final,
 "energy":energy_final,
 "asia":asia_final,
 "ideas":ideas_final,
 "source_status":status,
 "question":"今天哪一条信息改变、挑战或复杂化了你原来的判断？为什么？"
}
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
