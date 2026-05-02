"""
Baseball Web App — Flask backend
Fetches MLB schedules, team/player stats, computes win predictions,
and optionally retrieves betting odds via The Odds API.
"""

from flask import Flask, render_template, jsonify, request
import requests
from datetime import datetime, date, timedelta
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MLB_BASE = "https://statsapi.mlb.com/api/v1"
MAX_DISPLAYED_PLAYERS = 10   # Top hitters shown per team in the roster tab
ODDS_BASE = "https://api.the-odds-api.com/v4"
REQUEST_TIMEOUT = 10

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _get(url, params=None):
    """GET with timeout; returns parsed JSON or None on failure."""
    try:
        resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.warning("HTTP error fetching %s: %s", url, exc)
        return None


def _ml_to_prob(ml):
    """Convert American moneyline to implied win probability (0-1)."""
    try:
        ml = float(ml)
        if ml >= 0:
            return 100.0 / (ml + 100.0)
        else:
            return abs(ml) / (abs(ml) + 100.0)
    except (TypeError, ValueError, ZeroDivisionError):
        return 0.5


def pythagorean_win_pct(runs_scored, runs_allowed, exp=1.83):
    """Pythagorean win expectation (Bill James, exponent 1.83 by default)."""
    if runs_scored <= 0 or runs_allowed <= 0:
        return 0.5
    rs, ra = runs_scored ** exp, runs_allowed ** exp
    return rs / (rs + ra)


def log5(p_a, p_b):
    """Bill James Log5 method: P(A beats B) given each team's true win pct."""
    denom = p_a + p_b - 2 * p_a * p_b
    if denom == 0:
        return 0.5
    return (p_a - p_a * p_b) / denom


def calculate_win_probability(home_stats, away_stats,
                              home_pitcher=None, away_pitcher=None):
    """
    Compute home team win probability using:
      1. Pythagorean expectation per team
      2. Log5 combination
      3. Home-field advantage (+4 %)
      4. Probable-pitcher ERA adjustment (±5 %)
      5. Recent form (last-10 games) adjustment (±3 %)
    Returns float in [0.10, 0.90].
    """
    # --- Base team strength ---
    home_pyth = pythagorean_win_pct(
        home_stats.get("runs_per_game", 4.5),
        home_stats.get("runs_allowed_per_game", 4.5),
    )
    away_pyth = pythagorean_win_pct(
        away_stats.get("runs_per_game", 4.5),
        away_stats.get("runs_allowed_per_game", 4.5),
    )

    # --- Log5 combination ---
    prob = log5(home_pyth, away_pyth)

    # --- Home-field advantage ---
    prob = prob * 0.96 + 0.04

    # --- Pitcher adjustment ---
    if home_pitcher and away_pitcher:
        league_avg_era = 4.25
        home_era = home_pitcher.get("era", league_avg_era)
        away_era = away_pitcher.get("era", league_avg_era)
        # Positive delta → home pitcher better → boost home prob
        era_delta = away_era - home_era
        pitcher_adj = (era_delta / (league_avg_era * 4)) * 0.05
        prob += pitcher_adj

    # --- Recent-form adjustment ---
    home_form = home_stats.get("last10_wins", 5) / 10.0
    away_form = away_stats.get("last10_wins", 5) / 10.0
    form_adj = (home_form - away_form) * 0.03
    prob += form_adj

    return round(max(0.10, min(0.90, prob)), 4)


# ---------------------------------------------------------------------------
# Mock data (used when MLB API is unreachable)
# ---------------------------------------------------------------------------

MOCK_TEAMS = {
    143: {"id": 143, "name": "Philadelphia Phillies", "abbreviation": "PHI",
          "venue": "Citizens Bank Park", "league": "NL"},
    121: {"id": 121, "name": "New York Mets",          "abbreviation": "NYM",
          "venue": "Citi Field",           "league": "NL"},
    147: {"id": 147, "name": "New York Yankees",        "abbreviation": "NYY",
          "venue": "Yankee Stadium",       "league": "AL"},
    111: {"id": 111, "name": "Boston Red Sox",          "abbreviation": "BOS",
          "venue": "Fenway Park",          "league": "AL"},
    119: {"id": 119, "name": "Los Angeles Dodgers",     "abbreviation": "LAD",
          "venue": "Dodger Stadium",       "league": "NL"},
    109: {"id": 109, "name": "Arizona Diamondbacks",    "abbreviation": "ARI",
          "venue": "Chase Field",          "league": "NL"},
    145: {"id": 145, "name": "Chicago White Sox",       "abbreviation": "CWS",
          "venue": "Guaranteed Rate Field","league": "AL"},
    112: {"id": 112, "name": "Chicago Cubs",            "abbreviation": "CHC",
          "venue": "Wrigley Field",        "league": "NL"},
    117: {"id": 117, "name": "Houston Astros",          "abbreviation": "HOU",
          "venue": "Minute Maid Park",     "league": "AL"},
    140: {"id": 140, "name": "Texas Rangers",           "abbreviation": "TEX",
          "venue": "Globe Life Field",     "league": "AL"},
    136: {"id": 136, "name": "Seattle Mariners",        "abbreviation": "SEA",
          "venue": "T-Mobile Park",        "league": "AL"},
    133: {"id": 133, "name": "Oakland Athletics",       "abbreviation": "OAK",
          "venue": "Sutter Health Park",   "league": "AL"},
    137: {"id": 137, "name": "San Francisco Giants",    "abbreviation": "SF",
          "venue": "Oracle Park",          "league": "NL"},
    135: {"id": 135, "name": "San Diego Padres",        "abbreviation": "SD",
          "venue": "Petco Park",           "league": "NL"},
}

MOCK_TEAM_STATS = {
    143: {"wins": 54, "losses": 41, "runs_per_game": 5.1, "runs_allowed_per_game": 4.2,
          "batting_avg": .268, "obp": .343, "slg": .452, "ops": .795,
          "era": 3.84, "whip": 1.21, "k_per_9": 9.8, "last10_wins": 7},
    121: {"wins": 49, "losses": 46, "runs_per_game": 4.6, "runs_allowed_per_game": 4.5,
          "batting_avg": .251, "obp": .323, "slg": .418, "ops": .741,
          "era": 4.12, "whip": 1.28, "k_per_9": 9.1, "last10_wins": 5},
    147: {"wins": 57, "losses": 38, "runs_per_game": 5.4, "runs_allowed_per_game": 4.0,
          "batting_avg": .262, "obp": .340, "slg": .461, "ops": .801,
          "era": 3.71, "whip": 1.19, "k_per_9": 10.2, "last10_wins": 8},
    111: {"wins": 44, "losses": 51, "runs_per_game": 4.3, "runs_allowed_per_game": 4.9,
          "batting_avg": .246, "obp": .318, "slg": .402, "ops": .720,
          "era": 4.45, "whip": 1.35, "k_per_9": 8.7, "last10_wins": 4},
    119: {"wins": 62, "losses": 33, "runs_per_game": 5.7, "runs_allowed_per_game": 3.8,
          "batting_avg": .277, "obp": .355, "slg": .480, "ops": .835,
          "era": 3.52, "whip": 1.14, "k_per_9": 10.6, "last10_wins": 8},
    109: {"wins": 47, "losses": 48, "runs_per_game": 4.5, "runs_allowed_per_game": 4.6,
          "batting_avg": .255, "obp": .326, "slg": .423, "ops": .749,
          "era": 4.21, "whip": 1.29, "k_per_9": 9.3, "last10_wins": 5},
    145: {"wins": 32, "losses": 63, "runs_per_game": 3.8, "runs_allowed_per_game": 5.4,
          "batting_avg": .232, "obp": .297, "slg": .381, "ops": .678,
          "era": 5.02, "whip": 1.48, "k_per_9": 8.1, "last10_wins": 3},
    112: {"wins": 51, "losses": 44, "runs_per_game": 4.8, "runs_allowed_per_game": 4.4,
          "batting_avg": .259, "obp": .333, "slg": .435, "ops": .768,
          "era": 4.05, "whip": 1.26, "k_per_9": 9.4, "last10_wins": 6},
    117: {"wins": 55, "losses": 40, "runs_per_game": 5.0, "runs_allowed_per_game": 4.1,
          "batting_avg": .265, "obp": .338, "slg": .447, "ops": .785,
          "era": 3.88, "whip": 1.22, "k_per_9": 9.9, "last10_wins": 7},
    140: {"wins": 50, "losses": 45, "runs_per_game": 4.7, "runs_allowed_per_game": 4.5,
          "batting_avg": .257, "obp": .328, "slg": .430, "ops": .758,
          "era": 4.18, "whip": 1.27, "k_per_9": 9.0, "last10_wins": 5},
    136: {"wins": 52, "losses": 43, "runs_per_game": 4.6, "runs_allowed_per_game": 4.2,
          "batting_avg": .248, "obp": .320, "slg": .415, "ops": .735,
          "era": 3.95, "whip": 1.23, "k_per_9": 10.1, "last10_wins": 6},
    133: {"wins": 35, "losses": 60, "runs_per_game": 3.9, "runs_allowed_per_game": 5.2,
          "batting_avg": .237, "obp": .305, "slg": .388, "ops": .693,
          "era": 4.85, "whip": 1.44, "k_per_9": 8.4, "last10_wins": 3},
    137: {"wins": 46, "losses": 49, "runs_per_game": 4.4, "runs_allowed_per_game": 4.6,
          "batting_avg": .252, "obp": .324, "slg": .420, "ops": .744,
          "era": 4.22, "whip": 1.30, "k_per_9": 9.2, "last10_wins": 4},
    135: {"wins": 53, "losses": 42, "runs_per_game": 4.9, "runs_allowed_per_game": 4.2,
          "batting_avg": .262, "obp": .335, "slg": .443, "ops": .778,
          "era": 3.91, "whip": 1.22, "k_per_9": 10.0, "last10_wins": 7},
}

MOCK_PITCHERS = {
    143: {"name": "Zack Wheeler",    "hand": "R", "era": 2.98, "whip": 1.05, "k_per_9": 10.8, "wins": 11, "losses": 4},
    121: {"name": "Kodai Senga",     "hand": "R", "era": 3.10, "whip": 1.10, "k_per_9": 10.5, "wins": 10, "losses": 5},
    147: {"name": "Gerrit Cole",     "hand": "R", "era": 2.88, "whip": 1.02, "k_per_9": 11.2, "wins": 13, "losses": 4},
    111: {"name": "Brayan Bello",    "hand": "R", "era": 3.82, "whip": 1.22, "k_per_9": 9.1,  "wins": 9,  "losses": 8},
    119: {"name": "Yoshinobu Yamamoto","hand":"R", "era": 3.00, "whip": 1.04, "k_per_9": 10.9, "wins": 12, "losses": 3},
    109: {"name": "Zac Gallen",      "hand": "R", "era": 3.47, "whip": 1.15, "k_per_9": 9.7,  "wins": 10, "losses": 7},
    145: {"name": "Garrett Crochet", "hand": "L", "era": 3.29, "whip": 1.08, "k_per_9": 11.5, "wins": 6,  "losses": 12},
    112: {"name": "Justin Steele",   "hand": "L", "era": 3.52, "whip": 1.14, "k_per_9": 9.4,  "wins": 10, "losses": 6},
    117: {"name": "Framber Valdez",  "hand": "L", "era": 3.17, "whip": 1.12, "k_per_9": 8.8,  "wins": 12, "losses": 6},
    140: {"name": "Nathan Eovaldi",  "hand": "R", "era": 3.65, "whip": 1.18, "k_per_9": 9.0,  "wins": 11, "losses": 7},
    136: {"name": "Logan Gilbert",   "hand": "R", "era": 3.25, "whip": 1.09, "k_per_9": 10.3, "wins": 12, "losses": 5},
    133: {"name": "JP Sears",        "hand": "L", "era": 4.41, "whip": 1.33, "k_per_9": 8.5,  "wins": 7,  "losses": 11},
    137: {"name": "Logan Webb",      "hand": "R", "era": 3.38, "whip": 1.10, "k_per_9": 9.6,  "wins": 10, "losses": 8},
    135: {"name": "Dylan Cease",     "hand": "R", "era": 3.05, "whip": 1.07, "k_per_9": 11.0, "wins": 12, "losses": 5},
}

MOCK_PLAYERS = {
    143: [
        {"name": "Trea Turner",     "position": "SS", "avg": .285, "hr": 18, "rbi": 72,  "obp": .348, "slg": .478},
        {"name": "Bryce Harper",    "position": "1B", "avg": .296, "hr": 24, "rbi": 81,  "obp": .380, "slg": .532},
        {"name": "Kyle Schwarber",  "position": "LF", "avg": .240, "hr": 34, "rbi": 79,  "obp": .354, "slg": .519},
        {"name": "Nick Castellanos","position": "RF", "avg": .271, "hr": 19, "rbi": 68,  "obp": .320, "slg": .455},
        {"name": "J.T. Realmuto",   "position": "C",  "avg": .265, "hr": 15, "rbi": 58,  "obp": .332, "slg": .442},
    ],
    121: [
        {"name": "Francisco Lindor","position": "SS", "avg": .280, "hr": 25, "rbi": 84,  "obp": .352, "slg": .495},
        {"name": "Pete Alonso",     "position": "1B", "avg": .252, "hr": 30, "rbi": 89,  "obp": .334, "slg": .505},
        {"name": "Mark Vientos",    "position": "3B", "avg": .278, "hr": 22, "rbi": 71,  "obp": .341, "slg": .478},
        {"name": "Starling Marte",  "position": "CF", "avg": .270, "hr": 12, "rbi": 54,  "obp": .330, "slg": .425},
        {"name": "Jesse Winker",    "position": "LF", "avg": .261, "hr": 14, "rbi": 61,  "obp": .358, "slg": .430},
    ],
    147: [
        {"name": "Aaron Judge",     "position": "CF", "avg": .305, "hr": 42, "rbi": 102, "obp": .415, "slg": .620},
        {"name": "Juan Soto",       "position": "RF", "avg": .290, "hr": 32, "rbi": 95,  "obp": .405, "slg": .535},
        {"name": "Giancarlo Stanton","position": "DH","avg": .248, "hr": 27, "rbi": 78,  "obp": .325, "slg": .498},
        {"name": "Anthony Volpe",   "position": "SS", "avg": .258, "hr": 18, "rbi": 62,  "obp": .322, "slg": .432},
        {"name": "Jazz Chisholm Jr.","position":"2B", "avg": .265, "hr": 24, "rbi": 74,  "obp": .340, "slg": .470},
    ],
    111: [
        {"name": "Rafael Devers",   "position": "3B", "avg": .278, "hr": 28, "rbi": 83,  "obp": .345, "slg": .492},
        {"name": "Trevor Story",    "position": "SS", "avg": .249, "hr": 16, "rbi": 57,  "obp": .318, "slg": .428},
        {"name": "Jarren Duran",    "position": "CF", "avg": .290, "hr": 14, "rbi": 64,  "obp": .345, "slg": .465},
        {"name": "Tyler O'Neill",   "position": "LF", "avg": .252, "hr": 22, "rbi": 70,  "obp": .320, "slg": .455},
        {"name": "Masataka Yoshida","position": "DH", "avg": .282, "hr": 15, "rbi": 66,  "obp": .355, "slg": .455},
    ],
    119: [
        {"name": "Shohei Ohtani",   "position": "DH", "avg": .310, "hr": 40, "rbi": 104, "obp": .396, "slg": .638},
        {"name": "Freddie Freeman", "position": "1B", "avg": .302, "hr": 23, "rbi": 92,  "obp": .388, "slg": .520},
        {"name": "Mookie Betts",    "position": "SS", "avg": .290, "hr": 26, "rbi": 84,  "obp": .368, "slg": .520},
        {"name": "Teoscar Hernandez","position":"LF", "avg": .268, "hr": 24, "rbi": 75,  "obp": .325, "slg": .478},
        {"name": "Will Smith",      "position": "C",  "avg": .278, "hr": 18, "rbi": 67,  "obp": .358, "slg": .480},
    ],
    117: [
        {"name": "Yordan Alvarez",  "position": "DH", "avg": .305, "hr": 35, "rbi": 98,  "obp": .389, "slg": .590},
        {"name": "Jose Altuve",     "position": "2B", "avg": .285, "hr": 18, "rbi": 65,  "obp": .358, "slg": .468},
        {"name": "Jeremy Peña",     "position": "SS", "avg": .262, "hr": 15, "rbi": 60,  "obp": .318, "slg": .435},
        {"name": "Kyle Tucker",     "position": "RF", "avg": .280, "hr": 21, "rbi": 78,  "obp": .352, "slg": .490},
        {"name": "Alex Bregman",    "position": "3B", "avg": .272, "hr": 20, "rbi": 74,  "obp": .358, "slg": .468},
    ],
    136: [
        {"name": "Cal Raleigh",     "position": "C",  "avg": .255, "hr": 28, "rbi": 76,  "obp": .320, "slg": .488},
        {"name": "Julio Rodriguez", "position": "CF", "avg": .281, "hr": 22, "rbi": 72,  "obp": .341, "slg": .472},
        {"name": "Randy Arozarena", "position": "LF", "avg": .258, "hr": 18, "rbi": 68,  "obp": .328, "slg": .445},
        {"name": "J.P. Crawford",   "position": "SS", "avg": .255, "hr": 10, "rbi": 52,  "obp": .340, "slg": .390},
        {"name": "Mitch Garver",    "position": "DH", "avg": .268, "hr": 16, "rbi": 58,  "obp": .348, "slg": .452},
    ],
    135: [
        {"name": "Fernando Tatis Jr.","position":"SS","avg": .272, "hr": 31, "rbi": 88,  "obp": .336, "slg": .528},
        {"name": "Manny Machado",   "position": "3B", "avg": .268, "hr": 22, "rbi": 78,  "obp": .338, "slg": .462},
        {"name": "Jackson Merrill", "position": "CF", "avg": .278, "hr": 18, "rbi": 70,  "obp": .330, "slg": .468},
        {"name": "Jake Cronenworth","position": "1B", "avg": .248, "hr": 14, "rbi": 55,  "obp": .322, "slg": .412},
        {"name": "Jurickson Profar","position": "LF", "avg": .262, "hr": 16, "rbi": 62,  "obp": .348, "slg": .432},
    ],
    109: [
        {"name": "Corbin Carroll",  "position": "CF", "avg": .275, "hr": 20, "rbi": 72,  "obp": .350, "slg": .470},
        {"name": "Ketel Marte",     "position": "2B", "avg": .291, "hr": 18, "rbi": 68,  "obp": .358, "slg": .480},
        {"name": "Eugenio Suarez",  "position": "3B", "avg": .248, "hr": 24, "rbi": 75,  "obp": .319, "slg": .462},
        {"name": "Christian Walker","position": "1B", "avg": .255, "hr": 22, "rbi": 71,  "obp": .326, "slg": .458},
        {"name": "Lourdes Gurriel Jr.","position":"LF","avg":.265, "hr": 15, "rbi": 58,  "obp": .318, "slg": .435},
    ],
    112: [
        {"name": "Dansby Swanson",  "position": "SS", "avg": .246, "hr": 18, "rbi": 65,  "obp": .318, "slg": .432},
        {"name": "Ian Happ",        "position": "LF", "avg": .262, "hr": 16, "rbi": 60,  "obp": .358, "slg": .448},
        {"name": "Seiya Suzuki",    "position": "RF", "avg": .278, "hr": 18, "rbi": 68,  "obp": .348, "slg": .462},
        {"name": "Cody Bellinger",  "position": "CF", "avg": .272, "hr": 20, "rbi": 74,  "obp": .338, "slg": .462},
        {"name": "Christopher Morel","position":"3B", "avg": .255, "hr": 22, "rbi": 70,  "obp": .312, "slg": .468},
    ],
    140: [
        {"name": "Corey Seager",    "position": "SS", "avg": .285, "hr": 22, "rbi": 78,  "obp": .358, "slg": .495},
        {"name": "Marcus Semien",   "position": "2B", "avg": .260, "hr": 20, "rbi": 70,  "obp": .325, "slg": .452},
        {"name": "Adolis Garcia",   "position": "RF", "avg": .262, "hr": 25, "rbi": 80,  "obp": .318, "slg": .482},
        {"name": "Wyatt Langford",  "position": "LF", "avg": .268, "hr": 18, "rbi": 65,  "obp": .335, "slg": .462},
        {"name": "Josh Jung",       "position": "3B", "avg": .258, "hr": 16, "rbi": 60,  "obp": .318, "slg": .440},
    ],
    137: [
        {"name": "Matt Chapman",    "position": "3B", "avg": .250, "hr": 22, "rbi": 72,  "obp": .322, "slg": .452},
        {"name": "Heliot Ramos",    "position": "RF", "avg": .268, "hr": 16, "rbi": 58,  "obp": .335, "slg": .442},
        {"name": "Patrick Bailey",  "position": "C",  "avg": .245, "hr": 10, "rbi": 45,  "obp": .312, "slg": .390},
        {"name": "Tyler Fitzgerald","position": "SS", "avg": .255, "hr": 14, "rbi": 52,  "obp": .312, "slg": .422},
        {"name": "LaMonte Wade Jr.","position": "1B", "avg": .252, "hr": 12, "rbi": 50,  "obp": .348, "slg": .418},
    ],
    133: [
        {"name": "Brent Rooker",    "position": "DH", "avg": .255, "hr": 24, "rbi": 72,  "obp": .322, "slg": .472},
        {"name": "Zack Gelof",      "position": "2B", "avg": .248, "hr": 18, "rbi": 60,  "obp": .318, "slg": .445},
        {"name": "Shea Langeliers", "position": "C",  "avg": .238, "hr": 19, "rbi": 58,  "obp": .302, "slg": .438},
        {"name": "JJ Bleday",       "position": "CF", "avg": .240, "hr": 15, "rbi": 50,  "obp": .315, "slg": .415},
        {"name": "Tyler Soderstrom","position": "LF", "avg": .245, "hr": 14, "rbi": 48,  "obp": .308, "slg": .412},
    ],
    145: [
        {"name": "Luis Robert Jr.", "position": "CF", "avg": .258, "hr": 24, "rbi": 70,  "obp": .315, "slg": .475},
        {"name": "Andrew Vaughn",   "position": "1B", "avg": .252, "hr": 16, "rbi": 60,  "obp": .312, "slg": .428},
        {"name": "Gavin Sheets",    "position": "LF", "avg": .242, "hr": 14, "rbi": 52,  "obp": .298, "slg": .415},
        {"name": "Lenyn Sosa",      "position": "SS", "avg": .235, "hr": 12, "rbi": 48,  "obp": .290, "slg": .398},
        {"name": "Martin Maldonado","position": "C",  "avg": .215, "hr": 5,  "rbi": 28,  "obp": .280, "slg": .328},
    ],
}

MOCK_GAME_SCHEDULE = [
    {"gamePk": 1001, "away_team_id": 143, "home_team_id": 121, "game_time": "19:10", "series": "Regular Season"},
    {"gamePk": 1002, "away_team_id": 111, "home_team_id": 147, "game_time": "19:05", "series": "Regular Season"},
    {"gamePk": 1003, "away_team_id": 109, "home_team_id": 119, "game_time": "22:10", "series": "Regular Season"},
    {"gamePk": 1004, "away_team_id": 133, "home_team_id": 136, "game_time": "21:40", "series": "Regular Season"},
    {"gamePk": 1005, "away_team_id": 145, "home_team_id": 112, "game_time": "20:05", "series": "Regular Season"},
    {"gamePk": 1006, "away_team_id": 140, "home_team_id": 117, "game_time": "20:10", "series": "Regular Season"},
    {"gamePk": 1007, "away_team_id": 137, "home_team_id": 135, "game_time": "21:40", "series": "Regular Season"},
]


def get_mock_games(date_str):
    games = []
    for g in MOCK_GAME_SCHEDULE:
        away = MOCK_TEAMS[g["away_team_id"]]
        home = MOCK_TEAMS[g["home_team_id"]]
        games.append({
            "gamePk": g["gamePk"],
            "gameDate": date_str,
            "gameTime": g["game_time"],
            "status": "Scheduled",
            "awayTeam": {"id": away["id"], "name": away["name"],
                         "abbreviation": away["abbreviation"]},
            "homeTeam": {"id": home["id"], "name": home["name"],
                         "abbreviation": home["abbreviation"]},
            "venue": home["venue"],
            "seriesDescription": g["series"],
            "isMock": True,
        })
    return games


def get_mock_game_details(game_pk, date_str=None):
    game_pk = int(game_pk)
    schedule_entry = next((g for g in MOCK_GAME_SCHEDULE if g["gamePk"] == game_pk), None)
    if not schedule_entry:
        return None

    away_id = schedule_entry["away_team_id"]
    home_id = schedule_entry["home_team_id"]
    away_team = MOCK_TEAMS[away_id]
    home_team = MOCK_TEAMS[home_id]
    away_stats = MOCK_TEAM_STATS[away_id]
    home_stats = MOCK_TEAM_STATS[home_id]
    away_pitcher = MOCK_PITCHERS.get(away_id)
    home_pitcher = MOCK_PITCHERS.get(home_id)

    home_win_prob = calculate_win_probability(
        home_stats, away_stats, home_pitcher, away_pitcher
    )

    return {
        "gamePk": game_pk,
        "gameDate": date_str or date.today().isoformat(),
        "gameTime": schedule_entry["game_time"],
        "venue": home_team["venue"],
        "status": "Scheduled",
        "awayTeam": {
            "id": away_id,
            "name": away_team["name"],
            "abbreviation": away_team["abbreviation"],
            "record": f"{away_stats['wins']}-{away_stats['losses']}",
            "stats": away_stats,
            "probablePitcher": away_pitcher,
            "players": MOCK_PLAYERS.get(away_id, []),
        },
        "homeTeam": {
            "id": home_id,
            "name": home_team["name"],
            "abbreviation": home_team["abbreviation"],
            "record": f"{home_stats['wins']}-{home_stats['losses']}",
            "stats": home_stats,
            "probablePitcher": home_pitcher,
            "players": MOCK_PLAYERS.get(home_id, []),
        },
        "prediction": {
            "homeWinProbability": home_win_prob,
            "awayWinProbability": round(1 - home_win_prob, 4),
            "favored": home_team["name"] if home_win_prob >= 0.5 else away_team["name"],
            "confidence": "High" if abs(home_win_prob - 0.5) > 0.15
                          else "Medium" if abs(home_win_prob - 0.5) > 0.07
                          else "Low",
            "factors": [
                f"Home field advantage (+4% to {home_team['abbreviation']})",
                f"Pythagorean Win%: {home_team['abbreviation']} {pythagorean_win_pct(home_stats['runs_per_game'], home_stats['runs_allowed_per_game']):.3f} vs "
                f"{away_team['abbreviation']} {pythagorean_win_pct(away_stats['runs_per_game'], away_stats['runs_allowed_per_game']):.3f}",
                f"Probable pitchers: {home_pitcher['name'] if home_pitcher else 'TBD'} (ERA {home_pitcher['era'] if home_pitcher else 'N/A'}) vs "
                f"{away_pitcher['name'] if away_pitcher else 'TBD'} (ERA {away_pitcher['era'] if away_pitcher else 'N/A'})",
                f"Recent form (L10): {home_team['abbreviation']} {home_stats['last10_wins']}-{10 - home_stats['last10_wins']} vs "
                f"{away_team['abbreviation']} {away_stats['last10_wins']}-{10 - away_stats['last10_wins']}",
            ],
        },
        "isMock": True,
    }


# ---------------------------------------------------------------------------
# MLB Stats API helpers
# ---------------------------------------------------------------------------

def fetch_mlb_schedule(date_str):
    """Fetch schedule from MLB Stats API."""
    data = _get(f"{MLB_BASE}/schedule",
                {"sportId": 1, "date": date_str, "hydrate":
                 "team,venue,game(content(summary))"})
    if not data:
        return None

    games = []
    for date_entry in data.get("dates", []):
        for game in date_entry.get("games", []):
            status = game.get("status", {}).get("abstractGameState", "Preview")
            game_pk = game.get("gamePk")
            game_dt = game.get("gameDate", "")
            # Parse time
            game_time = ""
            if game_dt:
                try:
                    dt = datetime.fromisoformat(game_dt.replace("Z", "+00:00"))
                    game_time = dt.strftime("%H:%M")
                except ValueError:
                    game_time = game_dt

            away = game.get("teams", {}).get("away", {}).get("team", {})
            home = game.get("teams", {}).get("home", {}).get("team", {})

            games.append({
                "gamePk": game_pk,
                "gameDate": date_str,
                "gameTime": game_time,
                "status": status,
                "awayTeam": {
                    "id": away.get("id"),
                    "name": away.get("name", ""),
                    "abbreviation": away.get("abbreviation", ""),
                },
                "homeTeam": {
                    "id": home.get("id"),
                    "name": home.get("name", ""),
                    "abbreviation": home.get("abbreviation", ""),
                },
                "venue": game.get("venue", {}).get("name", ""),
                "seriesDescription": game.get("seriesDescription", "Regular Season"),
                "isMock": False,
            })
    return games


def fetch_team_season_stats(team_id, season=None):
    """Fetch team hitting + pitching stats for a season."""
    if season is None:
        season = datetime.now().year

    hitting = _get(f"{MLB_BASE}/teams/{team_id}/stats",
                   {"stats": "season", "group": "hitting", "season": season})
    pitching = _get(f"{MLB_BASE}/teams/{team_id}/stats",
                    {"stats": "season", "group": "pitching", "season": season})

    stats = MOCK_TEAM_STATS.get(team_id, {
        "wins": 0, "losses": 0,
        "runs_per_game": 4.5, "runs_allowed_per_game": 4.5,
        "batting_avg": .250, "obp": .320, "slg": .410, "ops": .730,
        "era": 4.25, "whip": 1.30, "k_per_9": 9.0, "last10_wins": 5,
    }).copy()

    if hitting:
        for split in hitting.get("stats", []):
            s = split.get("splits", [{}])[0].get("stat", {}) if split.get("splits") else {}
            if s:
                stats["batting_avg"] = float(s.get("avg", stats["batting_avg"]))
                stats["obp"] = float(s.get("obp", stats["obp"]))
                stats["slg"] = float(s.get("slg", stats["slg"]))
                stats["ops"] = float(s.get("ops", stats["ops"]))
                rs = s.get("runs")
                gp = s.get("gamesPlayed")
                if rs and gp:
                    stats["runs_per_game"] = round(int(rs) / int(gp), 2)

    if pitching:
        for split in pitching.get("stats", []):
            s = split.get("splits", [{}])[0].get("stat", {}) if split.get("splits") else {}
            if s:
                stats["era"] = float(s.get("era", stats["era"]))
                stats["whip"] = float(s.get("whip", stats["whip"]))
                ra = s.get("runs")
                gp = s.get("gamesPlayed")
                if ra and gp:
                    stats["runs_allowed_per_game"] = round(int(ra) / int(gp), 2)

    return stats


def fetch_probable_pitcher(game_pk, team_id):
    """Fetch probable pitcher for a team in a game."""
    data = _get(f"{MLB_BASE}/game/{game_pk}/boxscore")
    if not data:
        return MOCK_PITCHERS.get(team_id)

    side = None
    teams = data.get("teams", {})
    for s in ("home", "away"):
        t = teams.get(s, {}).get("team", {})
        if t.get("id") == team_id:
            side = s
            break

    if not side:
        return MOCK_PITCHERS.get(team_id)

    pitcher_info = teams.get(side, {}).get("probablePitcher", {})
    if not pitcher_info:
        return MOCK_PITCHERS.get(team_id)

    pitcher_id = pitcher_info.get("id")
    pitcher_name = pitcher_info.get("fullName", "TBD")

    # Fetch season stats
    p_stats = _get(f"{MLB_BASE}/people/{pitcher_id}/stats",
                   {"stats": "season", "group": "pitching",
                    "season": datetime.now().year})
    era, whip, k9, w, l = 4.50, 1.30, 9.0, 0, 0
    if p_stats:
        for split in p_stats.get("stats", []):
            s = split.get("splits", [{}])[0].get("stat", {}) if split.get("splits") else {}
            if s:
                era = float(s.get("era", era))
                whip = float(s.get("whip", whip))
                w = int(s.get("wins", w))
                l = int(s.get("losses", l))
                ip = float(s.get("inningsPitched", 1))
                so = int(s.get("strikeOuts", 0))
                k9 = round(so / ip * 9, 1) if ip > 0 else 9.0

    return {
        "name": pitcher_name,
        "era": era,
        "whip": whip,
        "k_per_9": k9,
        "wins": w,
        "losses": l,
    }


def fetch_roster_stats(team_id, season=None):
    """Fetch top hitters for a team."""
    if season is None:
        season = datetime.now().year

    data = _get(f"{MLB_BASE}/teams/{team_id}/roster",
                {"rosterType": "active", "season": season})
    if not data:
        return MOCK_PLAYERS.get(team_id, [])

    players = []
    for p in data.get("roster", [])[:MAX_DISPLAYED_PLAYERS]:
        pid = p.get("person", {}).get("id")
        pname = p.get("person", {}).get("fullName", "")
        pos = p.get("position", {}).get("abbreviation", "")

        p_stats = _get(f"{MLB_BASE}/people/{pid}/stats",
                       {"stats": "season", "group": "hitting", "season": season})
        avg = obp = slg = 0.0
        hr = rbi = 0
        if p_stats:
            for split in p_stats.get("stats", []):
                s = split.get("splits", [{}])[0].get("stat", {}) if split.get("splits") else {}
                if s:
                    avg = float(s.get("avg", 0))
                    obp = float(s.get("obp", 0))
                    slg = float(s.get("slg", 0))
                    hr = int(s.get("homeRuns", 0))
                    rbi = int(s.get("rbi", 0))

        if avg > 0 or hr > 0:  # skip pitchers / no-stat players
            players.append({
                "name": pname, "position": pos,
                "avg": avg, "hr": hr, "rbi": rbi,
                "obp": obp, "slg": slg,
            })

    players.sort(key=lambda x: x["avg"], reverse=True)
    return players[:MAX_DISPLAYED_PLAYERS] if players else MOCK_PLAYERS.get(team_id, [])


def fetch_odds(api_key, sport="baseball_mlb"):
    """
    Fetch moneyline odds from The Odds API.
    Returns dict keyed by '{away_abbr}_vs_{home_abbr}' with list of bookmaker odds.
    """
    if not api_key:
        return {}
    data = _get(f"{ODDS_BASE}/sports/{sport}/odds",
                {"apiKey": api_key, "regions": "us", "markets": "h2h",
                 "oddsFormat": "american"})
    if not data:
        return {}

    results = {}
    for game in data:
        teams = game.get("teams", [])
        if len(teams) < 2:
            continue
        home_team = game.get("home_team", "")
        books = []
        for bm in game.get("bookmakers", []):
            for mkt in bm.get("markets", []):
                if mkt.get("key") != "h2h":
                    continue
                outcomes = {o["name"]: o["price"] for o in mkt.get("outcomes", [])}
                if home_team in outcomes:
                    home_ml = outcomes[home_team]
                    away_team = [t for t in outcomes if t != home_team]
                    away_ml = outcomes[away_team[0]] if away_team else None
                    books.append({
                        "bookmaker": bm.get("title", ""),
                        "homeMoneyline": home_ml,
                        "awayMoneyline": away_ml,
                        "homeImpliedProb": round(_ml_to_prob(home_ml), 4),
                        "awayImpliedProb": round(_ml_to_prob(away_ml), 4) if away_ml else None,
                    })
        if books:
            key = f"{teams[0].split()[-1]}_vs_{teams[1].split()[-1]}"
            results[key] = {"bookmakers": books, "homeTeam": home_team}

    return results


def fetch_standings(season=None):
    """Fetch current standings."""
    if season is None:
        season = datetime.now().year
    data = _get(f"{MLB_BASE}/standings",
                {"leagueId": "103,104", "season": season,
                 "standingsTypes": "regularSeason"})
    if not data:
        return {}

    records = {}
    for rec in data.get("records", []):
        for tr in rec.get("teamRecords", []):
            tid = tr.get("team", {}).get("id")
            records[tid] = {
                "wins": tr.get("wins", 0),
                "losses": tr.get("losses", 0),
                "pct": float(tr.get("winningPercentage", 0)),
                "gb": tr.get("gamesBack", "-"),
            }
    return records


# ---------------------------------------------------------------------------
# Flask routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    today = date.today().isoformat()
    return render_template("index.html", today=today)


@app.route("/api/games")
def api_games():
    date_str = request.args.get("date", date.today().isoformat())

    # Try live API first
    games = fetch_mlb_schedule(date_str)

    if not games and games != []:          # API failed
        games = get_mock_games(date_str)
        source = "mock"
    elif games == []:                      # Real response but no games
        source = "live"
    else:
        source = "live"

    if not games:
        games = get_mock_games(date_str)
        source = "mock"

    return jsonify({"games": games, "source": source, "date": date_str})


@app.route("/api/game/<game_pk>/details")
def api_game_details(game_pk):
    odds_key = request.args.get("oddsApiKey", "")
    season = datetime.now().year

    # Determine if this is a mock game
    try:
        gid = int(game_pk)
    except ValueError:
        return jsonify({"error": "Invalid game ID"}), 400

    is_mock = 1000 <= gid < 2000

    if is_mock:
        date_str = request.args.get("date", date.today().isoformat())
        details = get_mock_game_details(gid, date_str)
        if not details:
            return jsonify({"error": "Game not found"}), 404
    else:
        # Fetch live game data
        game_data = _get(f"{MLB_BASE}.1/game/{game_pk}/feed/live")
        if not game_data:
            # fall back to mock if API unavailable
            date_str = request.args.get("date", date.today().isoformat())
            details = get_mock_game_details(1001, date_str)
            details["gamePk"] = gid
        else:
            gd = game_data.get("gameData", {})
            away_info = gd.get("teams", {}).get("away", {})
            home_info = gd.get("teams", {}).get("home", {})
            away_id = away_info.get("id")
            home_id = home_info.get("id")

            away_stats = fetch_team_season_stats(away_id, season)
            home_stats = fetch_team_season_stats(home_id, season)

            # standings for W-L record
            standings = fetch_standings(season)
            away_rec = standings.get(away_id, {})
            home_rec = standings.get(home_id, {})

            away_pitcher = fetch_probable_pitcher(gid, away_id)
            home_pitcher = fetch_probable_pitcher(gid, home_id)

            away_players = fetch_roster_stats(away_id, season)
            home_players = fetch_roster_stats(home_id, season)

            home_win_prob = calculate_win_probability(
                home_stats, away_stats, home_pitcher, away_pitcher
            )

            details = {
                "gamePk": gid,
                "venue": gd.get("venue", {}).get("name", ""),
                "gameTime": gd.get("datetime", {}).get("time", ""),
                "status": gd.get("status", {}).get("abstractGameState", ""),
                "awayTeam": {
                    "id": away_id,
                    "name": away_info.get("name", ""),
                    "abbreviation": away_info.get("abbreviation", ""),
                    "record": f"{away_rec.get('wins', 0)}-{away_rec.get('losses', 0)}",
                    "stats": away_stats,
                    "probablePitcher": away_pitcher,
                    "players": away_players,
                },
                "homeTeam": {
                    "id": home_id,
                    "name": home_info.get("name", ""),
                    "abbreviation": home_info.get("abbreviation", ""),
                    "record": f"{home_rec.get('wins', 0)}-{home_rec.get('losses', 0)}",
                    "stats": home_stats,
                    "probablePitcher": home_pitcher,
                    "players": home_players,
                },
                "prediction": {
                    "homeWinProbability": home_win_prob,
                    "awayWinProbability": round(1 - home_win_prob, 4),
                    "favored": home_info.get("name", "") if home_win_prob >= 0.5 else away_info.get("name", ""),
                    "confidence": "High" if abs(home_win_prob - 0.5) > 0.15
                                  else "Medium" if abs(home_win_prob - 0.5) > 0.07
                                  else "Low",
                    "factors": [
                        f"Home field advantage (+4% to {home_info.get('abbreviation', '')})",
                        f"Pythagorean Win%: {home_info.get('abbreviation','')} "
                        f"{pythagorean_win_pct(home_stats['runs_per_game'], home_stats['runs_allowed_per_game']):.3f} vs "
                        f"{away_info.get('abbreviation','')} "
                        f"{pythagorean_win_pct(away_stats['runs_per_game'], away_stats['runs_allowed_per_game']):.3f}",
                        f"Recent form (L10): {home_info.get('abbreviation','')} "
                        f"{home_stats['last10_wins']}-{10 - home_stats['last10_wins']} vs "
                        f"{away_info.get('abbreviation','')} "
                        f"{away_stats['last10_wins']}-{10 - away_stats['last10_wins']}",
                    ],
                },
                "isMock": False,
            }

    # Append betting odds if key supplied
    if odds_key:
        all_odds = fetch_odds(odds_key)
        away_abbr = details["awayTeam"]["abbreviation"]
        home_abbr = details["homeTeam"]["abbreviation"]
        game_odds = all_odds.get(f"{away_abbr}_vs_{home_abbr}") or \
                    all_odds.get(f"{home_abbr}_vs_{away_abbr}")
        details["bettingOdds"] = game_odds
    else:
        details["bettingOdds"] = None

    return jsonify(details)


@app.route("/api/standings")
def api_standings():
    season = request.args.get("season", datetime.now().year)
    data = fetch_standings(int(season))
    if not data:
        # Build from mock
        data = {
            tid: {
                "wins": s["wins"],
                "losses": s["losses"],
                "pct": round(s["wins"] / (s["wins"] + s["losses"]), 3),
                "gb": "-",
            }
            for tid, s in MOCK_TEAM_STATS.items()
        }
    return jsonify({"standings": data, "season": season})


if __name__ == "__main__":
    import os
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(debug=debug, host="0.0.0.0", port=5000)
