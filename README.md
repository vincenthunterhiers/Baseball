# Baseball Game Predictor

A browser-based MLB research dashboard that lets you pick a date, gather the
major league games scheduled for that day, inspect first-pitch times and venues,
compare team and player statistics, and generate a transparent model prediction.
If you provide a The Odds API key, the app also compares its projection against
bookmaker moneylines.

## Features

- Select any MLB date and load games from MLB's public Stats API.
- Show matchup, venue, status, and localized first-pitch time.
- Pull team season stats, record, run scoring/prevention, OPS, ERA, WHIP, and
  recent run differential.
- Include probable pitcher season ERA/WHIP when MLB has announced starters.
- Lazily load active roster player hitting and pitching stats per game.
- Calculate a simple prediction score using team strength, run prevention,
  probable pitchers, home-field advantage, recent form, and optional market odds.
- Compare sportsbook head-to-head moneylines when a The Odds API key is entered.

## Running locally

This app is dependency-free and can be served by any static HTTP server:

```bash
python3 -m http.server 8000
```

Then open <http://localhost:8000>.

Opening `index.html` directly in a browser may work in some environments, but a
local static server is more reliable for ES module loading.

## Odds API setup

Odds are optional. To enable them, create an API key at
<https://the-odds-api.com/> and paste it into the app's "Odds API key" field.
The key is only used in your browser session and is not stored by this app.

## Prediction model notes

The model is intentionally transparent rather than statistically exhaustive. It
weights:

- winning percentage
- OPS
- team ERA and WHIP
- runs scored and allowed per game
- recent run differential
- probable-pitcher ERA/WHIP
- home-field advantage
- average implied market probability, when odds are available

Use the output as a research starting point. It does not account for confirmed
lineups, weather, injuries, bullpen availability, umpire tendencies, late
scratches, or live odds movement.

## Tests

Run the lightweight structural tests with:

```bash
python3 -m unittest discover -s tests
```
