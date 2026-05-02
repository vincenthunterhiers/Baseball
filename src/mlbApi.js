const MLB_BASE_URL = "https://statsapi.mlb.com/api/v1";

export async function fetchGamesForDate(date) {
  const schedule = await getJson(
    `${MLB_BASE_URL}/schedule?sportId=1&date=${encodeURIComponent(date)}&hydrate=team,venue,probablePitcher`,
  );

  return (schedule.dates?.[0]?.games ?? []).map((game) => ({
    id: game.gamePk,
    status: game.status?.detailedState ?? "Scheduled",
    dateTime: game.gameDate,
    venue: game.venue?.name ?? "Venue TBD",
    away: {
      id: game.teams.away.team.id,
      name: game.teams.away.team.name,
      probablePitcher: game.teams.away.probablePitcher ?? null,
    },
    home: {
      id: game.teams.home.team.id,
      name: game.teams.home.team.name,
      probablePitcher: game.teams.home.probablePitcher ?? null,
    },
  }));
}

export async function enrichGame(game, date) {
  const season = date.slice(0, 4);
  const [awayStats, homeStats, awayPitcher, homePitcher] = await Promise.all([
    fetchTeamSnapshot(game.away.id, date),
    fetchTeamSnapshot(game.home.id, date),
    fetchPitcherSnapshot(game.away.probablePitcher?.id, season),
    fetchPitcherSnapshot(game.home.probablePitcher?.id, season),
  ]);

  return {
    ...game,
    season,
    away: {
      ...game.away,
      stats: awayStats,
      probablePitcher: {
        name: game.away.probablePitcher?.fullName ?? "TBD",
        ...awayPitcher,
      },
    },
    home: {
      ...game.home,
      stats: homeStats,
      probablePitcher: {
        name: game.home.probablePitcher?.fullName ?? "TBD",
        ...homePitcher,
      },
    },
  };
}

export async function fetchRosterPlayerStats(teamId, season = new Date().getFullYear()) {
  const roster = await getJson(`${MLB_BASE_URL}/teams/${teamId}/roster?rosterType=active`);
  const players = roster.roster ?? [];

  const snapshots = await Promise.all(
    players.map(async (entry) => {
      const person = entry.person;
      const group = entry.position?.type === "Pitcher" ? "pitching" : "hitting";
      const stats = await fetchPersonSeasonStats(person.id, group, season);

      return {
        id: person.id,
        name: person.fullName,
        position: entry.position?.abbreviation ?? "",
        group,
        stats,
      };
    }),
  );

  return snapshots;
}

async function fetchTeamSnapshot(teamId, date) {
  const season = date.slice(0, 4);
  const [record, hitting, pitching, recentSchedule] = await Promise.all([
    getJson(`${MLB_BASE_URL}/standings?leagueId=103,104&season=${season}`),
    getJson(`${MLB_BASE_URL}/teams/${teamId}/stats?stats=season&group=hitting&season=${season}`),
    getJson(`${MLB_BASE_URL}/teams/${teamId}/stats?stats=season&group=pitching&season=${season}`),
    getJson(
      `${MLB_BASE_URL}/schedule?sportId=1&teamId=${teamId}&endDate=${encodeURIComponent(
        date,
      )}&startDate=${encodeURIComponent(previousDate(date, 14))}`,
    ),
  ]);

  const standing = findTeamStanding(record.records, teamId);
  const hittingStats = hitting.stats?.[0]?.splits?.[0]?.stat ?? {};
  const pitchingStats = pitching.stats?.[0]?.splits?.[0]?.stat ?? {};

  return {
    wins: Number(standing?.wins ?? 0),
    losses: Number(standing?.losses ?? 0),
    winPct: Number(standing?.winningPercentage ?? 0),
    runsPerGame: perGame(hittingStats.runs, hittingStats.gamesPlayed),
    runsAllowedPerGame: perGame(pitchingStats.runs, pitchingStats.gamesPlayed),
    ops: Number(hittingStats.ops ?? 0),
    era: Number(pitchingStats.era ?? 0),
    whip: Number(pitchingStats.whip ?? 0),
    recentRunDifferential: recentRunDifferential(recentSchedule.dates ?? [], teamId),
  };
}

async function fetchPitcherSnapshot(personId, season) {
  if (!personId) {
    return { era: 4.25, whip: 1.3, summary: "Probable pitcher has not been announced." };
  }

  const stats = await fetchPersonSeasonStats(personId, "pitching", season);

  return {
    era: Number(stats.era ?? 4.25),
    whip: Number(stats.whip ?? 1.3),
    summary: `${stats.wins ?? 0}-${stats.losses ?? 0}, ${stats.era ?? "N/A"} ERA, ${stats.whip ?? "N/A"} WHIP`,
  };
}

async function fetchPersonSeasonStats(personId, group, season = new Date().getFullYear()) {
  const payload = await getJson(
    `${MLB_BASE_URL}/people/${personId}/stats?stats=season&group=${group}&season=${season}`,
  );

  return payload.stats?.[0]?.splits?.[0]?.stat ?? {};
}

function findTeamStanding(records = [], teamId) {
  for (const division of records) {
    const found = division.teamRecords?.find((record) => record.team.id === teamId);
    if (found) {
      return found;
    }
  }

  return null;
}

function recentRunDifferential(dates, teamId) {
  let differential = 0;
  let games = 0;

  for (const date of dates) {
    for (const game of date.games ?? []) {
      const away = game.teams?.away;
      const home = game.teams?.home;

      if (away?.score == null || home?.score == null) {
        continue;
      }

      if (away.team.id === teamId) {
        differential += away.score - home.score;
        games += 1;
      }

      if (home.team.id === teamId) {
        differential += home.score - away.score;
        games += 1;
      }
    }
  }

  return games === 0 ? 0 : differential / games;
}

function perGame(total, games) {
  const totalNumber = Number(total);
  const gameNumber = Number(games);
  return gameNumber > 0 ? totalNumber / gameNumber : 0;
}

function previousDate(date, daysBack) {
  const value = new Date(`${date}T12:00:00Z`);
  value.setUTCDate(value.getUTCDate() - daysBack);
  return value.toISOString().slice(0, 10);
}

async function getJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`MLB API request failed (${response.status}) for ${url}`);
  }

  return response.json();
}
