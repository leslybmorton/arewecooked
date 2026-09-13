import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from bs4 import BeautifulSoup


st.set_page_config(
    page_title="Are We Cooked? 🌍",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

PACIFIC = ZoneInfo("America/Los_Angeles")
REFRESH_EVERY = "15m"

HEADERS = {
    "User-Agent": "Mozilla/5.0 AreWeCookedDashboard/1.0"
}

GDELT_ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"
NOAA_ENSO_URL = (
    "https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/"
    "enso_advisory/ensodisc.shtml"
)

st.markdown(
    """
    <style>
        .stApp {
            background:
                radial-gradient(circle at 15% 0%, rgba(127,209,200,.08), transparent 28%),
                radial-gradient(circle at 100% 15%, rgba(242,159,61,.06), transparent 24%),
                #0b0d10;
            color: #f4f7f8;
        }
        .block-container { max-width: 1450px; padding-top: 1.6rem; padding-bottom: 4rem; }
        .eyebrow { color:#8f9aa5;font-size:.78rem;letter-spacing:.16em;font-weight:800;margin-bottom:.35rem; }
        .hero-title { font-size:clamp(2.5rem,5vw,4.8rem);font-weight:800;letter-spacing:-.045em;line-height:.95;margin-bottom:.7rem; }
        .subtitle { color:#b7c0c8;font-size:1.03rem;line-height:1.6;max-width:820px;margin-bottom:1rem; }
        .panel {
            background:linear-gradient(180deg,rgba(255,255,255,.025),rgba(255,255,255,.01)),#12161b;
            border:1px solid #26303a;border-radius:22px;padding:22px;box-shadow:0 18px 50px rgba(0,0,0,.22);height:100%;
        }
        .metric-card {
            background:linear-gradient(180deg,rgba(255,255,255,.025),rgba(255,255,255,.01)),#12161b;
            border:1px solid #26303a;border-radius:20px;padding:18px;margin-bottom:12px;
        }
        .risk-name { font-weight:800;font-size:1.15rem;margin-bottom:4px; }
        .risk-score { font-size:2.2rem;font-weight:800;letter-spacing:-.03em; }
        .muted { color:#9aa5b1; }
        .status-pill { display:inline-block;padding:6px 10px;border-radius:999px;font-size:.75rem;font-weight:800;letter-spacing:.08em;margin-right:8px; }
        .green-pill { background:rgba(73,200,120,.14);color:#69df96;border:1px solid rgba(73,200,120,.35); }
        .yellow-pill { background:rgba(232,197,71,.14);color:#f2d964;border:1px solid rgba(232,197,71,.35); }
        .orange-pill { background:rgba(242,159,61,.14);color:#ffc16f;border:1px solid rgba(242,159,61,.35); }
        .red-pill { background:rgba(239,92,92,.14);color:#ff7f7f;border:1px solid rgba(239,92,92,.35); }
        .big-score { font-size:5.2rem;line-height:.9;font-weight:800;letter-spacing:-.06em;margin-top:.4rem; }
        .section-title { font-size:1.8rem;font-weight:800;margin-top:1.6rem;margin-bottom:.8rem; }
        .mini-label { color:#8f9aa5;font-size:.72rem;letter-spacing:.1em;font-weight:800;margin-bottom:.3rem; }
        .spotlight { border-left:4px solid #ef5c5c; }
        .refresh-meta { color:#8f9aa5;font-size:.8rem;margin-top:.35rem; }
        a { color:#7fd1c8 !important; }
    </style>
    """,
    unsafe_allow_html=True,
)


def now_pt():
    return datetime.now(PACIFIC)


def clamp(v, low=0.0, high=10.0):
    return max(low, min(high, v))


def score_color(score):
    if score <= 2: return "#49c878"
    if score <= 5: return "#e8c547"
    if score < 8: return "#f29f3d"
    return "#ef5c5c"


def status_for(score):
    if score <= 2: return "NORMAL", "green-pill"
    if score <= 5: return "ELEVATED", "yellow-pill"
    if score < 8: return "SERIOUS", "orange-pill"
    return "CRITICAL", "red-pill"


def trend_for(current, previous):
    if previous is None: return "→ Stable"
    d = current - previous
    if d <= -0.5: return "↓ Improving"
    if d >= 1.0: return "↑ Worsening quickly"
    if d >= 0.35: return "↗ Worsening"
    return "→ Stable"


def clean_text(value):
    return re.sub(r"\s+", " ", value or "").strip()


CATEGORY_CONFIG = {
    "Energy": {
        "emoji": "🛢️",
        "query": '(oil OR crude OR LNG OR "natural gas" OR pipeline OR refinery OR "Strait of Hormuz" OR "Bab el-Mandeb") (outage OR attack OR disruption OR shortage OR shutdown OR blockade OR sanctions)',
        "base": 4.3,
        "severe": ["blockade","shutdown","shortage","rationing","pipeline attack","refinery attack","hormuz","bab el-mandeb"],
        "next": "A sustained supply or shipping disruption that creates physical shortages or industrial cutbacks.",
        "up": "Confirmed loss of major export capacity, chokepoint closure, rationing, or broad refinery/pipeline outages.",
        "down": "Restored export capacity, reliable shipping, repaired infrastructure, and falling disruption volume.",
    },
    "War / Geopolitics": {
        "emoji": "⚔️",
        "query": '(war OR missile OR drone OR invasion OR ceasefire OR airstrike OR mobilization OR "military attack") (Iran OR Israel OR Ukraine OR Russia OR Taiwan OR China OR NATO OR Gulf)',
        "base": 5.0,
        "severe": ["nuclear","mobilization","invasion","direct attack","missile barrage","regional war","nato","strait"],
        "next": "A wider state-on-state escalation, new combatant, or sustained attacks on strategic infrastructure.",
        "up": "New major combatants, direct great-power clashes, large mobilization, nuclear escalation, or attacks spreading across regions.",
        "down": "Durable ceasefires, successful negotiations, demobilization, or sustained decline in attacks.",
    },
    "Economy": {
        "emoji": "💰",
        "query": '("financial crisis" OR recession OR inflation OR default OR bank failure OR "credit stress" OR layoffs OR "market crash" OR stagflation)',
        "base": 3.8,
        "severe": ["bank failure","default","market crash","credit freeze","stagflation","recession","mass layoffs"],
        "next": "Persistent inflation plus weaker growth, credit stress, or industrial disruption.",
        "up": "Bank failures, frozen credit markets, sovereign defaults, deep recession, or broad industrial shutdowns.",
        "down": "Falling inflation pressure, improving growth, calmer credit conditions, and fewer crisis signals.",
    },
    "Climate": {
        "emoji": "🌡️",
        "query": '("extreme heat" OR drought OR flood OR wildfire OR hurricane OR cyclone OR "record temperature") (emergency OR damage OR evacuation OR crop OR infrastructure)',
        "base": 3.8,
        "severe": ["record temperature","emergency","evacuation","crop damage","catastrophic flood","megadrought"],
        "next": "Simultaneous severe weather impacts across major food, energy, or population centers.",
        "up": "Multiple major regions experience damaging heat, flood, fire, drought, or storm impacts at the same time.",
        "down": "Hazards remain localized, seasonal outlooks moderate, and crop/infrastructure impacts improve.",
    },
    "Food": {
        "emoji": "🌾",
        "query": '("food shortage" OR famine OR crop failure OR fertilizer shortage OR "food prices" OR wheat OR corn OR rice) (shortage OR drought OR flood OR export ban OR disruption OR crisis)',
        "base": 3.6,
        "severe": ["famine","export ban","crop failure","fertilizer shortage","food shortage","rationing"],
        "next": "Export restrictions or multiple harvest shocks that push localized shortages into broader price stress.",
        "up": "Major export bans, widespread crop failure, fertilizer shortages, or physical food shortages across multiple regions.",
        "down": "Strong harvests, lower fertilizer/energy costs, reopened trade routes, and fewer shortage reports.",
    },
    "AI": {
        "emoji": "🤖",
        "query": '("artificial intelligence" OR AI) (autonomous OR cyberattack OR biosecurity OR safeguard OR jailbreak OR "AI safety" OR "model capability" OR "self replication" OR agentic)',
        "base": 3.8,
        "severe": ["self replication","autonomous cyber","biosecurity","safeguard failure","control failure","agentic","jailbreak"],
        "next": "More reliable autonomous operation, consequential cyber use, safeguard bypass, or accelerated AI-assisted R&D.",
        "up": "Demonstrated long-horizon autonomy, real-world control evasion, replication/resource acquisition, or major AI-enabled cyber/bio incidents.",
        "down": "Capability growth slows, stronger controls hold under evaluation, and serious misuse incidents decline.",
    },
    "Infrastructure / Cyber": {
        "emoji": "🏗️",
        "query": '("power grid" OR blackout OR cyberattack OR ransomware OR telecom OR port OR pipeline OR "critical infrastructure") (attack OR outage OR disruption OR shutdown OR failure)',
        "base": 3.5,
        "severe": ["blackout","grid failure","ransomware","critical infrastructure","port shutdown","telecom outage","pipeline shutdown"],
        "next": "A cyber-plus-physical cascade affecting grids, ports, telecoms, pipelines, or payments across multiple regions.",
        "up": "Multi-country grid failures, payment disruption, destructive cyberattacks, or simultaneous infrastructure outages.",
        "down": "Systems recover quickly, attacks remain localized, and incident volume returns toward baseline.",
    },
}


@st.cache_data(ttl=900, show_spinner=False)
def fetch_gdelt(query):
    params = {
        "query": query,
        "mode": "artlist",
        "format": "json",
        "timespan": "24h",
        "maxrecords": 30,
        "sort": "datedesc",
    }
    r = requests.get(
        GDELT_ENDPOINT,
        params=params,
        headers=HEADERS,
        timeout=6,
    )
    r.raise_for_status()
    data = r.json()
    rows = []
    for a in data.get("articles", []):
        rows.append({
            "title": clean_text(a.get("title")),
            "url": a.get("url", ""),
            "domain": a.get("domain", ""),
        })
    return rows


@st.cache_data(ttl=21600, show_spinner=False)
def fetch_noaa():
    try:
        r = requests.get(NOAA_ENSO_URL, headers=HEADERS, timeout=6)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        text = clean_text(soup.get_text(" ")).lower()

        if "very strong el niño" in text:
            return 6.0, "NOAA reports a very strong El Niño signal."
        if "el niño advisory" in text:
            return 5.0, "NOAA has an El Niño Advisory in effect."
        if "la niña advisory" in text:
            return 4.5, "NOAA has a La Niña Advisory in effect."
        if "enso-neutral" in text:
            return 3.0, "NOAA indicates ENSO-neutral conditions."

        return 4.0, "NOAA ENSO outlook available."
    except Exception:
        return 4.0, "NOAA ENSO feed was unavailable during this check."


def category_from_articles(name, cfg, articles, prev=None):
    title_blob = " ".join(a["title"].lower() for a in articles)
    hits = sum(1 for word in cfg["severe"] if word.lower() in title_blob)

    count_adj = 0.0
    if len(articles) >= 25:
        count_adj = 1.0
    elif len(articles) >= 15:
        count_adj = 0.5
    elif len(articles) <= 3:
        count_adj = -0.5

    hit_adj = min(1.5, hits * 0.3)
    score = round(clamp(cfg["base"] + count_adj + hit_adj) * 2) / 2

    summary = (
        f"{len(articles)} fresh matching reports in the latest GDELT sample; "
        f"{hits} high-severity signal terms detected."
    )
    if articles:
        summary += f" Latest signal: {articles[0]['title']}"

    return {
        "name": name,
        "emoji": cfg["emoji"],
        "score": score,
        "trend": trend_for(score, prev),
        "summary": summary,
        "next_risk": cfg["next"],
        "raises_score": cfg["up"],
        "lowers_score": cfg["down"],
        "signals": articles[:5],
    }


def build_report():
    previous = {}
    if st.session_state.get("last_report"):
        previous = {
            c["name"]: c["score"]
            for c in st.session_state.last_report.get("categories", [])
        }

    fetched = {}

    # Run all category calls at the same time.
    with ThreadPoolExecutor(max_workers=7) as pool:
        future_map = {
            pool.submit(fetch_gdelt, cfg["query"]): name
            for name, cfg in CATEGORY_CONFIG.items()
        }

        for future in as_completed(future_map):
            name = future_map[future]
            try:
                fetched[name] = future.result()
            except Exception:
                fetched[name] = []

    categories = []
    for name, cfg in CATEGORY_CONFIG.items():
        categories.append(
            category_from_articles(
                name,
                cfg,
                fetched.get(name, []),
                previous.get(name),
            )
        )

    # Add NOAA climate context without blocking the rest of the dashboard.
    climate = next(c for c in categories if c["name"] == "Climate")
    noaa_score, noaa_text = fetch_noaa()
    climate["score"] = round(((climate["score"] * 0.6) + (noaa_score * 0.4)) * 2) / 2
    climate["trend"] = trend_for(climate["score"], previous.get("Climate"))
    climate["summary"] = f"{noaa_text} {climate['summary']}"

    scores = {c["name"]: c["score"] for c in categories}
    weights = {
        "Energy": 1.25,
        "War / Geopolitics": 1.25,
        "Economy": 1.0,
        "Climate": 0.9,
        "Food": 1.0,
        "AI": 0.85,
        "Infrastructure / Cyber": 1.0,
    }

    overall = sum(scores[k] * weights[k] for k in scores) / sum(weights.values())

    severe = sum(1 for s in scores.values() if s >= 7)
    elevated = sum(1 for s in scores.values() if s >= 5.5)

    if severe >= 2:
        overall += 0.5
    if severe >= 3:
        overall += 0.5
    if elevated >= 5:
        overall += 0.35

    overall = round(clamp(overall) * 2) / 2

    prev_overall = None
    if st.session_state.get("last_report"):
        prev_overall = st.session_state.last_report.get("overall_score")

    biggest = max(categories, key=lambda x: x["score"])
    now = now_pt()

    return {
        "report_date": now.strftime("%B %d, %Y"),
        "checked_at": now.strftime("%b %d, %Y · %I:%M %p %Z"),
        "overall_score": overall,
        "overall_trend": trend_for(overall, prev_overall),
        "overall_summary": (
            f"The free public-data index currently reads {overall:.1f}/10. "
            f"{severe} categories are at 7+ and {elevated} are at 5.5+. "
            "Headline effects are capped so one news cycle cannot dominate the meter."
        ),
        "biggest_risk": biggest["name"],
        "biggest_risk_summary": biggest["summary"],
        "watch_next": biggest["next_risk"],
        "categories": categories,
    }


if "last_report" not in st.session_state:
    st.session_state.last_report = None

if "history" not in st.session_state:
    st.session_state.history = []


def add_history(report):
    stamp = report["checked_at"]
    if st.session_state.history and st.session_state.history[-1]["Checked"] == stamp:
        return
    st.session_state.history.append({"Checked": stamp, "Score": report["overall_score"]})
    st.session_state.history = st.session_state.history[-50:]


def render_dashboard(report):
    score = float(report["overall_score"])
    status, pill = status_for(score)

    left, right = st.columns([4.5, 1.6], vertical_alignment="top")

    with left:
        st.html("""
        <div class="eyebrow">GLOBAL RISK DASHBOARD</div>
        <div class="hero-title">Are We Cooked? 🌍</div>
        <div class="subtitle">
            A rules-based look at current global systemic risk — using free public data, not paid AI calls.
        </div>
        """)

    with right:
        st.html(f"""
        <div class="panel" style="padding:14px 16px;">
            <div class="mini-label">LIVE REPORT</div>
            <div style="font-weight:800;">{report["report_date"]}</div>
            <div class="refresh-meta">Last checked:<br>{report["checked_at"]}</div>
        </div>
        """)

    refresh_col, note_col = st.columns([1.2, 5], vertical_alignment="center")

    with refresh_col:
        if st.button("🔄 Refresh Now", use_container_width=True, type="primary"):
            fetch_gdelt.clear()
            fetch_noaa.clear()
            st.rerun()

    with note_col:
        st.caption("Checks free public data every 15 minutes while this page is open.")

    c1, c2 = st.columns([1.7, 1], gap="large")

    with c1:
        st.html(f"""
        <div class="panel">
            <div class="mini-label">OVERALL GLOBAL RISK</div>
            <div class="big-score">
                {score:.1f}
                <span style="font-size:1.4rem;color:#8f9aa5;"> / 10</span>
            </div>
            <div style="margin:.8rem 0 1rem 0;">
                <span class="status-pill {pill}">{status}</span>
                <span style="color:{score_color(score)};font-weight:800;">{report["overall_trend"]}</span>
            </div>
            <div style="color:#c4ccd3;line-height:1.65;">{report["overall_summary"]}</div>
        </div>
        """)

    with c2:
        st.html(f"""
        <div class="panel spotlight">
            <div class="mini-label">🔥 BIGGEST RISK RIGHT NOW</div>
            <h2 style="margin:.35rem 0 .6rem 0;">{report["biggest_risk"]}</h2>
            <div style="color:#c4ccd3;line-height:1.6;">{report["biggest_risk_summary"]}</div>
            <div style="margin-top:1rem;font-weight:800;">👀 Watch: {report["watch_next"]}</div>
        </div>
        """)

    st.html('<div class="section-title">Risk by category</div>')

    categories = report["categories"]

    for i in range(0, len(categories), 2):
        cols = st.columns(2, gap="large")

        for j, col in enumerate(cols):
            idx = i + j
            if idx >= len(categories):
                break

            item = categories[idx]
            item_score = float(item["score"])

            with col:
                st.html(f"""
                <div class="metric-card">
                    <div style="display:flex;justify-content:space-between;gap:18px;align-items:flex-start;">
                        <div>
                            <div class="risk-name">{item["emoji"]} {item["name"]}</div>
                            <div style="color:{score_color(item_score)};font-weight:800;font-size:.84rem;">
                                {item["trend"]}
                            </div>
                        </div>
                        <div style="text-align:right;">
                            <div class="risk-score">{item_score:.1f}</div>
                            <div class="muted" style="font-size:.74rem;">/ 10</div>
                        </div>
                    </div>

                    <div style="margin:.8rem 0;">
                        <div style="height:8px;background:#252d34;border-radius:999px;overflow:hidden;">
                            <div style="width:{item_score*10}%;height:100%;background:{score_color(item_score)};"></div>
                        </div>
                    </div>

                    <div style="color:#c5cdd4;line-height:1.55;font-size:.93rem;">
                        {item["summary"]}
                    </div>
                </div>
                """)

                with st.expander("Why this score + live signals"):
                    st.markdown(f"**Next plausible risk:** {item['next_risk']}")
                    st.markdown(f"**⬆️ Raises score:** {item['raises_score']}")
                    st.markdown(f"**⬇️ Lowers score:** {item['lowers_score']}")

                    if item["signals"]:
                        st.markdown("**Recent signals:**")
                        for a in item["signals"][:5]:
                            if a["url"]:
                                st.markdown(f"- [{a['title']}]({a['url']})  \n  `{a['domain']}`")
                    else:
                        st.caption("No fresh GDELT article links were returned for this check.")

    st.html('<div class="section-title">Session risk history</div>')

    if len(st.session_state.history) >= 2:
        df = pd.DataFrame(st.session_state.history)
        fig = px.line(df, x="Checked", y="Score", markers=True, range_y=[0, 10])
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="#dfe5ea",
            margin=dict(l=10, r=10, t=10, b=10),
            height=330,
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("The history chart will appear after at least two successful checks.")

    with st.expander("ⓘ Data sources & scoring methodology"):
        st.markdown("""
**Live/public sources**

- **GDELT Project — DOC 2.0:** global online-news metadata and fresh article signals.
- **NOAA Climate Prediction Center:** official ENSO diagnostic discussion/outlook.

**How scoring works**

Each category begins with a fixed baseline. Recent GDELT article counts and selected
high-severity signal terms create capped adjustments. Climate also blends NOAA's
ENSO outlook.

The overall score combines all seven categories and adds a small coupling adjustment
when several systems become severe at the same time.

This is a situational-awareness index, not a probability of extinction.
        """)
        st.markdown("- [GDELT DOC 2.0](https://api.gdeltproject.org/api/v2/doc/doc)")
        st.markdown(f"- [NOAA ENSO Discussion]({NOAA_ENSO_URL})")


@st.fragment(run_every=REFRESH_EVERY)
def live_dashboard():
    try:
        with st.spinner("Checking free public data sources…"):
            report = build_report()

        st.session_state.last_report = report
        add_history(report)
        render_dashboard(report)

    except Exception as exc:
        st.error("The public-data refresh failed.")
        with st.expander("Technical error"):
            st.code(str(exc))

        if st.session_state.last_report:
            render_dashboard(st.session_state.last_report)


live_dashboard()
