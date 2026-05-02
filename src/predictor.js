const PCT_WEIGHT = 42;
const OPS_WEIGHT = 38;
const ERA_WEIGHT = 28;
const RECENT_WEIGHT = 18;
const PITCHER_WEIGHT = 24;
const HOME_FIELD_ADVANTAGE = 3.5;
const MARKET_WEIGHT = 14;

export function normalizeTeamStats(stats = {}) {
  return {
    winPct: numberOrZero(stats.winPct),
    runsPerGame: numberOrZero(stats.runsPerGame),
    runsAllowedPerGame: numberOrZero(stats.runsAllowedPerGame),
    ops: numberOrZero(stats.ops),
    era: numberOrZero(stats.era),
    whip: numberOrZero(stats.whip),
    recentRunDifferential: numberOrZero(stats.recentRunDifferential),
  };
}

export function impliedProbability(americanOdds) {
  const odds = Number(americanOdds);
  if (!Number.isFinite(odds) || odds === 0) {
    return null;
  }

  if (odds < 0) {
    return Math.abs(odds) / (Math.abs(odds) + 100);
  }

  return 100 / (odds + 100);
}

export function averageImpliedProbability(bookmakers = [], teamName) {
  const probabilities = [];

  for (const bookmaker of bookmakers) {
    for (const market of bookmaker.markets ?? []) {
      if (market.key !== "h2h") {
        continue;
      }

      for (const outcome of market.outcomes ?? []) {
        if (sameTeamName(outcome.name, teamName)) {
          const probability = impliedProbability(outcome.price);
          if (probability !== null) {
            probabilities.push(probability);
          }
        }
      }
    }
  }

  if (probabilities.length === 0) {
    return null;
  }

  return probabilities.reduce((sum, value) => sum + value, 0) / probabilities.length;
}

export function predictGame({ awayTeam, homeTeam, odds }) {
  const away = normalizeTeamStats(awayTeam.stats);
  const home = normalizeTeamStats(homeTeam.stats);
  const awayPitcher = normalizePitcherStats(awayTeam.probablePitcher);
  const homePitcher = normalizePitcherStats(homeTeam.probablePitcher);
  const awayMarket = odds ? averageImpliedProbability(odds.bookmakers, awayTeam.name) : null;
  const homeMarket = odds ? averageImpliedProbability(odds.bookmakers, homeTeam.name) : null;

  const awayScore =
    teamScore(away, home, awayPitcher, homePitcher) +
    marketScore(awayMarket, homeMarket);

  const homeScore =
    teamScore(home, away, homePitcher, awayPitcher) +
    HOME_FIELD_ADVANTAGE +
    marketScore(homeMarket, awayMarket);

  const spread = homeScore - awayScore;
  const winner = spread >= 0 ? homeTeam.name : awayTeam.name;
  const confidence = Math.min(88, Math.max(52, 50 + Math.abs(spread) * 0.9));

  return {
    winner,
    confidence,
    awayScore,
    homeScore,
    factors: buildFactors({
      awayTeam,
      homeTeam,
      away,
      home,
      awayPitcher,
      homePitcher,
      awayMarket,
      homeMarket,
      spread,
    }),
  };
}

export function sameTeamName(left, right) {
  return compactName(left) === compactName(right);
}

function teamScore(team, opponent, pitcher, opponentPitcher) {
  return (
    team.winPct * PCT_WEIGHT +
    (team.ops - opponent.ops) * OPS_WEIGHT +
    (opponent.era - team.era) * ERA_WEIGHT +
    (team.runsPerGame - opponent.runsAllowedPerGame) * 4 +
    team.recentRunDifferential * RECENT_WEIGHT +
    (opponentPitcher.era - pitcher.era) * PITCHER_WEIGHT +
    (opponentPitcher.whip - pitcher.whip) * 14
  );
}

function marketScore(teamProbability, opponentProbability) {
  if (teamProbability === null || opponentProbability === null) {
    return 0;
  }

  return (teamProbability - opponentProbability) * MARKET_WEIGHT;
}

function normalizePitcherStats(pitcher = {}) {
  return {
    era: numberOrFallback(pitcher.era, 4.25),
    whip: numberOrFallback(pitcher.whip, 1.3),
  };
}

function buildFactors({
  awayTeam,
  homeTeam,
  away,
  home,
  awayPitcher,
  homePitcher,
  awayMarket,
  homeMarket,
  spread,
}) {
  const leadingTeam = spread >= 0 ? homeTeam.name : awayTeam.name;
  const trailingTeam = spread >= 0 ? awayTeam.name : homeTeam.name;
  const leadingStats = spread >= 0 ? home : away;
  const trailingStats = spread >= 0 ? away : home;
  const leadingPitcher = spread >= 0 ? homePitcher : awayPitcher;
  const trailingPitcher = spread >= 0 ? awayPitcher : homePitcher;

  const factors = [
    `${leadingTeam} rates ahead of ${trailingTeam} by ${Math.abs(spread).toFixed(1)} model points.`,
    `${leadingTeam} win percentage: ${(leadingStats.winPct * 100).toFixed(1)}% vs ${(trailingStats.winPct * 100).toFixed(1)}%.`,
    `${leadingTeam} run prevention edge: ${leadingStats.runsAllowedPerGame.toFixed(2)} allowed/game vs ${trailingStats.runsAllowedPerGame.toFixed(2)}.`,
    `Probable pitcher comparison: ${leadingPitcher.era.toFixed(2)} ERA / ${leadingPitcher.whip.toFixed(2)} WHIP vs ${trailingPitcher.era.toFixed(2)} ERA / ${trailingPitcher.whip.toFixed(2)} WHIP.`,
  ];

  if (awayMarket !== null && homeMarket !== null) {
    factors.push(
      `Average market implied probabilities: ${awayTeam.name} ${(awayMarket * 100).toFixed(1)}%, ${homeTeam.name} ${(homeMarket * 100).toFixed(1)}%.`,
    );
  }

  return factors;
}

function compactName(value = "") {
  return String(value).toLowerCase().replace(/[^a-z0-9]/g, "");
}

function numberOrZero(value) {
  return numberOrFallback(value, 0);
}

function numberOrFallback(value, fallback) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}
