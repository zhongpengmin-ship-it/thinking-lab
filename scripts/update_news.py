from urllib.request import Request, urlopen
from urllib.parse import quote
from xml.etree import ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
import json, re, html
from pathlib import Path

OUT=Path(__file__).resolve().parents[1]/"data"/"news.json"
UA={"User-Agent":"Mozilla/5.0 ThinkingLab/2.0"}

QUERIES={
 "energy":[
  '"energy transition" Asia OR ASEAN OR "Asia Pacific"',
  'renewable energy grid storage Asia ASEAN',
  'energy security Asia IEA IRENA'
 ],
 "asia":[
  'RCEP ASEAN APEC trade regional cooperation',
  '"Asian economic integration" trade investment',
  'Asia supply chain regional cooperation trade'
 ],
 "world":[
  'global economy geopolitics trade Reuters',
  'world economy IMF trade geopolitics',
  'international economy Asia Reuters'
 ]
}

# Higher scores are preferred. This is deliberately transparent and editable.
SOURCE_WEIGHTS={
 "Reuters":10,"Financial Times":9,"Bloomberg":9,"The Economist":8,
 "International Energy Agency":10,"IEA":10,"IRENA":10,
 "Asian Development Bank":10,"ADB":10,"IMF":10,"World Bank":10,
 "UNCTAD":9,"United Nations":8,"ESCAP":9,"APEC":9,"ASEAN":9,
 "Nikkei Asia":8,"South China Morning Post":7,"Channel News Asia":7,
 "World Economic Forum":6
}
BLOCKED=("britannica","wikipedia","haver analytics")

def fetch(query):
    url="https://news.google.com/rss/search?q="+quote(query)+"&hl=en-US&gl=US&ceid=US:en"
    req=Request(url,headers=UA)
    root=ET.fromstring(urlopen(req,timeout=30).read())
    out=[]
    for item in root.findall("./channel/item")[:25]:
        raw=html.unescape(item.findtext("title") or "").strip()
        link=(item.findtext("link") or "").strip()
        pub=item.findtext("pubDate") or ""
        src=item.find("source")
        source=(src.text or "").strip() if src is not None else ""
        title=raw
        if not source and " - " in raw:
            title,source=raw.rsplit(" - ",1)
        try: dt=parsedate_to_datetime(pub).astimezone(timezone.utc)
        except: dt=None
        out.append({"title":title,"link":link,"source":source,"dt":dt})
    return out

def source_score(source):
    s=source.lower()
    if any(x in s for x in BLOCKED): return -100
    best=2
    for name,w in SOURCE_WEIGHTS.items():
        if name.lower() in s: best=max(best,w)
    return best

def clean(items, category, max_age_days, limit):
    now=datetime.now(timezone.utc); seen=set(); arr=[]
    for x in items:
        if not x["dt"] or now-x["dt"]>timedelta(days=max_age_days): continue
        key=re.sub(r"\W+"," ",x["title"].lower()).strip()
        if key in seen: continue
        seen.add(key)
        score=source_score(x["source"])
        if score<0: continue
        # Freshness bonus, so a strong recent item beats an older generic one.
        age=max(0,(now-x["dt"]).total_seconds()/86400)
        score += max(0,4-age)
        x["score"]=score
        x["category"]=category
        x["published"]=x["dt"].strftime("%Y-%m-%d")
        del x["dt"]
        arr.append(x)
    arr.sort(key=lambda z:z["score"],reverse=True)
    for x in arr: x.pop("score",None)
    return arr[:limit]

def gather(cat, days, limit):
    raw=[]
    for q in QUERIES[cat]:
        try: raw.extend(fetch(q))
        except Exception as e: print("feed error:",cat,q,e)
    return clean(raw,cat.capitalize(),days,limit)

QUESTIONS=[
 "今天哪一条信息真正改变了既有趋势，而不只是延续了趋势？",
 "如果从利益受损方的角度看，今天最重要的一项政策会被怎样解释？",
 "今天读到的内容里，哪些是事实，哪些其实已经包含了因果判断？",
 "谁从今天最重要的变化中获益，谁承担成本？这种分配可持续吗？",
 "今天看到的是短期冲击，还是长期结构性变化？你凭什么判断？",
 "如果你必须反驳自己对今天最重要新闻的第一反应，最强论据是什么？"
]

now=datetime.now(timezone.utc)
data={
 "generated_at":now.strftime("%Y-%m-%d %H:%M UTC"),
 "date_display":now.strftime("%A · %d %B %Y"),
 "world":gather("world",3,3),
 "energy":gather("energy",7,12),
 "asia":gather("asia",7,12),
 "question":QUESTIONS[now.toordinal()%len(QUESTIONS)]
}
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
