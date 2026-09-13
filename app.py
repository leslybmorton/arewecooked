import json
import textwrap
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.express as px
import streamlit as st
from openai import OpenAI


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Are We Cooked? 🌍",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

PACIFIC = ZoneInfo("America/Los_Angeles")
MODEL = "gpt-5.6-luna"


# ============================================================
# STYLES
# ============================================================

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

        .block-container {
            max-width: 1450px;
            padding-top: 2rem;
            padding-bottom: 4rem;
        }

        h1, h2, h3 {
            color: #f4f7f8 !important;
        }

        .eyebrow {
            color: #8f9aa5;
            font-size: .78rem;
            letter-spacing: .16em;
            font-weight: 800;
            margin-bottom: .35rem;
        }

        .hero-title {
            font-size: clamp(2.5rem, 5vw, 4.8rem);
            font-weight: 800;
            letter-spacing: -.045em;
            line-height: .95;
            margin-bottom: .7rem;
        }

        .subtitle {
            color: #b7c0c8;
            font-size: 1.03rem;
            line-height: 1.6;
            max-width: 820px;
            margin-bottom: 1rem;
        }

        .panel {
            background:
                linear-gradient(180deg, rgba(255,255,255,.025), rgba(255,255,255,.01)),
                #12161b;
            border: 1px solid #26303a;
            border-radius: 22px;
            padding: 22px;
            box-shadow: 0 18px 50px rgba(0,0,0,.22);
            height: 100%;
        }

        .metric-card {
            background:
                linear-gradient(180deg, rgba(255,255,255,.025), rgba(255,255,255,.01)),
                #12161b;
            border: 1px solid #26303a;
            border-radius: 20px;
            padding: 18px;
            margin-bottom: 12px;
        }

        .risk-name {
            font-weight: 800;
            font-size: 1.15rem;
            margin-bottom: 4px;
        }

        .risk-score {
            font-size: 2.2rem;
            font-weight: 800;
            letter-spacing: -.03em;
        }

        .muted {
            color: #9aa5b1;
        }

        .status-pill {
            display: inline-block;
            padding: 6px 10px;
            border-radius: 999px;
            font-size: .75rem;
            font-weight: 800;
            letter-spacing: .08em;
            margin-right: 8px;
        }

        .green-pill {
            background: rgba(73,200,120,.14);
            color: #69df96;
            border: 1px solid rgba(73,200,120,.35);
        }

        .yellow-pill {
            background: rgba(232,197,71,.14);
            color: #f2d964;
            border: 1px solid rgba(232,197,71,.35);
        }

        .orange-pill {
            background: rgba(242,159,61,.14);
            color: #ffc16f;
            border: 1px solid rgba(242,159,61,.35);
        }

        .red-pill {
            background: rgba(239,92,92,.14);
            color: #ff7f7f;
            border: 1px solid rgba(239,92,92,.35);
        }

        .big-score {
            font-size: 5.2rem;
            line-height: .9;
            font-weight: 800;
            letter-spacing: -.06em;
            margin-top: .4rem;
        }

        .section-title {
            font-size: 1.8rem;
            font-weight: 800;
            margin-top: 1.6rem;
            margin-bottom: .8rem;
        }

        .mini-label {
            color: #8f9aa5;
            font-size: .72rem;
            letter-spacing: .1em;
            font-weight: 800;
            margin-bottom: .3rem;
        }

        .detail-box {
            background: #0e1216;
            border: 1px solid #242d35;
            border-radius: 14px;
            padding: 12px 14px;
            margin-top: 8px;
        }

        .spotlight {
            border-left: 4px solid #ef5c5c;
        }

        div[data-testid="stExpander"] {
            background: #11161b;
            border: 1px solid #26303a;
            border-radius: 14px;
        }

        .footer-note {
            color: #7f8a95;
            font-size: .82rem;
            line-height: 1.5;
            margin-top: 2rem;
        }

        .refresh-meta {
            color: #8f9aa5;
            font-size: .8rem;
            margin-top: .35rem;
        }

        a {
            color: #7fd1c8 !important;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# HELPERS
# ============================================================

def html(block: str):
    """Render HTML safely without indentation becoming a code block."""
    st.markdown(textwrap.dedent(block).strip(), unsafe_allow_html=True)


def now_pt():
    return datetime.now(PACIFIC)


def score_color(score: float) -> str:
    if score <= 2:
        return "#49c878"
    if score <= 5:
        return "#e8c547"
    if score < 8:
        return "#f29f3d"
    if score < 10:
        return "#ef5c5c"
    return "#111111"


def status_for(score: float):
    if score <= 2:
        return "NORMAL", "green-pill"
    if score <= 5:
        return "ELEVATED", "yellow-pill"
    if score < 8:
        return "SERIOUS", "orange-pill"
    if score < 10:
        return "CRITICAL", "red-pill"
    return "CATASTROPHIC", "red-pill"


# ============================================================
# FALLBACK REPORT
# ============================================================

FALLBACK_REPORT = {
    "report_date": "September 13, 2026",
    "checked_at": "Baseline fallback",
    "overall_score": 6.5,
    "overall_trend": "↗ Worsening",
    "overall_summary": (
        "Global systems are under unusually high, interconnected stress. "
        "A catastrophe is not currently unfolding, but war and energy disruption "
        "have created credible pathways to wider economic and infrastructure problems."
    ),
    "biggest_risk": "Energy",
    "biggest_risk_summary": (
        "Energy-system disruption remains the clearest near-term pathway from "
        "regional conflict into broader global economic stress."
    ),
    "watch_next": "Hormuz shipping, Saudi export capacity, and regional escalation.",
    "categories": [
        {
            "name": "Energy",
            "emoji": "🛢️",
            "score": 8.0,
            "trend": "↑ Worsening quickly",
            "summary": "Major shipping and export-route disruption is putting unusual pressure on energy resilience.",
            "next_risk": "Physical fuel shortages, rationing, industrial cutbacks, and higher transport and food costs.",
            "raises_score": "More export infrastructure is lost or chokepoints remain heavily constrained.",
            "lowers_score": "Export routes reopen, infrastructure is restored, and safe passage becomes reliable.",
            "sources": [],
        },
        {
            "name": "War / Geopolitics",
            "emoji": "⚔️",
            "score": 7.5,
            "trend": "↑ Worsening quickly",
            "summary": "Regional conflict and attacks on strategic infrastructure create elevated escalation risk.",
            "next_risk": "Broader regional war or additional states entering sustained combat.",
            "raises_score": "Direct great-power confrontation, major new combatants, or nuclear escalation.",
            "lowers_score": "Sustained ceasefire activity, negotiations, or meaningful reduction in attacks.",
            "sources": [],
        },
        {
            "name": "Economy",
            "emoji": "💰",
            "score": 6.0,
            "trend": "↗ Worsening",
            "summary": "Energy and geopolitical shocks are raising inflation and uncertainty while financial systems remain functional.",
            "next_risk": "Stagflation, recession, or industrial disruption if energy stress persists.",
            "raises_score": "Credit dysfunction, banking stress, mass industrial shutdowns, or sovereign defaults.",
            "lowers_score": "Energy costs retreat and financial conditions stabilize.",
            "sources": [],
        },
        {
            "name": "Climate",
            "emoji": "🌡️",
            "score": 6.0,
            "trend": "↗ Worsening",
            "summary": "Extreme-weather risk can amplify food, energy, infrastructure, and humanitarian pressures.",
            "next_risk": "Major simultaneous crop-region droughts, floods, or heat waves.",
            "raises_score": "Severe multi-region agricultural or infrastructure impacts.",
            "lowers_score": "Impacts remain limited and major harvest forecasts improve.",
            "sources": [],
        },
        {
            "name": "Food",
            "emoji": "🌾",
            "score": 5.0,
            "trend": "↗ Worsening",
            "summary": "Food systems face cost and logistics pressure, but there is no worldwide physical shortage.",
            "next_risk": "Export restrictions and localized shortages that amplify international prices.",
            "raises_score": "Major export bans, fertilizer shortages, or simultaneous harvest failures.",
            "lowers_score": "Strong harvests, cheaper inputs, and improved logistics.",
            "sources": [],
        },
        {
            "name": "AI",
            "emoji": "🤖",
            "score": 5.0,
            "trend": "↗ Worsening",
            "summary": "Frontier systems are gaining autonomy-relevant capabilities but remain below actual loss-of-control conditions.",
            "next_risk": "Reliable long-horizon autonomy, safeguard circumvention, or faster AI-assisted AI research.",
            "raises_score": "Sustained autonomous operation, real-world control evasion, replication, or rapid AI-R&D acceleration.",
            "lowers_score": "Capability growth slows and robust control methods survive harder evaluations.",
            "sources": [],
        },
        {
            "name": "Infrastructure / Cyber",
            "emoji": "🏗️",
            "score": 4.5,
            "trend": "↗ Worsening",
            "summary": "Regional infrastructure is under pressure while global power, communications, logistics, and payments remain broadly operational.",
            "next_risk": "A cyber-plus-physical cascade across grids, ports, pipelines, telecoms, or payments.",
            "raises_score": "Multi-country grid failures or destructive systemic infrastructure attacks.",
            "lowers_score": "Threat activity falls and failures remain localized.",
            "sources": [],
        },
    ],
    "changes": [
        "Fallback baseline is being shown because a fresh live report was unavailable.",
        "Use Refresh Now after checking your Streamlit API secret and app logs.",
    ],
    "pathways": [
        {
            "label": "De-escalation",
            "icon": "↙️",
            "description": "Key infrastructure recovers and diplomacy reduces disruption.",
            "target": "~5–5.5",
        },
        {
            "label": "Muddling through",
            "icon": "⬇️",
            "description": "Serious tensions continue but core buffers remain functional.",
            "target": "~6–6.5",
        },
        {
            "label": "Further escalation",
            "icon": "↘️",
            "description": "Additional chokepoints or critical systems are disrupted.",
            "target": "~7–7.5",
        },
        {
            "label": "Systemic cascade",
            "icon": "🔴",
            "description": "Energy, food, industry, and financial stress begin reinforcing one another.",
            "target": "8+",
        },
    ],
}


# ============================================================
# STRUCTURED OUTPUT SCHEMA
# ============================================================

SOURCE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "url": {"type": "string"},
    },
    "required": ["title", "url"],
    "additionalProperties": False,
}

CATEGORY_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "emoji": {"type": "string"},
        "score": {"type": "number"},
        "trend": {"type": "string"},
        "summary": {"type": "string"},
        "next_risk": {"type": "string"},
        "raises_score": {"type": "string"},
        "lowers_score": {"type": "string"},
        "sources": {
            "type": "array",
            "items": SOURCE_SCHEMA,
        },
    },
    "required": [
        "name",
        "emoji",
        "score",
        "trend",
        "summary",
        "next_risk",
        "raises_score",
        "lowers_score",
        "sources",
    ],
    "additionalProperties": False,
}

PATHWAY_SCHEMA = {
    "type": "object",
    "properties": {
        "label": {"type": "string"},
        "icon": {"type": "string"},
        "description": {"type": "string"},
        "target": {"type": "string"},
    },
    "required": ["label", "icon", "description", "target"],
    "additionalProperties": False,
}

REPORT_SCHEMA = {
    "type": "object",
    "properties": {
        "report_date": {"type": "string"},
        "checked_at": {"type": "string"},
        "overall_score": {"type": "number"},
        "overall_trend": {"type": "string"},
        "overall_summary": {"type": "string"},
        "biggest_risk": {"type": "string"},
        "biggest_risk_summary": {"type": "string"},
        "watch_next": {"type": "string"},
        "categories": {
            "type": "array",
            "items": CATEGORY_SCHEMA,
        },
        "changes": {
            "type": "array",
            "items": {"type": "string"},
        },
        "pathways": {
            "type": "array",
            "items": PATHWAY_SCHEMA,
        },
    },
    "required": [
        "report_date",
        "checked_at",
        "overall_score",
        "overall_trend",
        "overall_summary",
        "biggest_risk",
        "biggest_risk_summary",
        "watch_next",
        "categories",
        "changes",
        "pathways",
    ],
    "additionalProperties": False,
}


# ============================================================
# LIVE RESEARCH PROMPT
# ============================================================

SYSTEM_INSTRUCTIONS = """
You are the research engine for a public dashboard called "Are We Cooked?",
which measures CURRENT global systemic risk.

You MUST use web search before scoring. Research what is true right now.

The dashboard is NOT a probability of extinction. It measures present systemic
stress, remaining buffers/resilience, trajectory, and how strongly risks are
coupled.

Fixed score meanings:
0-2 = Normal background risk
3-5 = Elevated
6-7 = Serious global stress
8-9 = Critical systemic danger
10 = A global catastrophe is actually underway

Scoring rules:
- Do not increase a score merely because a scary headline appeared.
- Require an observable change in systemic conditions, resilience, or credible
  near-term pathways before materially changing a score.
- Explicitly credit improvements, restored infrastructure, de-escalation,
  replenished buffers, successful negotiations, and improving conditions.
- Distinguish current severity from future possibility.
- Avoid sensationalism.
- If evidence is mixed or uncertain, say so and score conservatively.
- Prefer Reuters, AP, AFP, BBC, major financial publications, official agencies,
  international organizations, peer-reviewed or primary technical sources,
  and first-party AI lab safety/research publications.
- Favor the last 24 hours for fast-moving war, energy, finance, infrastructure,
  and cyber developments. Use authoritative recent sources for climate, food,
  and AI where appropriate.
- Each category should include 1-3 useful real source URLs.

AI-specific rule:
Do not score AI based only on hypothetical future superintelligence. Score
observable current capabilities, deployment, autonomy, control failures,
AI-enabled cyber/bio risk, and AI-assisted AI R&D.

Return EXACTLY these seven categories, in this order:
1. Energy — 🛢️
2. War / Geopolitics — ⚔️
3. Economy — 💰
4. Climate — 🌡️
5. Food — 🌾
6. AI — 🤖
7. Infrastructure / Cyber — 🏗️

For each category:
- score must be between 0 and 10
- trend must be exactly one of:
  "↓ Improving"
  "→ Stable"
  "↗ Worsening"
  "↑ Worsening quickly"
- summary should be 1-2 concise sentences
- next_risk should describe the most plausible next-stage risk, not the
  theatrical worst case
- raises_score and lowers_score must be concrete observable triggers

Overall score:
Do NOT simply average the categories. Consider coupling and cascades.
Normally the overall score should remain below the most severe category unless
several major systems are simultaneously deteriorating.

Changes:
Give 2-5 concise bullets describing what materially changed in the newest data.
If nothing important changed, explicitly say conditions are broadly unchanged.

Pathways:
Return exactly four entries named:
De-escalation
Muddling through
Further escalation
Systemic cascade

The current date/time supplied by the app is authoritative.
"""


# ============================================================
# OPENAI / WEB SEARCH
# ============================================================

def prior_report_summary():
    previous = st.session_state.get("last_good_report")
    if not previous:
        return "No prior live report exists in this browser session."

    prior = {
        "overall_score": previous.get("overall_score"),
        "overall_trend": previous.get("overall_trend"),
        "categories": [
            {
                "name": c.get("name"),
                "score": c.get("score"),
                "trend": c.get("trend"),
            }
            for c in previous.get("categories", [])
        ],
    }
    return json.dumps(prior, ensure_ascii=False)


@st.cache_data(ttl=900, show_spinner=False)
def fetch_live_report():
    if "OPENAI_API_KEY" not in st.secrets:
        raise RuntimeError(
            "OPENAI_API_KEY is missing from Streamlit Secrets."
        )

    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    current = now_pt()

    prompt = f"""
Current Pacific time: {current.strftime("%A, %B %d, %Y at %I:%M %p %Z")}

Research the current global situation and generate a fresh Are We Cooked?
dashboard report.

Prior session baseline, if available:
{prior_report_summary()}

Use web search extensively enough to assess all seven categories. Prioritize
freshness for fast-moving categories. Return only the structured report.
"""

    response = client.responses.create(
        model=MODEL,
        reasoning={"effort": "low"},
        tools=[
            {
                "type": "web_search",
                "search_context_size": "medium",
            }
        ],
        input=[
            {
                "role": "system",
                "content": SYSTEM_INSTRUCTIONS,
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "are_we_cooked_report",
                "strict": True,
                "schema": REPORT_SCHEMA,
            }
        },
    )

    report = json.loads(response.output_text)

    # Basic guardrails in case a model output somehow slips outside bounds.
    report["overall_score"] = max(0, min(10, float(report["overall_score"])))

    for category in report.get("categories", []):
        category["score"] = max(0, min(10, float(category["score"])))

    # Stamp the actual app-side research time too.
    report["checked_at"] = current.strftime("%b %d, %Y · %I:%M %p %Z")

    return report


# ============================================================
# SESSION HISTORY
# ============================================================

if "last_good_report" not in st.session_state:
    st.session_state.last_good_report = None

if "history" not in st.session_state:
    st.session_state.history = []

if "last_report_key" not in st.session_state:
    st.session_state.last_report_key = None


def record_history(report):
    key = report.get("checked_at")

    if not key or key == st.session_state.last_report_key:
        return

    st.session_state.last_report_key = key
    st.session_state.history.append(
        {
            "Checked": key,
            "Score": float(report["overall_score"]),
        }
    )

    # Keep chart tidy inside a single browser session.
    st.session_state.history = st.session_state.history[-40:]


# ============================================================
# SOURCES
# ============================================================

def render_sources(sources):
    if not sources:
        st.caption("No source links were returned for this category.")
        return

    for source in sources:
        title = source.get("title", "Source")
        url = source.get("url", "")

        if url.startswith("http://") or url.startswith("https://"):
            st.markdown(f"- [{title}]({url})")
        else:
            st.markdown(f"- {title}")


# ============================================================
# DASHBOARD RENDERING
# ============================================================

def render_dashboard(report):
    score = float(report["overall_score"])
    status, pill = status_for(score)

    # HEADER
    left, right = st.columns([4.5, 1.6], vertical_alignment="top")

    with left:
        html("""
        <div class="eyebrow">GLOBAL RISK DASHBOARD</div>
        <div class="hero-title">Are We Cooked? 🌍</div>
        <div class="subtitle">
            A sober look at global systemic risk — without turning every scary
            headline into apocalypse.
        </div>
        """)

    with right:
        html(f"""
        <div class="panel" style="padding:14px 16px;">
            <div class="mini-label">LIVE REPORT</div>
            <div style="font-weight:800;">{report.get("report_date", "")}</div>
            <div class="refresh-meta">
                Last researched:<br>
                {report.get("checked_at", "Unknown")}
            </div>
        </div>
        """)

    # REFRESH CONTROLS
    refresh_col, note_col = st.columns([1.2, 5], vertical_alignment="center")

    with refresh_col:
        if st.button(
            "🔄 Refresh Now",
            use_container_width=True,
            type="primary",
            key="manual_refresh",
        ):
            fetch_live_report.clear()
            st.session_state.force_refresh = True
            st.rerun()

    with note_col:
        st.caption(
            "The dashboard researches fresh data automatically every 15 minutes "
            "while this page is open. Refresh Now forces a new research run."
        )

    # HERO
    c1, c2 = st.columns([1.7, 1], gap="large")

    with c1:
        html(f"""
        <div class="panel">
            <div class="mini-label">OVERALL GLOBAL RISK</div>

            <div class="big-score">
                {score:.1f}
                <span style="font-size:1.4rem;color:#8f9aa5;"> / 10</span>
            </div>

            <div style="margin:.8rem 0 1rem 0;">
                <span class="status-pill {pill}">{status}</span>
                <span style="color:{score_color(score)};font-weight:800;">
                    {report.get("overall_trend", "→ Stable")}
                </span>
            </div>

            <div style="color:#c4ccd3;line-height:1.65;">
                {report.get("overall_summary", "")}
            </div>
        </div>
        """)

    with c2:
        html(f"""
        <div class="panel spotlight">
            <div class="mini-label">🔥 BIGGEST RISK RIGHT NOW</div>

            <h2 style="margin:.35rem 0 .6rem 0;">
                {report.get("biggest_risk", "Unknown")}
            </h2>

            <div style="color:#c4ccd3;line-height:1.6;">
                {report.get("biggest_risk_summary", "")}
            </div>

            <div style="margin-top:1rem;font-weight:800;">
                👀 Watch: {report.get("watch_next", "")}
            </div>
        </div>
        """)

    # CATEGORY CARDS
    html('<div class="section-title">Risk by category</div>')

    categories = report.get("categories", [])

    for i in range(0, len(categories), 2):
        cols = st.columns(2, gap="large")

        for j, col in enumerate(cols):
            idx = i + j

            if idx >= len(categories):
                break

            item = categories[idx]
            item_score = float(item["score"])

            with col:
                html(f"""
                <div class="metric-card">
                    <div style="
                        display:flex;
                        justify-content:space-between;
                        gap:18px;
                        align-items:flex-start;
                    ">
                        <div>
                            <div class="risk-name">
                                {item.get("emoji","")} {item.get("name","")}
                            </div>

                            <div style="
                                color:{score_color(item_score)};
                                font-weight:800;
                                font-size:.84rem;
                            ">
                                {item.get("trend","→ Stable")}
                            </div>
                        </div>

                        <div style="text-align:right;">
                            <div class="risk-score">{item_score:.1f}</div>
                            <div class="muted" style="font-size:.74rem;">/ 10</div>
                        </div>
                    </div>

                    <div style="margin:.8rem 0;">
                        <div style="
                            height:8px;
                            background:#252d34;
                            border-radius:999px;
                            overflow:hidden;
                        ">
                            <div style="
                                width:{item_score * 10}%;
                                height:100%;
                                background:{score_color(item_score)};
                            "></div>
                        </div>
                    </div>

                    <div style="
                        color:#c5cdd4;
                        line-height:1.55;
                        font-size:.93rem;
                    ">
                        {item.get("summary","")}
                    </div>
                </div>
                """)

                with st.expander("Next risk + escalation triggers + sources"):
                    st.markdown(
                        f"**Next plausible risk:** {item.get('next_risk','')}"
                    )
                    st.markdown(
                        f"**⬆️ Raises score:** {item.get('raises_score','')}"
                    )
                    st.markdown(
                        f"**⬇️ Lowers score:** {item.get('lowers_score','')}"
                    )
                    st.markdown("**Sources:**")
                    render_sources(item.get("sources", []))

    # WHAT CHANGED
    html('<div class="section-title">What changed in the latest check?</div>')

    changes = report.get("changes", [])
    if changes:
        for change in changes:
            st.markdown(f"- {change}")
    else:
        st.markdown("- No material change was identified.")

    # HISTORY + PATHWAYS
    html('<div class="section-title">Where this could go next</div>')

    left, right = st.columns([1.45, 1], gap="large")

    with left:
        html('<div class="mini-label">📈 SESSION RISK HISTORY</div>')

        history_rows = st.session_state.history

        if len(history_rows) >= 2:
            history_df = pd.DataFrame(history_rows)

            fig = px.line(
                history_df,
                x="Checked",
                y="Score",
                markers=True,
                range_y=[0, 10],
            )

            fig.update_traces(
                line=dict(width=4),
                marker=dict(size=9),
            )

            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#dfe5ea",
                margin=dict(l=10, r=10, t=10, b=10),
                height=330,
                xaxis=dict(showgrid=False, title=None, tickangle=-20),
                yaxis=dict(gridcolor="#26303a", title=None, dtick=2),
                showlegend=False,
            )

            st.plotly_chart(fig, use_container_width=True)

            st.caption(
                "This chart records successful live checks in the current "
                "Streamlit browser session."
            )
        else:
            st.info(
                "History will start plotting after the dashboard has completed "
                "at least two successful live research checks."
            )

    with right:
        html('<div class="mini-label">🧭 MOST PLAUSIBLE NEXT PATHS</div>')

        for pathway in report.get("pathways", []):
            html(f"""
            <div class="detail-box">
                <div style="
                    display:flex;
                    justify-content:space-between;
                    gap:14px;
                    align-items:center;
                ">
                    <div>
                        <div style="font-weight:800;">
                            {pathway.get("icon","")} {pathway.get("label","")}
                        </div>

                        <div class="muted" style="
                            font-size:.82rem;
                            margin-top:3px;
                        ">
                            {pathway.get("description","")}
                        </div>
                    </div>

                    <div style="font-size:1.15rem;font-weight:800;">
                        {pathway.get("target","")}
                    </div>
                </div>
            </div>
            """)

    # SCORE KEY
    html('<div class="section-title">How to read the meter</div>')

    k1, k2, k3, k4, k5 = st.columns(5)

    key_items = [
        (k1, "0–2", "Normal", "#49c878"),
        (k2, "3–5", "Elevated", "#e8c547"),
        (k3, "6–7", "Serious", "#f29f3d"),
        (k4, "8–9", "Critical", "#ef5c5c"),
        (k5, "10", "Catastrophic", "#111111"),
    ]

    for col, label, desc, color in key_items:
        with col:
            html(f"""
            <div class="panel" style="padding:14px;">
                <div style="
                    height:6px;
                    background:{color};
                    border-radius:999px;
                    margin-bottom:10px;
                "></div>

                <div style="font-size:1.3rem;font-weight:800;">
                    {label}
                </div>

                <div class="muted" style="font-size:.8rem;">
                    {desc}
                </div>
            </div>
            """)

    html("""
    <div class="footer-note">
        <strong>Important:</strong>
        This is an analytical index, not a probability of human extinction.
        Scores reflect current systemic stress, resilience, trajectory, and
        interactions between risks. A frightening headline by itself should
        not move the meter unless it changes underlying conditions.
    </div>
    """)


# ============================================================
# LIVE AUTO-REFRESH
# ============================================================

@st.fragment(run_every="15m")
def live_dashboard():
    try:
        with st.spinner("Researching the latest global conditions…"):
            report = fetch_live_report()

        st.session_state.last_good_report = report
        record_history(report)

        render_dashboard(report)

    except Exception as exc:
        previous = st.session_state.last_good_report

        if previous:
            st.warning(
                "The latest research refresh failed, so the dashboard is "
                "showing the last successful live report."
            )
            with st.expander("Technical error"):
                st.code(str(exc))

            render_dashboard(previous)

        else:
            st.error(
                "The live research check failed. I’m showing the built-in "
                "baseline so the dashboard still works."
            )
            with st.expander("Technical error"):
                st.code(str(exc))

            render_dashboard(FALLBACK_REPORT)


live_dashboard()
