import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import quote_plus

import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from bs4 import BeautifulSoup


st.set_page_config(page_title="Are We Cooked? 🌍", page_icon="🌍", layout="wide")

PACIFIC = ZoneInfo("America/Los_Angeles")
HEADERS = {"User-Agent": "Mozilla/5.0 (AreWeCooked public-data dashboard)"}
GDELT = "https://api.gdeltproject.org/api/v2/doc/doc"
NOAA = "https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/ensodisc.shtml"
FAO = "https://www.fao.org/worldfoodsituation/foodpricesindex/en/"
REFRESH = "15m"

st.markdown("""
<style>
.stApp{background:#0b0d10;color:#f4f7f8}
.block-container{max-width:1450px;padding-top:1.5rem;padding-bottom:4rem}
.eyebrow{color:#8f9aa5;font-size:.75rem;letter-spacing:.16em;font-weight:800}
.hero{font-size:clamp(2.6rem,5vw,4.8rem);font-weight:850;letter-spacing:-.05em;line-height:1}
.sub{color:#b7c0c8;margin:.7rem 0 1.2rem}
.panel,.card{background:#14181d;border:1px solid #29323b;border-radius:20px;padding:20px}
.card{margin-bottom:10px}
.label{color:#8f9aa5;font-size:.72rem;letter-spacing:.1em;font-weight:800}
.score{font-size:4.8rem;font-weight:850;line-height:1}
.cat-score{font-size:2.1rem;font-weight:850}
.muted{color:#9aa5b1}
.section{font-size:1.7rem;font-weight:850;margin:1.7rem 0 .8rem}
.live{color:#6ddd98}.partial{color:#f2d964}.down{color:#ff7f7f}
a{color:#7fd1c8!important}
</style>
""", unsafe_allow_html=True)


def clamp(x): return max(0.0, min(10.0, x))

def color(score):
    if score <= 2: return "#49c878"
    if score <= 5: return "#e8c547"
    if score < 8: return "#f29f3d"
    return "#ef5c5c"

def status(score):
    if score <= 2: return "NORMAL"
    if score <= 5: return "ELEVATED"
    if score < 8: return "SERIOUS"
    return "CRITICAL"

def trend(cur, prev):
    if prev is None: return "→ Stable"
    d = cur - prev
    if d <= -.5: return "↓ Improving"
    if d >= 1: return "↑ Worsening quickly"
    if d >= .35: return "↗ Worsening"
    return "→ Stable"

def clean(s): return re.sub(r"\s+", " ", s or "").strip()

def get(url, params=None, timeout=5):
    r = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    return r


CONFIG = {
    "Energy": {
        "emoji":"🛢️","base":4.5,
        "query":"(oil OR crude OR LNG OR pipeline OR refinery OR Hormuz OR tanker)",
        "bad":["blockade","shortage","rationing","shutdown","attack","disruption","hormuz","outage"],
        "good":["reopen","restored","resume","ceasefire","repaired"],
        "next":"A sustained loss of export, refinery, pipeline, or shipping capacity.",
        "up":"Physical shortages, chokepoint closure, rationing, or major capacity loss.",
        "down":"Restored shipping/capacity and sustained easing of supply disruption."
    },
    "War / Geopolitics": {
        "emoji":"⚔️","base":5.0,
        "query":"(war OR missile OR drone OR invasion OR ceasefire OR airstrike OR mobilization)",
        "bad":["nuclear","invasion","mobilization","barrage","escalation","attack","strike"],
        "good":["ceasefire","truce","agreement","withdrawal","talks"],
        "next":"A wider state-on-state war or attacks on strategic infrastructure.",
        "up":"New combatants, direct great-power clashes, mobilization, or nuclear escalation.",
        "down":"Durable ceasefires, negotiations, withdrawals, and fewer attacks."
    },
    "Economy": {
        "emoji":"💰","base":3.5,
        "query":"(recession OR inflation OR default OR layoffs OR banking OR markets OR credit)",
        "bad":["default","crash","recession","bank failure","layoffs","stagflation","plunge"],
        "good":["growth","recovery","inflation falls","rate cut","jobs gain"],
        "next":"Inflation, recession, or credit stress spreading into employment and industry.",
        "up":"Bank failures, frozen credit, deep recession, defaults, or broad layoffs.",
        "down":"Improving growth, inflation, employment, and credit conditions."
    },
    "Climate": {
        "emoji":"🌡️","base":4.0,
        "query":"(heatwave OR drought OR flood OR wildfire OR hurricane OR cyclone OR climate)",
        "bad":["record","catastrophic","emergency","evacuation","drought","wildfire","flood"],
        "good":["contained","weakened","rainfall","recovery"],
        "next":"Multiple severe climate hazards hitting food, energy, or population centers together.",
        "up":"Concurrent damaging heat, drought, flood, fire, or storm events.",
        "down":"Hazards remain localized and seasonal outlooks moderate."
    },
    "Food": {
        "emoji":"🌾","base":3.5,
        "query":"(famine OR food prices OR crop OR wheat OR rice OR fertilizer OR harvest)",
        "bad":["famine","shortage","export ban","crop failure","rationing","surge","drought"],
        "good":["harvest","prices fall","surplus","exports resume"],
        "next":"Export restrictions or harvest shocks causing broad food-price or availability stress.",
        "up":"Major crop failures, export bans, fertilizer shortages, or physical shortages.",
        "down":"Strong harvests, reopened trade, and easing food prices."
    },
    "AI": {
        "emoji":"🤖","base":4.0,
        "query":"(AI OR artificial intelligence OR autonomous agents OR AI safety)",
        "bad":["cyberattack","biosecurity","self-replication","jailbreak","safeguard","autonomous weapons","misuse"],
        "good":["safety standard","regulation","safeguard","evaluation"],
        "next":"More capable autonomous systems causing consequential cyber, bio, or control failures.",
        "up":"Demonstrated dangerous autonomy, control evasion, or major AI-enabled incidents.",
        "down":"Effective safeguards, slower capability growth, and fewer serious incidents."
    },
    "Infrastructure / Cyber": {
        "emoji":"🏗️","base":3.5,
        "query":"(cyberattack OR ransomware OR blackout OR power grid OR telecom OR critical infrastructure)",
        "bad":["blackout","ransomware","shutdown","outage","attack","disruption","breach"],
        "good":["restored","recovered","patched","contained"],
        "next":"A cyber/physical cascade affecting grids, telecoms, ports, pipelines, or payments.",
        "up":"Multi-region outages or destructive attacks on critical infrastructure.",
        "down":"Fast recovery, contained attacks, and fewer major outages."
    }
}


@st.cache_data(ttl=900, show_spinner=False)
def gdelt(query):
    # IMPORTANT: one OR block only. GDELT does not support nested OR blocks.
    try:
        r = get(GDELT, {
            "query": query,
            "mode":"artlist",
            "format":"json",
            "timespan":"24h",
            "maxrecords":20,
            "sort":"datedesc"
        })
        data = r.json()
        out = []
        for a in data.get("articles", []):
            title = clean(a.get("title"))
            if title:
                out.append({"title":title,"url":a.get("url",""),"domain":a.get("domain",""),"source":"GDELT"})
        if out:
            return out, "live"
    except Exception:
        pass
    return [], "failed"


@st.cache_data(ttl=900, show_spinner=False)
def google_news(query):
    # Free RSS fallback. We only use article titles/links as signals.
    try:
        url = "https://news.google.com/rss/search?q=" + quote_plus(query + " when:1d") + "&hl=en-US&gl=US&ceid=US:en"
        r = get(url)
        root = ET.fromstring(r.content)
        out = []
        for item in root.findall(".//item")[:20]:
            title = clean(item.findtext("title"))
            link = clean(item.findtext("link"))
            source_node = item.find("source")
            domain = clean(source_node.text) if source_node is not None else "Google News"
            if title:
                out.append({"title":title,"url":link,"domain":domain,"source":"Google News RSS"})
        if out:
            return out, "live"
    except Exception:
        pass
    return [], "failed"


@st.cache_data(ttl=21600, show_spinner=False)
def noaa_signal():
    try:
        text = clean(BeautifulSoup(get(NOAA, timeout=6).text, "html.parser").get_text(" "))
        low = text.lower()
        score = 4.0
        summary = "NOAA ENSO discussion is available."
        if "very strong event" in low:
            score, summary = 6.5, "NOAA says a very strong ENSO event is likely/current."
        elif "el niño advisory" in low:
            score, summary = 5.0, "NOAA has an El Niño Advisory in effect."
        elif "la niña advisory" in low:
            score, summary = 4.5, "NOAA has a La Niña Advisory in effect."
        elif "enso-neutral" in low:
            score, summary = 3.0, "NOAA indicates ENSO-neutral conditions."
        m = re.search(r"Synopsis:\s*(.{0,350}?)(?:\s{2,}|Discussion:)", text, re.I)
        if m: summary = clean(m.group(1))
        return {"ok":True,"score":score,"summary":summary}
    except Exception:
        return {"ok":False}


@st.cache_data(ttl=21600, show_spinner=False)
def fao_signal():
    try:
        text = clean(BeautifulSoup(get(FAO, timeout=6).text, "html.parser").get_text(" "))
        # Latest page usually includes: "averaged X points ... up/down Y percent ... year ago"
        year = re.search(r"(\d+(?:\.\d+)?)\s*percent\)?\s*(higher|lower)\s*than\s*a year ago", text, re.I)
        month = re.search(r"(up|down)\s+\d+(?:\.\d+)?\s+points\s+\((\d+(?:\.\d+)?)\s*percent\)", text, re.I)
        score = 3.5
        bits = []
        if year:
            pct = float(year.group(1))
            direction = year.group(2).lower()
            bits.append(f"FAO food prices are {pct:.1f}% {direction} than a year ago.")
            if direction == "higher":
                score += min(2.0, pct / 5)
            else:
                score -= min(1.0, pct / 10)
        if month:
            direction = month.group(1).lower()
            pct = float(month.group(2))
            bits.append(f"Latest monthly move: {direction} {pct:.1f}%.")
            score += min(1.0, pct / 3) if direction == "up" else -min(.7, pct / 4)
        return {"ok":True,"score":round(clamp(score)*2)/2,"summary":" ".join(bits) or "FAO Food Price Index page is available."}
    except Exception:
        return {"ok":False}


def score_news(name, cfg, articles, source_state, previous=None):
    if not articles:
        # Critical rule: source failure is NOT zero risk.
        keep = previous if previous is not None else cfg["base"]
        return {
            "name":name,"emoji":cfg["emoji"],"score":round(keep*2)/2,
            "trend":"→ Unchanged (data unavailable)",
            "summary":"Fresh news data is unavailable. Keeping the last known/baseline score — not treating missing data as good news.",
            "next_risk":cfg["next"],"raises_score":cfg["up"],"lowers_score":cfg["down"],
            "signals":[],"data_status":"unavailable"
        }

    blob = " ".join(x["title"].lower() for x in articles)
    bad = sum(1 for k in cfg["bad"] if k.lower() in blob)
    good = sum(1 for k in cfg["good"] if k.lower() in blob)

    # Headlines are a modifier, never the whole score.
    adjustment = min(2.0, bad * .35) - min(1.0, good * .25)
    score = round(clamp(cfg["base"] + adjustment)*2)/2

    return {
        "name":name,"emoji":cfg["emoji"],"score":score,
        "trend":trend(score, previous),
        "summary":f"Fresh public-news signals: {len(articles)} items checked; {bad} escalation terms and {good} easing terms detected.",
        "next_risk":cfg["next"],"raises_score":cfg["up"],"lowers_score":cfg["down"],
        "signals":articles[:5],"data_status":source_state
    }


def fetch_category(name, cfg, previous):
    articles, state = gdelt(cfg["query"])
    if not articles:
        articles, state2 = google_news(cfg["query"])
        state = "fallback" if articles else "failed"
    return score_news(name, cfg, articles, state, previous)


def build_report():
    prev_report = st.session_state.get("last_report")
    prev = {}
    if prev_report:
        prev = {c["name"]:float(c["score"]) for c in prev_report["categories"]}

    cats = {}
    # Category news pulls happen in parallel.
    with ThreadPoolExecutor(max_workers=7) as pool:
        jobs = {pool.submit(fetch_category, n, cfg, prev.get(n)):n for n,cfg in CONFIG.items()}
        for f in as_completed(jobs):
            n = jobs[f]
            try:
                cats[n] = f.result()
            except Exception:
                cats[n] = score_news(n, CONFIG[n], [], "failed", prev.get(n))

    # Official-source modifiers. Failure does not lower a score.
    with ThreadPoolExecutor(max_workers=2) as pool:
        n_future = pool.submit(noaa_signal)
        f_future = pool.submit(fao_signal)
        noaa = n_future.result()
        fao = f_future.result()

    if noaa.get("ok"):
        c = cats["Climate"]
        old = c["score"]
        c["score"] = round(((old*.55)+(noaa["score"]*.45))*2)/2
        c["trend"] = trend(c["score"], prev.get("Climate"))
        c["summary"] = noaa["summary"] + " " + c["summary"]
        c["data_status"] = "official + news" if c["signals"] else "official only"

    if fao.get("ok"):
        c = cats["Food"]
        old = c["score"]
        c["score"] = round(((old*.45)+(fao["score"]*.55))*2)/2
        c["trend"] = trend(c["score"], prev.get("Food"))
        c["summary"] = fao["summary"] + " " + c["summary"]
        c["data_status"] = "official + news" if c["signals"] else "official only"

    order = list(CONFIG.keys())
    categories = [cats[n] for n in order]

    weights = {
        "Energy":1.25,"War / Geopolitics":1.25,"Economy":1.0,
        "Climate":.9,"Food":1.0,"AI":.85,"Infrastructure / Cyber":1.0
    }
    available = [c for c in categories if c["data_status"] != "unavailable"]
    scores = {c["name"]:c["score"] for c in categories}
    overall = sum(scores[n]*weights[n] for n in scores)/sum(weights.values())

    severe = sum(s >= 7 for s in scores.values())
    elevated = sum(s >= 5.5 for s in scores.values())
    if severe >= 2: overall += .5
    if severe >= 3: overall += .5
    if elevated >= 5: overall += .35
    overall = round(clamp(overall)*2)/2

    prev_overall = prev_report.get("overall_score") if prev_report else None
    biggest = max(categories, key=lambda c:c["score"])
    now = datetime.now(PACIFIC)

    return {
        "report_date":now.strftime("%B %d, %Y"),
        "checked_at":now.strftime("%b %d, %Y · %I:%M %p %Z"),
        "overall_score":overall,
        "overall_trend":trend(overall, prev_overall),
        "summary":f"{len(available)}/7 categories have fresh data this check. Missing feeds keep their prior/baseline score instead of being counted as zero.",
        "biggest":biggest,
        "categories":categories
    }


if "last_report" not in st.session_state: st.session_state.last_report = None
if "history" not in st.session_state: st.session_state.history = []


def render(report):
    s = report["overall_score"]
    st.html(f"""
    <div class="eyebrow">GLOBAL RISK DASHBOARD</div>
    <div class="hero">Are We Cooked? 🌍</div>
    <div class="sub">A rules-based global systemic-risk meter using free public data. No paid AI calls.</div>
    """)

    a,b = st.columns([1.1,4])
    with a:
        if st.button("🔄 Refresh Now", type="primary", use_container_width=True):
            gdelt.clear(); google_news.clear(); noaa_signal.clear(); fao_signal.clear()
            st.rerun()
    with b:
        st.caption(f"Last checked: {report['checked_at']} · Auto-refreshes every 15 minutes while open.")

    c1,c2 = st.columns([1.7,1], gap="large")
    with c1:
        st.html(f"""
        <div class="panel">
          <div class="label">OVERALL GLOBAL RISK</div>
          <div class="score">{s:.1f}<span style="font-size:1.2rem;color:#8f9aa5"> /10</span></div>
          <div style="color:{color(s)};font-weight:800;margin:.7rem 0">{status(s)} · {report["overall_trend"]}</div>
          <div class="muted">{report["summary"]}</div>
        </div>""")
    with c2:
        big=report["biggest"]
        st.html(f"""
        <div class="panel">
          <div class="label">🔥 BIGGEST RISK RIGHT NOW</div>
          <h2>{big["name"]}</h2>
          <div class="muted">{big["summary"]}</div>
          <div style="margin-top:1rem;font-weight:800">👀 Watch: {big["next_risk"]}</div>
        </div>""")

    st.html('<div class="section">Risk by category</div>')
    cats=report["categories"]
    for i in range(0,len(cats),2):
        cols=st.columns(2,gap="large")
        for j,col in enumerate(cols):
            if i+j>=len(cats): break
            x=cats[i+j]; sc=x["score"]
            status_class = "down" if x["data_status"]=="unavailable" else ("partial" if x["data_status"] in ("fallback","official only") else "live")
            status_text = "DATA UNAVAILABLE" if x["data_status"]=="unavailable" else x["data_status"].upper()
            with col:
                st.html(f"""
                <div class="card">
                  <div style="display:flex;justify-content:space-between">
                    <div><b>{x["emoji"]} {x["name"]}</b><br>
                    <span style="color:{color(sc)};font-size:.8rem;font-weight:800">{x["trend"]}</span></div>
                    <div class="cat-score">{sc:.1f}<span class="muted" style="font-size:.7rem"> /10</span></div>
                  </div>
                  <div style="height:7px;background:#252d34;border-radius:99px;margin:.9rem 0;overflow:hidden">
                    <div style="height:100%;width:{sc*10}%;background:{color(sc)}"></div>
                  </div>
                  <div class="{status_class}" style="font-size:.72rem;font-weight:800">{status_text}</div>
                  <div class="muted" style="margin-top:.5rem">{x["summary"]}</div>

                  <div style="margin-top:1rem;padding-top:.85rem;border-top:1px solid #29323b">
                    <div style="margin-bottom:.65rem">
                      <b style="color:#ff8b8b">⬆️ What could make it worse</b><br>
                      <span class="muted">{x["raises_score"]}</span>
                    </div>
                    <div style="margin-bottom:.65rem">
                      <b style="color:#76df9d">⬇️ What could make it better</b><br>
                      <span class="muted">{x["lowers_score"]}</span>
                    </div>
                    <div>
                      <b style="color:#f2d964">👀 What to watch next</b><br>
                      <span class="muted">{x["next_risk"]}</span>
                    </div>
                  </div>
                </div>""")
                with st.expander("Sources"):
                    if x["signals"]:
                        st.markdown("**Fresh signals:**")
                        for art in x["signals"]:
                            st.markdown(f"- [{art['title']}]({art['url']}) — {art['domain']}")
                    else:
                        st.caption("No fresh news feed. Score was not lowered because of missing data.")

    stamp=report["checked_at"]
    if not st.session_state.history or st.session_state.history[-1]["Checked"] != stamp:
        st.session_state.history.append({"Checked":stamp,"Score":s})
        st.session_state.history=st.session_state.history[-50:]

    st.html('<div class="section">Session risk history</div>')
    if len(st.session_state.history)>=2:
        df=pd.DataFrame(st.session_state.history)
        fig=px.line(df,x="Checked",y="Score",markers=True,range_y=[0,10])
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
                          font_color="#dfe5ea",height=300,showlegend=False,
                          margin=dict(l=10,r=10,t=10,b=10))
        st.plotly_chart(fig,use_container_width=True)
    else:
        st.info("History appears after two successful checks.")

    with st.expander("ⓘ Data sources & methodology"):
        st.markdown("""
**Sources**
- **NOAA Climate Prediction Center** — official ENSO/climate signal.
- **FAO Food Price Index** — official global food-price signal.
- **GDELT DOC 2.0** — fresh global news/event discovery.
- **Google News RSS** — fallback news discovery if GDELT fails.

**Important:** a broken/missing feed never counts as “everything is fine.” The app keeps the last known score (or a conservative baseline on the first run) and labels the category **DATA UNAVAILABLE**.

Headlines only make capped adjustments to fixed baselines. Official NOAA/FAO data gets more weight where available. This is a situational-awareness index, not an extinction probability.
        """)
        st.markdown(f"- [NOAA ENSO Discussion]({NOAA})")
        st.markdown(f"- [FAO Food Price Index]({FAO})")
        st.markdown("- [GDELT DOC 2.0](https://api.gdeltproject.org/api/v2/doc/doc)")


@st.fragment(run_every=REFRESH)
def dashboard():
    try:
        with st.spinner("Checking public data…"):
            report=build_report()
        st.session_state.last_report=report
        render(report)
    except Exception as e:
        st.error("A refresh failed. Keeping the last good dashboard instead of guessing.")
        with st.expander("Technical error"): st.code(str(e))
        if st.session_state.last_report: render(st.session_state.last_report)

dashboard()
