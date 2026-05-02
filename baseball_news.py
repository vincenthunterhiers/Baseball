#!/usr/bin/env python3
"""Fetch today's MLB matchups and recent baseball news."""

import json
from datetime import date
from urllib.request import urlopen
from urllib.error import URLError


MLB_SCHEDULE_URL = (
    "https://statsapi.mlb.com/api/v1/schedule"
    "?sportId=1&date={date}&hydrate=team,linescore"
)

NEWS_RSS_URL = (
    "https://www.mlb.com/feeds/news/rss.xml"
)


def fetch_json(url: str) -> dict:
    with urlopen(url, timeout=10) as response:
        return json.loads(response.read().decode())


def get_todays_matchups(game_date: str | None = None) -> list[dict]:
    """Return a list of today's MLB matchups."""
    if game_date is None:
        game_date = date.today().isoformat()
    url = MLB_SCHEDULE_URL.format(date=game_date)
    data = fetch_json(url)
    matchups = []
    for date_entry in data.get("dates", []):
        for game in date_entry.get("games", []):
            away = game["teams"]["away"]["team"]["name"]
            home = game["teams"]["home"]["team"]["name"]
            status = game["status"]["detailedState"]
            game_time = game.get("gameDate", "")
            matchups.append(
                {
                    "away": away,
                    "home": home,
                    "status": status,
                    "gameDate": game_time,
                }
            )
    return matchups


def print_matchups(game_date: str | None = None) -> None:
    """Print today's MLB matchups to stdout."""
    if game_date is None:
        game_date = date.today().isoformat()
    print(f"MLB Matchups for {game_date}")
    print("=" * 40)
    try:
        matchups = get_todays_matchups(game_date)
    except URLError as exc:
        print(f"Error fetching matchups: {exc}")
        return

    if not matchups:
        print("No games scheduled.")
        return

    for m in matchups:
        print(f"  {m['away']} @ {m['home']}")
        print(f"    Status : {m['status']}")
        if m["gameDate"]:
            print(f"    Time   : {m['gameDate']}")
        print()


if __name__ == "__main__":
    import sys

    game_date = sys.argv[1] if len(sys.argv) > 1 else None
    print_matchups(game_date)
