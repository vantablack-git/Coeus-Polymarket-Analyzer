# COEUS — Prediction Market Intelligence

A sharp, minimal prediction market analysis tool powered by Claude AI and Polymarket data.

---

## Features

- **Market Radar** — Pulls top Polymarket markets in real time, filters out meme/celebrity noise, runs Claude AI analysis on each: LEAN YES / LEAN NO / SKIP verdict + 3 reasons
- **Ask Coeus** — Full AI chat. Click any market → auto-loaded into chat context. Ask about probabilities, history, risks
- **Watchlist** — Save markets you're tracking, refresh prices, quick-chat from watchlist
- **Language Toggle** — English / Turkish
- **PIN Gate** — 4-digit PIN on entry

---

## Local Setup

```bash
git clone <your-repo>
cd coeus
pip install -r requirements.txt

# Create secrets file
mkdir -p .streamlit
cat > .streamlit/secrets.toml << EOF
PIN_CODE = "8719"
ANTHROPIC_API_KEY = "sk-ant-YOUR-KEY-HERE"
EOF

streamlit run app.py
```

---

## Deploy to Streamlit Cloud

1. Push to GitHub (secrets.toml is gitignored — safe)
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. New app → your repo → `app.py`
4. Settings → Secrets → paste:
```toml
PIN_CODE = "8719"
ANTHROPIC_API_KEY = "sk-ant-YOUR-KEY-HERE"
```
5. Deploy ✓

---

## Market Filters

Coeus automatically removes:
- Volume < $5,000 (thin markets)
- Liquidity < $500 (unanalyzable)
- Meme/celebrity behavior markets ("Will X say Y")
- Twitter/Instagram engagement markets

What remains: elections, crypto price targets, economic data, sports, geopolitics.

---

## Stack

- **Frontend**: Streamlit (Tokyo Night Mono theme)
- **AI**: Claude claude-sonnet-4-20250514 via Anthropic API
- **Data**: Polymarket CLOB API (free, no key)
- **Auth**: PIN via Streamlit session state + secrets

---

*Built for serious prediction market research. Not financial advice.*
