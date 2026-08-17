from urllib.request import Request, urlopen
from urllib.parse import quote
from xml.etree import ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json, re, html
from pathlib import Path

OUT=Path(__file__).resolve().parents[1]/"data"/"news.json"
UA={"User-Agent":"Mozilla/5.0 ThinkingLab/1.0"}

QUERIES={
 "energy":[
   "Asia Pacific energy transition renewable energy grid energy security",
   "ASEAN clean energy renewable electricity grid"
 ],
 "asia":[
   "Asia regional cooperation trade RCEP ASEAN APEC economic integration",
   "Asia trade supply chain regional integration"
 ],
 "world":[
   "international economy geopolitics world economy Asia"
 ]
}
QUESTIONS=[
 "今天哪一条新闻真正改变了既有趋势，而不仅仅是延续了趋势？",
 "如果把今天最重要的一条新闻从相反立场解释，最强的论据是什么？",
 "今天的信息里，哪些是事实，哪些其实已经包含了作者的因果判断？",
 "谁从今天最重要的政策变化中获益，谁承担成本？",
 "今天看到的变化，是短期冲击，还是长期结构性变化？"
]

def fetch(query):
    url="https://news.google.com/rss/search?q="+quote(query)+"&hl=en-US&gl=US&ceid=US:en"
    req=Request(url,headers=UA)
    xml=urlopen(req,timeout=30).read()
    root=ET.fromstring(xml)
    out=[]
    for item in root.findall("./channel/item")[:12]:
        title=html.unescape(item.findtext("title") or "").strip()
        link=(item.findtext("link") or "").strip()
        pub=item.findtext("pubDate") or ""
        source=""
        src=item.find("source")
        if src is not None and src.text: source=src.text.strip()
        if not source and " - " in title:
            parts=title.rsplit(" - ",1); title,source=parts[0],parts[1]
        try:
            dt=parsedate_to_datetime(pub)
            published=dt.astimezone(timezone.utc).strftime("%Y-%m-%d")
        except Exception: published=pub[:16]
        out.append({"title":title,"link":link,"source":source,"published":published})
    return out

def build():
    data={}
    for cat,qs in QUERIES.items():
        seen=set(); arr=[]
        for q in qs:
            try: items=fetch(q)
            except Exception as e:
                print("feed error",cat,q,e); items=[]
            for x in items:
                key=re.sub(r"\W+"," ",x["title"].lower()).strip()
                if key in seen: continue
                seen.add(key); x["category"]=cat.capitalize(); arr.append(x)
        data[cat]=arr[:12]
    now=datetime.now(timezone.utc)
    data["generated_at"]=now.strftime("%Y-%m-%d %H:%M UTC")
    data["date_display"]=now.strftime("%A · %d %B %Y")
    data["question"]=QUESTIONS[now.toordinal()%len(QUESTIONS)]
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
build()
