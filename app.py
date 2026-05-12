"""
COEUS — Prediction Market Intelligence
Streamlit web app with PIN auth, market radar, AI chat, and watchlist.
"""

import streamlit as st
import requests
import json
import time
import anthropic
from datetime import datetime, timezone
from typing import Optional

# ── Page config (must be first) ──────────────────────
st.set_page_config(
    page_title="Coeus",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ══════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════

PIN_CODE       = st.secrets.get("PIN_CODE", "8719")
ANTHROPIC_KEY  = st.secrets.get("ANTHROPIC_API_KEY", "")
POLYMARKET_URL = "https://clob.polymarket.com/markets"
MODEL          = "claude-sonnet-4-20250514"
MAX_TOKENS     = 1024
TOP_N_MARKETS  = 10

# Categories we care about (filter out meme/celebrity noise)
ALLOWED_CATEGORIES = {
    "politics", "crypto", "economics", "finance",
    "sports", "science", "world", "technology",
    "business", "elections", "climate", "geopolitics",
}

# Keywords that signal a low-quality meme market — skip these
MEME_KEYWORDS = [
    "say", "tweet", "post", "word", "phrase", "curse", "swear",
    "meme", "joke", "emoji", "pardon", "celebrity", "kardashian",
    "elon musk say", "will trump say", "will biden say",
    "how many times", "first word", "nickname",
]

# ══════════════════════════════════════════════════════
# STYLES — Tokyo Night Mono (B&W cold variant)
# ══════════════════════════════════════════════════════

def inject_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;1,9..40,300&display=swap');

    /* ── Reset & root ── */
    :root {
        --bg:        #0c0c10;
        --surface:   #111118;
        --surface2:  #18181f;
        --surface3:  #1e1e28;
        --border:    #26263a;
        --border2:   #32324a;
        --text:      #e2e2ec;
        --text2:     #8888a8;
        --text3:     #55556a;
        --white:     #f0f0f8;
        --accent:    #e2e2ec;
        --yes:       #5af0a0;
        --no:        #f05a5a;
        --skip:      #f0c050;
        --mono:      'Space Mono', monospace;
        --sans:      'DM Sans', sans-serif;
    }

    html, body, [data-testid="stApp"] {
        background: var(--bg) !important;
        color: var(--text) !important;
        font-family: var(--sans) !important;
    }

    /* Hide streamlit chrome */
    #MainMenu, header, footer,
    [data-testid="stToolbar"],
    [data-testid="stDecoration"],
    [data-testid="stStatusWidget"] { display: none !important; }

    /* Main container */
    .main .block-container {
        padding: 0 !important;
        max-width: 100% !important;
    }

    /* ── Scrollbar ── */
    ::-webkit-scrollbar { width: 4px; height: 4px; }
    ::-webkit-scrollbar-track { background: var(--bg); }
    ::-webkit-scrollbar-thumb { background: var(--border2); border-radius: 2px; }

    /* ── Topbar ── */
    .coeus-topbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 32px;
        height: 56px;
        background: var(--surface);
        border-bottom: 1px solid var(--border);
        position: sticky;
        top: 0;
        z-index: 100;
    }
    .coeus-logo {
        font-family: var(--mono);
        font-size: 18px;
        font-weight: 700;
        color: var(--white);
        letter-spacing: 0.08em;
    }
    .coeus-logo span {
        color: var(--text3);
        font-size: 11px;
        font-weight: 400;
        margin-left: 10px;
        letter-spacing: 0.12em;
        text-transform: uppercase;
    }

    /* ── PIN screen ── */
    .pin-wrapper {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        min-height: 100vh;
        background: var(--bg);
        gap: 0;
    }
    .pin-logo {
        font-family: var(--mono);
        font-size: 32px;
        font-weight: 700;
        color: var(--white);
        letter-spacing: 0.1em;
        margin-bottom: 8px;
    }
    .pin-sub {
        font-family: var(--sans);
        font-size: 13px;
        color: var(--text3);
        letter-spacing: 0.15em;
        text-transform: uppercase;
        margin-bottom: 48px;
    }
    .pin-label {
        font-family: var(--mono);
        font-size: 11px;
        color: var(--text3);
        letter-spacing: 0.2em;
        text-transform: uppercase;
        margin-bottom: 12px;
    }
    @keyframes shake {
        0%,100%{transform:translateX(0)}
        20%{transform:translateX(-8px)}
        40%{transform:translateX(8px)}
        60%{transform:translateX(-6px)}
        80%{transform:translateX(6px)}
    }
    .pin-error { animation: shake 0.4s ease; color: var(--no); font-size: 12px; margin-top: 12px; }

    /* ── Nav tabs ── */
    .nav-tabs {
        display: flex;
        gap: 2px;
        padding: 0 32px;
        background: var(--surface);
        border-bottom: 1px solid var(--border);
    }
    .nav-tab {
        font-family: var(--mono);
        font-size: 11px;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        padding: 14px 20px;
        color: var(--text3);
        cursor: pointer;
        border-bottom: 2px solid transparent;
        transition: all 0.2s;
    }
    .nav-tab.active {
        color: var(--white);
        border-bottom-color: var(--white);
    }

    /* ── Market card ── */
    .market-card {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 16px;
        transition: border-color 0.2s, transform 0.2s;
        animation: fadeSlideIn 0.4s ease both;
    }
    .market-card:hover {
        border-color: var(--border2);
        transform: translateY(-1px);
    }
    @keyframes fadeSlideIn {
        from { opacity: 0; transform: translateY(16px); }
        to   { opacity: 1; transform: translateY(0); }
    }
    .market-card:nth-child(1)  { animation-delay: 0.05s; }
    .market-card:nth-child(2)  { animation-delay: 0.10s; }
    .market-card:nth-child(3)  { animation-delay: 0.15s; }
    .market-card:nth-child(4)  { animation-delay: 0.20s; }
    .market-card:nth-child(5)  { animation-delay: 0.25s; }
    .market-card:nth-child(6)  { animation-delay: 0.30s; }
    .market-card:nth-child(7)  { animation-delay: 0.35s; }
    .market-card:nth-child(8)  { animation-delay: 0.40s; }
    .market-card:nth-child(9)  { animation-delay: 0.45s; }
    .market-card:nth-child(10) { animation-delay: 0.50s; }

    .card-meta {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 12px;
    }
    .card-category {
        font-family: var(--mono);
        font-size: 10px;
        letter-spacing: 0.18em;
        text-transform: uppercase;
        color: var(--text3);
        background: var(--surface2);
        padding: 4px 10px;
        border-radius: 4px;
        border: 1px solid var(--border);
    }
    .card-date {
        font-family: var(--mono);
        font-size: 10px;
        color: var(--text3);
    }
    .card-question {
        font-family: var(--sans);
        font-size: 15px;
        font-weight: 500;
        color: var(--text);
        line-height: 1.5;
        margin-bottom: 18px;
    }

    /* Progress bar */
    .prob-row {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 18px;
    }
    .prob-bar-bg {
        flex: 1;
        height: 6px;
        background: var(--surface3);
        border-radius: 3px;
        overflow: hidden;
    }
    .prob-bar-fill {
        height: 100%;
        border-radius: 3px;
        transition: width 0.8s cubic-bezier(0.4,0,0.2,1);
    }
    .prob-pct {
        font-family: var(--mono);
        font-size: 14px;
        font-weight: 700;
        min-width: 44px;
        text-align: right;
    }
    .prob-label {
        font-family: var(--mono);
        font-size: 10px;
        letter-spacing: 0.1em;
        padding: 3px 8px;
        border-radius: 4px;
        font-weight: 700;
    }
    .label-yes  { color: var(--yes);  background: rgba(90,240,160,0.08);  border: 1px solid rgba(90,240,160,0.2);  }
    .label-no   { color: var(--no);   background: rgba(240,90,90,0.08);   border: 1px solid rgba(240,90,90,0.2);   }
    .label-skip { color: var(--skip); background: rgba(240,192,80,0.08);  border: 1px solid rgba(240,192,80,0.2);  }

    /* Verdict badge */
    .verdict-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-family: var(--mono);
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        padding: 6px 14px;
        border-radius: 6px;
        margin-bottom: 16px;
    }
    .verdict-yes  { color: var(--yes);  background: rgba(90,240,160,0.10);  border: 1px solid rgba(90,240,160,0.25);  }
    .verdict-no   { color: var(--no);   background: rgba(240,90,90,0.10);   border: 1px solid rgba(240,90,90,0.25);   }
    .verdict-skip { color: var(--skip); background: rgba(240,192,80,0.10);  border: 1px solid rgba(240,192,80,0.25);  }

    /* Reasons */
    .reasons-list { list-style: none; padding: 0; margin: 0; }
    .reason-item {
        display: flex;
        align-items: flex-start;
        gap: 10px;
        padding: 8px 0;
        border-bottom: 1px solid var(--border);
        font-family: var(--sans);
        font-size: 13px;
        color: var(--text2);
        line-height: 1.5;
    }
    .reason-item:last-child { border-bottom: none; }
    .reason-dot {
        width: 5px;
        height: 5px;
        border-radius: 50%;
        background: var(--text3);
        margin-top: 7px;
        flex-shrink: 0;
    }

    /* Card footer */
    .card-footer {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-top: 16px;
        padding-top: 14px;
        border-top: 1px solid var(--border);
    }
    .card-vol {
        font-family: var(--mono);
        font-size: 10px;
        color: var(--text3);
    }

    /* ── Skeleton loader ── */
    .skeleton {
        background: linear-gradient(90deg, var(--surface2) 25%, var(--surface3) 50%, var(--surface2) 75%);
        background-size: 200% 100%;
        animation: shimmer 1.5s infinite;
        border-radius: 6px;
    }
    @keyframes shimmer {
        from { background-position: 200% 0; }
        to   { background-position: -200% 0; }
    }
    .skeleton-card {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 16px;
    }
    .skeleton-line { height: 12px; margin-bottom: 10px; }
    .skeleton-title { height: 18px; width: 80%; margin-bottom: 18px; }
    .skeleton-bar { height: 6px; width: 100%; margin-bottom: 20px; }

    /* ── Chat ── */
    .chat-container {
        display: flex;
        flex-direction: column;
        gap: 12px;
        padding: 24px 0;
        min-height: 400px;
    }
    .chat-msg {
        display: flex;
        gap: 12px;
        animation: fadeSlideIn 0.3s ease;
    }
    .chat-msg.user { flex-direction: row-reverse; }
    .chat-avatar {
        width: 32px;
        height: 32px;
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-family: var(--mono);
        font-size: 11px;
        font-weight: 700;
        flex-shrink: 0;
    }
    .avatar-ai  { background: var(--surface3); color: var(--text2); border: 1px solid var(--border); }
    .avatar-usr { background: var(--white); color: var(--bg); }
    .chat-bubble {
        max-width: 75%;
        padding: 12px 16px;
        border-radius: 12px;
        font-family: var(--sans);
        font-size: 14px;
        line-height: 1.6;
    }
    .bubble-ai  {
        background: var(--surface);
        border: 1px solid var(--border);
        color: var(--text);
        border-radius: 12px 12px 12px 2px;
    }
    .bubble-usr {
        background: var(--surface3);
        border: 1px solid var(--border2);
        color: var(--text);
        border-radius: 12px 12px 2px 12px;
    }
    .chat-time {
        font-family: var(--mono);
        font-size: 9px;
        color: var(--text3);
        margin-top: 4px;
        text-align: right;
    }

    /* ── Watchlist ── */
    .watch-card {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 10px;
        padding: 18px 20px;
        margin-bottom: 10px;
        display: flex;
        align-items: center;
        gap: 16px;
        animation: fadeSlideIn 0.3s ease;
    }
    .watch-pct {
        font-family: var(--mono);
        font-size: 20px;
        font-weight: 700;
        min-width: 56px;
        text-align: center;
    }
    .watch-q {
        flex: 1;
        font-family: var(--sans);
        font-size: 14px;
        color: var(--text);
        line-height: 1.4;
    }
    .watch-verdict {
        font-family: var(--mono);
        font-size: 10px;
        font-weight: 700;
        padding: 4px 10px;
        border-radius: 4px;
    }

    /* ── Section header ── */
    .section-head {
        font-family: var(--mono);
        font-size: 11px;
        letter-spacing: 0.18em;
        text-transform: uppercase;
        color: var(--text3);
        margin-bottom: 20px;
        padding-bottom: 10px;
        border-bottom: 1px solid var(--border);
    }

    /* ── Buttons ── */
    div[data-testid="stButton"] > button {
        font-family: var(--mono) !important;
        font-size: 11px !important;
        letter-spacing: 0.15em !important;
        text-transform: uppercase !important;
        background: var(--white) !important;
        color: var(--bg) !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 10px 24px !important;
        font-weight: 700 !important;
        transition: opacity 0.2s !important;
        cursor: pointer !important;
    }
    div[data-testid="stButton"] > button:hover {
        opacity: 0.85 !important;
    }
    div[data-testid="stButton"] > button[kind="secondary"] {
        background: var(--surface2) !important;
        color: var(--text2) !important;
        border: 1px solid var(--border) !important;
    }

    /* ── Inputs ── */
    div[data-testid="stTextInput"] input,
    div[data-testid="stChatInput"] textarea {
        background: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: 8px !important;
        color: var(--text) !important;
        font-family: var(--sans) !important;
        font-size: 14px !important;
    }
    div[data-testid="stTextInput"] input:focus,
    div[data-testid="stChatInput"] textarea:focus {
        border-color: var(--border2) !important;
        box-shadow: 0 0 0 2px rgba(226,226,236,0.06) !important;
    }

    /* ── Select / Radio ── */
    div[data-testid="stRadio"] label,
    div[data-testid="stSelectbox"] label {
        font-family: var(--mono) !important;
        font-size: 11px !important;
        letter-spacing: 0.1em !important;
        text-transform: uppercase !important;
        color: var(--text3) !important;
    }
    div[data-testid="stSelectbox"] div[data-baseweb="select"] {
        background: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: 8px !important;
    }

    /* ── Divider ── */
    hr { border-color: var(--border) !important; }

    /* ── Spinner ── */
    div[data-testid="stSpinner"] { color: var(--text2) !important; }

    /* ── Padding wrapper ── */
    .page-content {
        padding: 32px 40px;
        max-width: 1100px;
        margin: 0 auto;
    }
    .page-content-wide {
        padding: 32px 40px;
    }

    /* ── Language toggle ── */
    .lang-toggle {
        display: flex;
        gap: 4px;
        font-family: var(--mono);
        font-size: 10px;
    }
    .lang-btn {
        padding: 4px 10px;
        border-radius: 4px;
        cursor: pointer;
        color: var(--text3);
        border: 1px solid var(--border);
        background: transparent;
    }
    .lang-btn.active {
        color: var(--white);
        background: var(--surface3);
        border-color: var(--border2);
    }

    /* ── Empty state ── */
    .empty-state {
        text-align: center;
        padding: 80px 0;
        color: var(--text3);
        font-family: var(--mono);
        font-size: 12px;
        letter-spacing: 0.1em;
    }
    .empty-icon { font-size: 32px; margin-bottom: 16px; opacity: 0.4; }

    /* ── Score ring (big number) ── */
    .score-big {
        font-family: var(--mono);
        font-size: 48px;
        font-weight: 700;
        line-height: 1;
    }

    /* Streamlit column gap */
    div[data-testid="column"] { padding: 0 8px !important; }
    div[data-testid="stColumns"] { gap: 0 !important; }

    /* Chat input */
    div[data-testid="stChatInputContainer"] {
        background: var(--surface) !important;
        border-top: 1px solid var(--border) !important;
        padding: 12px !important;
    }
    </style>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════
# SESSION STATE INIT
# ══════════════════════════════════════════════════════

def init_session():
    defaults = {
        "authenticated": False,
        "pin_error":     False,
        "tab":           "radar",
        "lang":          "EN",
        "analyses":      [],       # list of analyzed market dicts
        "watchlist":     [],       # list of market dicts
        "chat_history":  [],       # list of {role, content, time}
        "chat_context":  None,     # market dict currently being discussed
        "last_fetched":  None,
        "loading":       False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_session()


# ══════════════════════════════════════════════════════
# POLYMARKET API
# ══════════════════════════════════════════════════════

def is_meme_market(question: str, category: str) -> bool:
    """Return True if this is a low-quality meme/celebrity market."""
    q_lower = question.lower()
    for kw in MEME_KEYWORDS:
        if kw in q_lower:
            return True
    # Category check
    cat_lower = (category or "").lower()
    if cat_lower and not any(a in cat_lower for a in ALLOWED_CATEGORIES):
        # Unknown category — check question for sense
        nonsense = ["twitter", "instagram", "tiktok", "followers", "likes"]
        if any(n in q_lower for n in nonsense):
            return True
    return False


def fetch_markets(limit: int = 60) -> list:
    """
    Fetch active Polymarket markets, filter noise,
    return top N by volume.
    """
    try:
        params = {
            "active": "true",
            "closed": "false",
            "limit":  limit,
        }
        r = requests.get(POLYMARKET_URL, params=params, timeout=10)
        r.raise_for_status()
        raw = r.json()

        if isinstance(raw, dict):
            items = raw.get("data", [])
        else:
            items = raw

        markets = []
        for item in items:
            try:
                question  = item.get("question", "")
                category  = item.get("category", "")
                volume    = float(item.get("volume", 0) or 0)
                liquidity = float(item.get("liquidity", 0) or 0)
                end_date  = item.get("end_date_iso", "") or ""

                # Filters
                if not question:                        continue
                if volume < 5_000:                      continue
                if liquidity < 500:                     continue
                if is_meme_market(question, category):  continue

                # Extract YES probability
                yes_prob = 50.0
                tokens = item.get("tokens", [])
                for t in tokens:
                    if str(t.get("outcome", "")).upper() == "YES":
                        yes_prob = round(float(t.get("price", 0.5) or 0.5) * 100, 1)
                        break

                markets.append({
                    "id":        item.get("condition_id", item.get("id", "")),
                    "question":  question,
                    "category":  category or "General",
                    "volume":    volume,
                    "liquidity": liquidity,
                    "yes_prob":  yes_prob,
                    "end_date":  end_date[:10] if end_date else "—",
                    "url":       f"https://polymarket.com/event/{item.get('market_slug', '')}",
                })
            except Exception:
                continue

        # Sort by volume, take top N
        markets.sort(key=lambda x: x["volume"], reverse=True)
        return markets[:TOP_N_MARKETS]

    except Exception as e:
        st.error(f"Polymarket API error: {e}")
        return []


# ══════════════════════════════════════════════════════
# CLAUDE API
# ══════════════════════════════════════════════════════

def get_claude_client() -> Optional[anthropic.Anthropic]:
    key = ANTHROPIC_KEY
    if not key:
        return None
    return anthropic.Anthropic(api_key=key)


def analyze_market(market: dict, lang: str = "EN") -> dict:
    """
    Ask Claude to analyze a single prediction market.
    Returns dict with verdict, score, reasons, summary.
    """
    client = get_claude_client()
    if not client:
        return _mock_analysis(market)

    lang_instruction = (
        "Respond in Turkish." if lang == "TR"
        else "Respond in English."
    )

    prompt = f"""You are a sharp, data-driven prediction market analyst.

Analyze this Polymarket prediction market and give a clear, honest assessment.

Market: {market['question']}
Current YES probability: {market['yes_prob']}%
Volume: ${market['volume']:,.0f}
Category: {market['category']}
Closes: {market['end_date']}

{lang_instruction}

Respond ONLY with valid JSON. No markdown, no extra text:
{{
  "verdict": "LEAN YES" | "LEAN NO" | "SKIP",
  "confidence": <integer 1-10>,
  "edge": "<one sentence: why the market might be mispriced or fairly priced>",
  "reasons": [
    "<reason 1 — specific, factual>",
    "<reason 2 — specific, factual>",
    "<reason 3 — specific, factual>"
  ],
  "summary": "<2-sentence max analyst take>"
}}

Rules:
- LEAN YES: you think YES is more likely than current price implies
- LEAN NO: you think NO is more likely than current price implies
- SKIP: market is too uncertain, too thin, or unanalyzable
- Be honest. If you don't know enough, say SKIP.
- Do NOT be bullish just because YES is above 50%.
"""

    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = resp.content[0].text.strip()
        # Clean up any accidental markdown
        raw = raw.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw)
        data["market"] = market
        return data
    except json.JSONDecodeError:
        return _mock_analysis(market)
    except Exception as e:
        return _mock_analysis(market)


def _mock_analysis(market: dict) -> dict:
    """Fallback when API key is missing — demo mode."""
    prob = market["yes_prob"]
    if prob > 65:
        verdict = "LEAN YES"
    elif prob < 35:
        verdict = "LEAN NO"
    else:
        verdict = "SKIP"

    return {
        "verdict":    verdict,
        "confidence": 5,
        "edge":       "Demo mode — add ANTHROPIC_API_KEY for real analysis.",
        "reasons":    [
            "Market price reflects current consensus",
            "Volume indicates moderate participation",
            "No AI analysis available in demo mode",
        ],
        "summary": "This is demo mode. Connect Claude API for real market intelligence.",
        "market":  market,
    }


def chat_with_claude(messages: list, lang: str = "EN") -> str:
    """Send a multi-turn conversation to Claude."""
    client = get_claude_client()
    if not client:
        return "⚡ Demo mode — add ANTHROPIC_API_KEY in secrets to enable AI chat."

    lang_note = "Always respond in Turkish." if lang == "TR" else "Always respond in English."
    system = f"""You are Coeus, a sharp and concise prediction market intelligence assistant.
You help users understand prediction markets on Polymarket — probabilities, risks, and opportunities.
Be direct, data-driven, and honest. Never be vague. {lang_note}
Keep responses under 200 words unless the user asks for more detail.
Format key points as short bullet points when helpful."""

    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=messages,
        )
        return resp.content[0].text.strip()
    except Exception as e:
        return f"Error: {e}"


# ══════════════════════════════════════════════════════
# UI COMPONENTS
# ══════════════════════════════════════════════════════

def render_topbar():
    lang = st.session_state.lang
    st.markdown(f"""
    <div class="coeus-topbar">
        <div class="coeus-logo">
            COEUS<span>Prediction Intelligence</span>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_nav():
    tab = st.session_state.tab
    lang = st.session_state.lang

    labels = {
        "EN": {"radar": "Market Radar", "chat": "Ask Coeus", "watch": "Watchlist"},
        "TR": {"radar": "Market Radar", "chat": "Coeus'a Sor", "watch": "Takip Listesi"},
    }[lang]

    col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 3, 1])

    with col1:
        if st.button(labels["radar"], key="nav_radar",
                     type="primary" if tab == "radar" else "secondary"):
            st.session_state.tab = "radar"
            st.rerun()
    with col2:
        if st.button(labels["chat"], key="nav_chat",
                     type="primary" if tab == "chat" else "secondary"):
            st.session_state.tab = "chat"
            st.rerun()
    with col3:
        if st.button(labels["watch"], key="nav_watch",
                     type="primary" if tab == "watch" else "secondary"):
            st.session_state.tab = "watch"
            st.rerun()
    with col5:
        new_lang = "TR" if lang == "EN" else "EN"
        if st.button(f"{'🇬🇧 EN' if lang == 'TR' else '🇹🇷 TR'}", key="lang_toggle",
                     type="secondary"):
            st.session_state.lang = new_lang
            st.rerun()


def verdict_html(verdict: str) -> str:
    cls = {"LEAN YES": "verdict-yes", "LEAN NO": "verdict-no", "SKIP": "verdict-skip"}.get(verdict, "verdict-skip")
    icon = {"LEAN YES": "▲", "LEAN NO": "▼", "SKIP": "—"}.get(verdict, "—")
    return f'<div class="verdict-badge {cls}">{icon} {verdict}</div>'


def prob_color(pct: float) -> str:
    if pct >= 65: return "var(--yes)"
    if pct <= 35: return "var(--no)"
    return "var(--text2)"


def fmt_volume(v: float) -> str:
    if v >= 1_000_000: return f"${v/1_000_000:.1f}M vol"
    if v >= 1_000:     return f"${v/1_000:.0f}K vol"
    return f"${v:.0f} vol"


def render_market_card(analysis: dict, idx: int, show_add_watch: bool = True):
    m       = analysis["market"]
    verdict = analysis.get("verdict", "SKIP")
    reasons = analysis.get("reasons", [])
    summary = analysis.get("summary", "")
    conf    = analysis.get("confidence", 5)
    edge    = analysis.get("edge", "")
    pct     = m["yes_prob"]
    color   = prob_color(pct)

    reasons_html = "".join(
        f'<li class="reason-item"><div class="reason-dot"></div><div>{r}</div></li>'
        for r in reasons
    )

    already_watching = any(w["id"] == m["id"] for w in st.session_state.watchlist)
    watch_label = "✓" if already_watching else "+"

    st.markdown(f"""
    <div class="market-card">
        <div class="card-meta">
            <span class="card-category">{m['category']}</span>
            <span class="card-date">Closes {m['end_date']}</span>
        </div>
        <div class="card-question">{m['question']}</div>
        <div class="prob-row">
            <div class="prob-bar-bg">
                <div class="prob-bar-fill" style="width:{pct}%;background:{color};"></div>
            </div>
            <span class="prob-pct" style="color:{color};">{pct}%</span>
            <span class="prob-label label-{'yes' if pct>=50 else 'no'}">YES</span>
        </div>
        {verdict_html(verdict)}
        <div style="font-family:var(--sans);font-size:13px;color:var(--text2);margin-bottom:14px;font-style:italic;">
            {summary}
        </div>
        {f'<div style="font-family:var(--mono);font-size:10px;color:var(--text3);margin-bottom:12px;letter-spacing:0.08em;">EDGE · {edge}</div>' if edge else ''}
        <ul class="reasons-list">{reasons_html}</ul>
        <div class="card-footer">
            <span class="card-vol">{fmt_volume(m['volume'])} · Confidence {conf}/10</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Action buttons below card
    if show_add_watch:
        bc1, bc2, bc3 = st.columns([1, 1, 6])
        with bc1:
            if not already_watching:
                if st.button(f"+ Watch", key=f"watch_{idx}_{m['id'][:8]}", type="secondary"):
                    st.session_state.watchlist.append({**m, "analysis": analysis})
                    st.rerun()
            else:
                st.button("✓ Watching", key=f"watched_{idx}_{m['id'][:8]}", type="secondary", disabled=True)
        with bc2:
            if st.button("Chat →", key=f"chat_{idx}_{m['id'][:8]}", type="secondary"):
                st.session_state.tab = "chat"
                st.session_state.chat_context = m
                # Pre-seed chat with market context
                if not st.session_state.chat_history:
                    st.session_state.chat_history = [{
                        "role": "assistant",
                        "content": f"I've loaded this market for analysis:\n\n**{m['question']}**\n\nCurrent YES: {m['yes_prob']}% | Volume: {fmt_volume(m['volume'])}\n\nWhat would you like to know?",
                        "time": datetime.now().strftime("%H:%M"),
                    }]
                st.rerun()


def render_skeleton():
    st.markdown("""
    <div class="skeleton-card">
        <div class="skeleton skeleton-line" style="width:25%"></div>
        <div class="skeleton skeleton-title"></div>
        <div class="skeleton skeleton-bar"></div>
        <div class="skeleton skeleton-line" style="width:60%"></div>
        <div class="skeleton skeleton-line" style="width:75%"></div>
        <div class="skeleton skeleton-line" style="width:50%"></div>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════
# PAGES
# ══════════════════════════════════════════════════════

def page_pin():
    """PIN entry screen."""
    error_class = "pin-error" if st.session_state.pin_error else ""

    st.markdown("""
    <div style="display:flex;flex-direction:column;align-items:center;
                justify-content:center;min-height:90vh;gap:0;">
        <div class="pin-logo">COEUS</div>
        <div class="pin-sub">Prediction Intelligence</div>
        <div class="pin-label">Enter PIN</div>
    </div>
    """, unsafe_allow_html=True)

    # Center the PIN input
    _, col, _ = st.columns([2, 1, 2])
    with col:
        pin = st.text_input(
            "", max_chars=4, type="password",
            placeholder="····", key="pin_input",
            label_visibility="collapsed"
        )
        if st.button("ENTER", use_container_width=True):
            if pin == PIN_CODE:
                st.session_state.authenticated = True
                st.session_state.pin_error     = False
                st.rerun()
            else:
                st.session_state.pin_error = True
                st.rerun()

        if st.session_state.pin_error:
            st.markdown('<div class="pin-error" style="text-align:center;margin-top:8px;">Incorrect PIN</div>',
                        unsafe_allow_html=True)


def page_radar():
    lang = st.session_state.lang
    texts = {
        "EN": {
            "head":    "Market Radar",
            "sub":     "Live analysis of top Polymarket markets filtered for quality.",
            "btn":     "Analyze Markets",
            "loading": "Fetching markets and running analysis...",
            "fetched": "Last analyzed",
        },
        "TR": {
            "head":    "Market Radar",
            "sub":     "En kaliteli Polymarket marketlerinin canlı analizi.",
            "btn":     "Marketleri Analiz Et",
            "loading": "Marketler çekiliyor ve analiz yapılıyor...",
            "fetched": "Son analiz",
        },
    }[lang]

    st.markdown('<div class="page-content">', unsafe_allow_html=True)
    st.markdown(f'<div class="section-head">{texts["head"]}</div>', unsafe_allow_html=True)
    st.markdown(f'<p style="color:var(--text2);font-size:13px;margin-bottom:24px;">{texts["sub"]}</p>',
                unsafe_allow_html=True)

    col_btn, col_info = st.columns([1, 3])
    with col_btn:
        analyze_clicked = st.button(texts["btn"], key="analyze_btn")

    if st.session_state.last_fetched:
        with col_info:
            st.markdown(
                f'<p style="color:var(--text3);font-size:11px;font-family:var(--mono);'
                f'padding-top:12px;">{texts["fetched"]} {st.session_state.last_fetched}</p>',
                unsafe_allow_html=True
            )

    st.markdown("---")

    if analyze_clicked:
        # Show skeletons while loading
        placeholders = [st.empty() for _ in range(5)]
        for ph in placeholders:
            with ph.container():
                render_skeleton()

        with st.spinner(texts["loading"]):
            markets = fetch_markets()
            analyses = []
            for i, m in enumerate(markets):
                result = analyze_market(m, lang)
                analyses.append(result)
                # Update progress
                if i < len(placeholders):
                    placeholders[i].empty()

        # Clear remaining skeletons
        for ph in placeholders:
            ph.empty()

        st.session_state.analyses    = analyses
        st.session_state.last_fetched = datetime.now().strftime("%H:%M:%S")
        st.rerun()

    # Render analyses
    if st.session_state.analyses:
        for i, analysis in enumerate(st.session_state.analyses):
            render_market_card(analysis, i)
    elif not analyze_clicked:
        st.markdown("""
        <div class="empty-state">
            <div class="empty-icon">⚡</div>
            <div>Hit Analyze Markets to pull live data</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)


def page_chat():
    lang = st.session_state.lang
    history = st.session_state.chat_history
    ctx = st.session_state.chat_context

    texts = {
        "EN": {
            "head":        "Ask Coeus",
            "sub":         "Chat about any prediction market. Ask about probabilities, risks, historical patterns.",
            "placeholder": "Ask anything about prediction markets...",
            "clear":       "Clear Chat",
            "ctx_label":   "Context",
            "ctx_none":    "No market selected — ask anything about Polymarket",
            "ctx_change":  "Change market",
        },
        "TR": {
            "head":        "Coeus'a Sor",
            "sub":         "Herhangi bir market hakkında sohbet et. Olasılıklar, riskler, geçmiş veriler.",
            "placeholder": "Prediction marketler hakkında herhangi bir şey sor...",
            "clear":       "Sohbeti Temizle",
            "ctx_label":   "Konu",
            "ctx_none":    "Market seçilmedi — Polymarket hakkında her şeyi sorabilirsin",
            "ctx_change":  "Marketi değiştir",
        },
    }[lang]

    st.markdown('<div class="page-content">', unsafe_allow_html=True)
    st.markdown(f'<div class="section-head">{texts["head"]}</div>', unsafe_allow_html=True)

    # Context bar + clear button
    col_ctx, col_clr = st.columns([4, 1])
    with col_ctx:
        if ctx:
            st.markdown(
                f'<div style="background:var(--surface2);border:1px solid var(--border);'
                f'border-radius:8px;padding:10px 14px;font-size:12px;color:var(--text2);">'
                f'<span style="color:var(--text3);font-family:var(--mono);font-size:10px;'
                f'letter-spacing:0.1em;text-transform:uppercase;">{texts["ctx_label"]} · </span>'
                f'{ctx["question"][:80]}{"..." if len(ctx["question"])>80 else ""}'
                f'</div>', unsafe_allow_html=True
            )
        else:
            st.markdown(
                f'<div style="color:var(--text3);font-size:12px;padding:10px 0;">'
                f'{texts["ctx_none"]}</div>', unsafe_allow_html=True
            )
    with col_clr:
        if st.button(texts["clear"], key="clear_chat", type="secondary"):
            st.session_state.chat_history = []
            st.session_state.chat_context = None
            st.rerun()

    st.markdown("---")

    # Chat history
    if history:
        for msg in history:
            role    = msg["role"]
            content = msg["content"]
            ts      = msg.get("time", "")
            if role == "user":
                st.markdown(f"""
                <div class="chat-msg user">
                    <div>
                        <div class="chat-bubble bubble-usr">{content}</div>
                        <div class="chat-time">{ts}</div>
                    </div>
                    <div class="chat-avatar avatar-usr">YOU</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                import re
                # Simple markdown-ish rendering for bullet points
                rendered = content.replace("\n\n", "<br><br>").replace("\n•", "<br>•").replace("\n-", "<br>•")
                st.markdown(f"""
                <div class="chat-msg">
                    <div class="chat-avatar avatar-ai">AI</div>
                    <div>
                        <div class="chat-bubble bubble-ai">{rendered}</div>
                        <div class="chat-time">{ts}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="empty-state" style="padding:40px 0;">
            <div class="empty-icon">💬</div>
            <div>Start a conversation</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # Chat input
    user_input = st.chat_input(texts["placeholder"])
    if user_input:
        ts = datetime.now().strftime("%H:%M")
        st.session_state.chat_history.append({
            "role": "user", "content": user_input, "time": ts
        })

        # Build messages for Claude
        api_messages = []
        # Inject market context if available
        if ctx:
            ctx_note = (
                f"The user is asking about this Polymarket market: "
                f"'{ctx['question']}' — Current YES: {ctx['yes_prob']}% "
                f"| Volume: ${ctx['volume']:,.0f} | Closes: {ctx['end_date']}"
            )
            api_messages.append({"role": "user", "content": ctx_note})
            api_messages.append({"role": "assistant", "content": "Understood. I'll analyze this market context."})

        for msg in st.session_state.chat_history:
            api_messages.append({"role": msg["role"], "content": msg["content"]})

        with st.spinner(""):
            reply = chat_with_claude(api_messages, lang)

        st.session_state.chat_history.append({
            "role": "assistant", "content": reply,
            "time": datetime.now().strftime("%H:%M")
        })
        st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)


def page_watchlist():
    lang = st.session_state.lang
    watchlist = st.session_state.watchlist

    texts = {
        "EN": {
            "head":    "Watchlist",
            "sub":     "Markets you're tracking. Refresh to get updated prices.",
            "empty":   "No markets in watchlist yet.",
            "empty2":  "Add markets from the Radar tab.",
            "remove":  "Remove",
            "refresh": "Refresh Prices",
            "chat":    "Chat →",
        },
        "TR": {
            "head":    "Takip Listesi",
            "sub":     "Takip ettiğin marketler. Güncel fiyatlar için yenile.",
            "empty":   "Henüz takip listesinde market yok.",
            "empty2":  "Radar sekmesinden market ekle.",
            "remove":  "Kaldır",
            "refresh": "Fiyatları Yenile",
            "chat":    "Sohbet →",
        },
    }[lang]

    st.markdown('<div class="page-content">', unsafe_allow_html=True)
    st.markdown(f'<div class="section-head">{texts["head"]}</div>', unsafe_allow_html=True)
    st.markdown(f'<p style="color:var(--text2);font-size:13px;margin-bottom:24px;">{texts["sub"]}</p>',
                unsafe_allow_html=True)

    if not watchlist:
        st.markdown(f"""
        <div class="empty-state">
            <div class="empty-icon">📋</div>
            <div>{texts["empty"]}</div>
            <div style="margin-top:8px;font-size:10px;">{texts["empty2"]}</div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # Refresh button
    col_r, _ = st.columns([1, 4])
    with col_r:
        if st.button(texts["refresh"], type="secondary"):
            with st.spinner("Refreshing..."):
                # Re-fetch prices for watchlisted markets
                fresh = fetch_markets(limit=100)
                fresh_map = {m["id"]: m for m in fresh}
                updated = []
                for w in st.session_state.watchlist:
                    if w["id"] in fresh_map:
                        w.update({
                            "yes_prob":  fresh_map[w["id"]]["yes_prob"],
                            "volume":    fresh_map[w["id"]]["volume"],
                            "liquidity": fresh_map[w["id"]]["liquidity"],
                        })
                    updated.append(w)
                st.session_state.watchlist = updated
            st.rerun()

    st.markdown("---")

    for i, m in enumerate(watchlist):
        analysis  = m.get("analysis", {})
        verdict   = analysis.get("verdict", "—")
        pct       = m["yes_prob"]
        color     = prob_color(pct)
        v_cls     = {"LEAN YES": "label-yes", "LEAN NO": "label-no"}.get(verdict, "label-skip")

        st.markdown(f"""
        <div class="watch-card">
            <div class="watch-pct" style="color:{color};">{pct}%</div>
            <div class="watch-q">
                <div style="font-size:13px;font-weight:500;">{m['question']}</div>
                <div style="font-size:11px;color:var(--text3);margin-top:4px;font-family:var(--mono);">
                    {m['category']} · {fmt_volume(m['volume'])} · Closes {m['end_date']}
                </div>
            </div>
            <span class="prob-label {v_cls}">{verdict}</span>
        </div>
        """, unsafe_allow_html=True)

        bc1, bc2, _ = st.columns([1, 1, 5])
        with bc1:
            if st.button(texts["chat"], key=f"wchat_{i}", type="secondary"):
                st.session_state.tab = "chat"
                st.session_state.chat_context = m
                st.rerun()
        with bc2:
            if st.button(texts["remove"], key=f"wrem_{i}", type="secondary"):
                st.session_state.watchlist.pop(i)
                st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════
# MAIN ROUTER
# ══════════════════════════════════════════════════════

def main():
    inject_css()

    if not st.session_state.authenticated:
        page_pin()
        return

    render_topbar()
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    render_nav()
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    tab = st.session_state.tab
    if tab == "radar":
        page_radar()
    elif tab == "chat":
        page_chat()
    elif tab == "watch":
        page_watchlist()


if __name__ == "__main__":
    main()
