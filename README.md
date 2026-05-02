# ⚾ Baseball Predictor

A web application that lets you pick any date and instantly see every MLB game scheduled, including full team and player stats, win predictions, and optional live betting-odds comparisons.

## Features

| Feature | Details |
|---|---|
| **Game Schedule** | Browse any date; see matchup, venue, game time |
| **Win Prediction** | Pythagorean expectation + Log5 method + home-field advantage + pitcher ERA + recent form |
| **Team Stats** | Batting AVG, OBP, SLG, OPS, ERA, WHIP, K/9, R/G |
| **Player Roster** | Top hitters per team with AVG, OBP, SLG, OPS, HR, RBI |
| **Probable Pitchers** | ERA, WHIP, K/9, Win-Loss record |
| **Betting Odds** | Live moneyline odds + implied probabilities via [The Odds API](https://the-odds-api.com) |
| **Data Sources** | Live MLB Stats API (no key required); graceful fallback to sample data |

## Quick Start

```bash
# 1. Clone & enter the repo
git clone https://github.com/vincenthunterhiers/Baseball.git
cd Baseball

# 2. (Optional) create a virtual environment
python3 -m venv venv && source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the app
python app.py
```

Then open **http://localhost:5000** in your browser.

## Betting Odds (optional)

1. Sign up for a free API key at [the-odds-api.com](https://the-odds-api.com) (500 requests/month free tier)
2. Paste the key into the **Odds API key** field in the top-right corner of the app
3. Click **Set** — the key is kept in memory for the current page session only (never written to browser storage)

## Prediction Model

The win probability for each game is computed in four steps:

1. **Pythagorean Win%** — `RS^1.83 / (RS^1.83 + RA^1.83)` for each team
2. **Log5 combination** — `(PA − PA·PB) / (PA + PB − 2·PA·PB)`
3. **Home-field adjustment** — +4 % to home team
4. **Pitcher ERA adjustment** — up to ±5 % based on ERA differential vs. league average (4.25)
5. **Recent-form adjustment** — up to ±3 % based on last-10-games win difference

## Project Structure

```
Baseball/
├── app.py              # Flask backend, MLB API integration, prediction engine
├── requirements.txt
├── templates/
│   └── index.html      # Single-page UI
└── static/
    ├── css/style.css
    └── js/app.js
```

## Dependencies

- **Flask** ≥ 3.0 — web framework
- **requests** ≥ 2.31 — HTTP client for MLB Stats API & Odds API

Data is fetched from the **official MLB Stats API** (`statsapi.mlb.com`) — no API key required.

