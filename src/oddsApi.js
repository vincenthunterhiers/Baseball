const ODDS_BASE_URL = "https://api.the-odds-api.com/v4";

export async function fetchMlbOdds(apiKey) {
  if (!apiKey) {
    return [];
  }

  const params = new URLSearchParams({
    apiKey,
    regions: "us",
    markets: "h2h",
    oddsFormat: "american",
    dateFormat: "iso",
  });

  const response = await fetch(`${ODDS_BASE_URL}/sports/baseball_mlb/odds?${params}`);
  if (!response.ok) {
    throw new Error(`Odds API request failed (${response.status}).`);
  }

  return response.json();
}

export function matchOddsToGame(oddsEvents, game) {
  return oddsEvents.find((event) => {
    const teams = event.home_team && event.away_team ? [event.home_team, event.away_team] : event.teams ?? [];
    return teams.some((name) => sameCompactName(name, game.home.name)) &&
      teams.some((name) => sameCompactName(name, game.away.name));
  }) ?? null;
}

function sameCompactName(left, right) {
  return compactName(left).endsWith(compactName(right)) ||
    compactName(right).endsWith(compactName(left)) ||
    compactName(left) === compactName(right);
}

function compactName(value = "") {
  return String(value).toLowerCase().replace(/[^a-z0-9]/g, "");
}
