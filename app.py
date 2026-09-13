
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date

st.set_page_config(
    page_title="Are We Cooked? 🌍",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------
# THEME / STYLES
# ---------------------------
st.markdown("""
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
        max-width: 780px;
        margin-bottom: 1.3rem;
    }

    .panel {
        background: linear-gradient(180deg, rgba(255,255,255,.025), rgba(255,255,255,.01)), #12161b;
        border: 1px solid #26303a;
        border-radius: 22px;
        padding: 22px;
        box-shadow: 0 18px 50px rgba(0,0,0,.22);
        height: 100%;
    }

    .metric-card {
        background: linear-gradient(180deg, rgba(255,255,255,.025), rgba(255,255,255,.01)), #12161b;
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

    .green-pill { background: rgba(73,200,120,.14); color: #69df96; border: 1px solid rgba(73,200,120,.35);}
    .yellow-pill { background: rgba(232,197,71,.14); color: #f2d964; border: 1px solid rgba(232,197,71,.35);}
    .orange-pill { background: rgba(242,159,61,.14); color: #ffc16f; border: 1px solid rgba(242,159,61,.35);}
    .red-pill { background: rgba(239,92,92,.14); color: #ff7f7f; border: 1px solid rgba(239,92,92,.35);}

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
        margin-top: 1.5rem;
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

    .stProgress > div > div > div > div {
        border-radius: 999px;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------
# DATA
# ---------------------------
AS_OF = "September 13, 2026"

OVERALL_SCORE = 6.5
OVERALL_STATUS = "SERIOUS"
OVERALL_TREND = "↗ Worsening"

OVERALL_SUMMARY = (
    "Global systems are under unusually high, interconnected stress. "
    "A catastrophe is not currently unfolding, but war and energy disruption have created "
    "credible pathways to wider economic and infrastructure problems."
)

categories = [
    {
        "emoji": "🛢️", "name": "Energy", "score": 8.0, "trend": "↑ Worsening quickly",
        "summary": "Hormuz shipping is severely disrupted while Saudi bypass capacity is impaired, reducing the system's ability to reroute lost exports.",
        "next": "Physical fuel shortages, rationing in vulnerable markets, industrial cutbacks and higher transport and food costs.",
        "up": "Pipeline stays offline into the inventory window; Bab el-Mandeb closes substantially; more Gulf export infrastructure is lost.",
        "down": "East-West pipeline restored; meaningful Hormuz shipping resumes; negotiated safe passage holds."
    },
    {
        "emoji": "⚔️", "name": "War / Geopolitics", "score": 7.5, "trend": "↑ Worsening quickly",
        "summary": "The Iran conflict has expanded into attacks on shipping and regional infrastructure while the Russia–Ukraine war remains active.",
        "next": "Broader regional war, additional states entering combat, or sustained attacks on critical infrastructure.",
        "up": "Major Gulf state enters sustained combat; direct great-power confrontation; nuclear escalation.",
        "down": "Shipping guarantees, meaningful ceasefire activity, or sustained reduction in attacks."
    },
    {
        "emoji": "💰", "name": "Economy", "score": 6.0, "trend": "↗ Worsening",
        "summary": "The energy shock is pushing inflation and uncertainty higher, but banks, credit, payments and trade are still functioning.",
        "next": "Stagflation or recession if expensive energy persists and physical shortages begin suppressing production.",
        "up": "Credit dysfunction, major bank stress, industrial shutdowns, unemployment shock or sovereign defaults.",
        "down": "Energy costs retreat, inflation expectations stabilize and financial conditions normalize."
    },
    {
        "emoji": "🌡️", "name": "Climate", "score": 6.0, "trend": "↗ Worsening",
        "summary": "Extreme-weather risk remains elevated and can amplify food, energy and humanitarian stresses already in motion.",
        "next": "Simultaneous crop-region droughts, floods or heat waves while energy and shipping buffers are already strained.",
        "up": "Confirmed severe breadbasket impacts or major infrastructure-disrupting weather across multiple regions.",
        "down": "Impacts remain geographically limited and harvest forecasts improve."
    },
    {
        "emoji": "🌾", "name": "Food", "score": 5.0, "trend": "↗ Worsening",
        "summary": "Food prices and agricultural supply chains face pressure from energy, transport, war and weather, but there is no worldwide physical shortage.",
        "next": "Export restrictions and localized shortages that amplify prices elsewhere.",
        "up": "Major export bans, fertilizer shortages, simultaneous harvest failures or widespread physical shortages.",
        "down": "Strong harvests, cheaper fertilizer and energy, and improved Black Sea logistics."
    },
    {
        "emoji": "🤖", "name": "AI", "score": 5.0, "trend": "↗ Worsening",
        "summary": "Frontier systems are gaining autonomy-relevant capabilities, but current systems still fall short of an actual loss-of-control scenario.",
        "next": "Reliable long-horizon autonomy, safeguard circumvention or materially faster AI-assisted frontier research.",
        "up": "Sustained autonomous operation, real-world safeguard evasion, replication or resource acquisition, or rapid AI-R&D acceleration.",
        "down": "Capability growth slows and increasingly strong control methods remain robust under harder evaluations."
    },
    {
        "emoji": "🏗️", "name": "Infrastructure / Cyber", "score": 4.5, "trend": "↗ Worsening",
        "summary": "Important regional infrastructure is being attacked, but global power, communications, logistics and payment systems remain broadly operational.",
        "next": "A cyber-plus-physical cascade affecting ports, grids, pipelines, telecoms or payments across multiple countries.",
        "up": "Multi-country grid failures, major payment disruption or destructive critical-infrastructure attacks.",
        "down": "Threat activity falls, vulnerabilities are patched and wars do not spill into systemic civilian infrastructure."
    },
]

history = pd.DataFrame({
    "Date": ["Aug 10", "Aug 20", "Aug 30", "Sep 4", "Sep 8", "Sep 11", "Sep 13"],
    "Score": [4.6, 4.9, 5.2, 5.5, 5.9, 6.2, 6.5]
})

changes = [
    "Energy remains the highest-risk category. The issue is no longer only Hormuz; it is the loss of redundancy if bypass routes remain impaired.",
    "War risk is elevated because multiple theaters and maritime chokepoints are interacting, but this is still below direct great-power war or nuclear-use thresholds.",
    "No category is currently at 9–10. Global financial, communications, food-distribution and power systems continue functioning.",
    "This dashboard tracks both escalation and de-escalation triggers so the score can move down as well as up."
]

pathways = [
    ("↙️", "De-escalation", "Pipeline repaired + shipping improves + diplomacy holds", "~5–5.5"),
    ("⬇️", "Muddling through", "Conflict persists but key buffers remain functional", "~6–6.5"),
    ("↘️", "Further escalation", "More chokepoints or Gulf infrastructure are disrupted", "~7–7.5"),
    ("🔴", "Systemic cascade", "Energy shortages feed industry, food and financial stress", "8+"),
]

# ---------------------------
# HELPERS
# ---------------------------
def score_color(score):
    if score <= 2:
        return "#49c878"
    if score <= 5:
        return "#e8c547"
    if score < 8:
        return "#f29f3d"
    if score < 10:
        return "#ef5c5c"
    return "#111111"

def status_for(score):
    if score <= 2:
        return "NORMAL", "green-pill"
    if score <= 5:
        return "ELEVATED", "yellow-pill"
    if score < 8:
        return "SERIOUS", "orange-pill"
    if score < 10:
        return "CRITICAL", "red-pill"
    return "CATASTROPHIC", "red-pill"

# ---------------------------
# HEADER
# ---------------------------
left, right = st.columns([4.5, 1.4], vertical_alignment="top")

with left:
    st.markdown('<div class="eyebrow">GLOBAL RISK DASHBOARD</div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-title">Are We Cooked? 🌍</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="subtitle">A sober look at global systemic risk — without turning every scary headline into apocalypse.</div>',
        unsafe_allow_html=True
    )

with right:
    st.markdown(f"""
        <div class="panel" style="padding:14px 16px;">
            <div class="mini-label">AS OF</div>
            <div style="font-weight:800;">{AS_OF}</div>
        </div>
    """, unsafe_allow_html=True)

# ---------------------------
# HERO
# ---------------------------
c1, c2 = st.columns([1.7, 1], gap="large")

with c1:
    status, pill = status_for(OVERALL_SCORE)
    st.markdown(f"""
    <div class="panel">
        <div class="mini-label">OVERALL GLOBAL RISK</div>
        <div class="big-score">{OVERALL_SCORE:.1f}<span style="font-size:1.4rem;color:#8f9aa5;"> / 10</span></div>
        <div style="margin:.8rem 0 1rem 0;">
            <span class="status-pill {pill}">{status}</span>
            <span style="color:{score_color(OVERALL_SCORE)};font-weight:800;">{OVERALL_TREND}</span>
        </div>
        <div style="color:#c4ccd3;line-height:1.65;">{OVERALL_SUMMARY}</div>
    </div>
    """, unsafe_allow_html=True)

with c2:
    st.markdown("""
    <div class="panel spotlight">
        <div class="mini-label">🔥 BIGGEST RISK RIGHT NOW</div>
        <h2 style="margin:.35rem 0 .6rem 0;">Energy</h2>
        <div style="color:#c4ccd3;line-height:1.6;">
            Hormuz disruption plus impaired Saudi bypass capacity is the clearest near-term pathway
            from serious regional conflict to broader global economic stress.
        </div>
        <div style="margin-top:1rem;font-weight:800;">👀 Watch: Saudi pipeline + Hormuz</div>
    </div>
    """, unsafe_allow_html=True)

# ---------------------------
# CATEGORY CARDS
# ---------------------------
st.markdown('<div class="section-title">Risk by category</div>', unsafe_allow_html=True)

for i in range(0, len(categories), 2):
    cols = st.columns(2, gap="large")
    for j, col in enumerate(cols):
        idx = i + j
        if idx >= len(categories):
            break
        item = categories[idx]
        with col:
            status, pill = status_for(item["score"])
            st.markdown(f"""
            <div class="metric-card">
                <div style="display:flex;justify-content:space-between;gap:18px;align-items:flex-start;">
                    <div>
                        <div class="risk-name">{item["emoji"]} {item["name"]}</div>
                        <div style="color:{score_color(item["score"])};font-weight:800;font-size:.84rem;">{item["trend"]}</div>
                    </div>
                    <div style="text-align:right;">
                        <div class="risk-score">{item["score"]:.1f}</div>
                        <div class="muted" style="font-size:.74rem;">/ 10</div>
                    </div>
                </div>
                <div style="margin:.8rem 0;">
                    <div style="height:8px;background:#252d34;border-radius:999px;overflow:hidden;">
                        <div style="width:{item["score"]*10}%;height:100%;background:{score_color(item["score"])};"></div>
                    </div>
                </div>
                <div style="color:#c5cdd4;line-height:1.55;font-size:.93rem;">{item["summary"]}</div>
            </div>
            """, unsafe_allow_html=True)

            with st.expander("Show next risk + escalation triggers"):
                st.markdown(f"**Next plausible risk:** {item['next']}")
                st.markdown(f"**⬆️ Raises score:** {item['up']}")
                st.markdown(f"**⬇️ Lowers score:** {item['down']}")

# ---------------------------
# HISTORY + PATHWAYS
# ---------------------------
st.markdown('<div class="section-title">Where this could go next</div>', unsafe_allow_html=True)
left, right = st.columns([1.45, 1], gap="large")

with left:
    st.markdown('<div class="mini-label">📈 RISK HISTORY</div>', unsafe_allow_html=True)
    fig = px.line(history, x="Date", y="Score", markers=True, range_y=[0, 10])
    fig.update_traces(line=dict(width=4), marker=dict(size=9))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#dfe5ea",
        margin=dict(l=10, r=10, t=10, b=10),
        height=330,
        xaxis=dict(showgrid=False, title=None),
        yaxis=dict(gridcolor="#26303a", title=None, dtick=2),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)

with right:
    st.markdown('<div class="mini-label">🧭 MOST PLAUSIBLE NEXT PATH</div>', unsafe_allow_html=True)
    for icon, name, detail, target in pathways:
        st.markdown(f"""
        <div class="detail-box">
            <div style="display:flex;justify-content:space-between;gap:14px;align-items:center;">
                <div>
                    <div style="font-weight:800;">{icon} {name}</div>
                    <div class="muted" style="font-size:.82rem;margin-top:3px;">{detail}</div>
                </div>
                <div style="font-size:1.15rem;font-weight:800;">{target}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

# ---------------------------
# CHANGES
# ---------------------------
st.markdown('<div class="section-title">What changed since the last report?</div>', unsafe_allow_html=True)
for change in changes:
    st.markdown(f"- {change}")

# ---------------------------
# SCORE KEY
# ---------------------------
st.markdown('<div class="section-title">How to read the meter</div>', unsafe_allow_html=True)
k1, k2, k3, k4, k5 = st.columns(5)
for col, label, desc, color in [
    (k1, "0–2", "Normal", "#49c878"),
    (k2, "3–5", "Elevated", "#e8c547"),
    (k3, "6–7", "Serious", "#f29f3d"),
    (k4, "8–9", "Critical", "#ef5c5c"),
    (k5, "10", "Catastrophic", "#111111"),
]:
    with col:
        st.markdown(f"""
        <div class="panel" style="padding:14px;">
            <div style="height:6px;background:{color};border-radius:999px;margin-bottom:10px;"></div>
            <div style="font-size:1.3rem;font-weight:800;">{label}</div>
            <div class="muted" style="font-size:.8rem;">{desc}</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("""
<div class="footer-note">
<strong>Important:</strong> This is an analytical index, not a probability of human extinction.
Scores are intended to reflect current systemic stress, resilience, and how risks interact with one another.
New scary headlines should not raise the meter unless they actually cross a defined threshold.
</div>
""", unsafe_allow_html=True)
