from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text()


class StaticAppTests(unittest.TestCase):
    def test_app_entrypoint_and_module_files_exist(self):
        self.assertTrue((ROOT / "index.html").exists())
        self.assertTrue((ROOT / "src/app.js").exists())
        self.assertTrue((ROOT / "src/mlbApi.js").exists())
        self.assertTrue((ROOT / "src/oddsApi.js").exists())
        self.assertTrue((ROOT / "src/predictor.js").exists())
        self.assertTrue((ROOT / "src/styles.css").exists())

    def test_index_loads_module_script_and_required_controls(self):
        html = read("index.html")

        self.assertIn('type="module" src="./src/app.js"', html)
        self.assertIn('id="game-date"', html)
        self.assertIn('id="odds-key"', html)
        self.assertIn('id="games"', html)
        self.assertIn('id="game-card-template"', html)

    def test_mlb_api_uses_public_stats_endpoints(self):
        source = read("src/mlbApi.js")

        self.assertIn("https://statsapi.mlb.com/api/v1", source)
        self.assertIn("schedule?sportId=1", source)
        self.assertIn("roster?rosterType=active", source)
        self.assertIn("stats?stats=season&group=hitting", source)
        self.assertIn("stats?stats=season&group=pitching", source)

    def test_odds_api_supports_optional_moneyline_lookup(self):
        source = read("src/oddsApi.js")
        app_source = read("src/app.js")

        self.assertIn("api.the-odds-api.com", source)
        self.assertIn("sports/baseball_mlb/odds", source)
        self.assertIn('markets: "h2h"', source)
        self.assertIn('oddsFormat: "american"', source)
        self.assertIn("fetchMlbOdds(oddsKey)", app_source)

    def test_prediction_model_includes_core_metrics(self):
        source = read("src/predictor.js")

        for metric in [
            "winPct",
            "ops",
            "era",
            "whip",
            "recentRunDifferential",
            "HOME_FIELD_ADVANTAGE",
            "averageImpliedProbability",
        ]:
            self.assertIn(metric, source)

