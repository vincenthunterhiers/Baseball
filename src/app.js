import { enrichGame, fetchGamesForDate, fetchRosterPlayerStats } from "./mlbApi.js";
import { fetchMlbOdds } from "./oddsApi.js";
import { predictGame } from "./predictor.js";

const form = document.querySelector("#search-form");
const dateInput = document.querySelector("#game-date");
const oddsKeyInput = document.querySelector("#odds-key");
const gamesContainer = document.querySelector("#games");
const statusElement = document.querySelector("#status");
const cardTemplate = document.querySelector("#game-card-template");

dateInput.value = new Date().toISOString().slice(0, 10);

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  await loadGames(dateInput.value, oddsKeyInput.value.trim());
});

async function loadGames(date, oddsKey) {
  gamesContainer.innerHTML = "";
  setStatus(`Gathering MLB games for ${formatDate(date)}...`);

  try {
    const games = await fetchGamesForDate(date);
    if (games.length === 0) {
      setStatus(`No MLB games found for ${formatDate(date)}.`);
      return;
    }

    setStatus(`Found ${games.length} game${games.length === 1 ? "" : "s"}. Loading team stats and odds...`);
    const [enrichedGames, odds] = await Promise.all([
      Promise.all(games.map((game) => enrichGame(game, date))),
      oddsKey ? fetchMlbOdds(oddsKey).catch(() => []) : Promise.resolve([]),
    ]);

    renderGames(enrichedGames, odds);
    setStatus(`Loaded ${games.length} game${games.length === 1 ? "" : "s"} for ${formatDate(date)}.`);
  } catch (error) {
    setStatus(error.message, true);
  }
}

function renderGames(games, oddsList) {
  const fragment = document.createDocumentFragment();

  for (const game of games) {
    const gameOdds = oddsList.find((odds) => matchesOddsGame(odds, game));
    const prediction = predictGame({
      awayTeam: game.away,
      homeTeam: game.home,
      odds: gameOdds,
    });

    const card = cardTemplate.content.firstElementChild.cloneNode(true);
    card.querySelector(".game-time").textContent = `${formatDateTime(game.dateTime)} - ${game.status}`;
    card.querySelector(".matchup").textContent = `${game.away.name} at ${game.home.name}`;
    card.querySelector(".venue").textContent = game.venue;
    card.querySelector(".winner").textContent = prediction.winner;
    card.querySelector(".confidence").textContent = `${prediction.confidence.toFixed(0)}% confidence`;

    renderTeamPanel(card.querySelector(".away-panel"), "Away", game.away, prediction.awayScore);
    renderTeamPanel(card.querySelector(".home-panel"), "Home", game.home, prediction.homeScore);
    renderFactors(card.querySelector(".factors"), prediction.factors);
    renderOdds(card.querySelector(".odds"), gameOdds);
    wirePlayerStats(card, game);

    fragment.append(card);
  }

  gamesContainer.replaceChildren(fragment);
}

function renderTeamPanel(panel, label, team, score) {
  panel.querySelector("h3").textContent = `${label}: ${team.name}`;
  panel.querySelector("dl").innerHTML = statRows([
    ["Model score", score.toFixed(1)],
    ["Record", `${team.stats.wins}-${team.stats.losses}`],
    ["Win pct", formatNumber(team.stats.winPct, 3)],
    ["Runs/game", formatNumber(team.stats.runsPerGame, 2)],
    ["Allowed/game", formatNumber(team.stats.runsAllowedPerGame, 2)],
    ["OPS", formatNumber(team.stats.ops, 3)],
    ["Team ERA", formatNumber(team.stats.era, 2)],
    ["Team WHIP", formatNumber(team.stats.whip, 2)],
    ["Recent run diff", formatNumber(team.stats.recentRunDifferential, 2)],
    ["Probable pitcher", team.probablePitcher.name],
    ["Pitcher line", team.probablePitcher.summary],
  ]);
}

function renderFactors(list, factors) {
  list.innerHTML = factors.map((factor) => `<li>${escapeHtml(factor)}</li>`).join("");
}

function renderOdds(container, odds) {
  if (!odds?.bookmakers?.length) {
    container.innerHTML =
      "<p>No odds loaded. Add a The Odds API key to compare sportsbook moneylines.</p>";
    return;
  }

  const rows = odds.bookmakers
    .flatMap((bookmaker) =>
      (bookmaker.markets ?? [])
        .filter((market) => market.key === "h2h")
        .flatMap((market) =>
          (market.outcomes ?? []).map(
            (outcome) =>
              `<tr><td>${escapeHtml(bookmaker.title)}</td><td>${escapeHtml(outcome.name)}</td><td>${escapeHtml(
                outcome.price,
              )}</td></tr>`,
          ),
        ),
    )
    .join("");

  container.innerHTML = `
    <table>
      <thead><tr><th>Book</th><th>Team</th><th>Moneyline</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function wirePlayerStats(card, game) {
  const button = card.querySelector(".load-players");
  const container = card.querySelector(".players");
  button.addEventListener("click", async () => {
    button.disabled = true;
    button.textContent = "Loading player stats...";

    try {
      const [awayPlayers, homePlayers] = await Promise.all([
        fetchRosterPlayerStats(game.away.id, game.season),
        fetchRosterPlayerStats(game.home.id, game.season),
      ]);

      container.innerHTML = `
        ${playerTable(game.away.name, awayPlayers)}
        ${playerTable(game.home.name, homePlayers)}
      `;
      button.textContent = "Refresh active roster stats";
    } catch (error) {
      container.innerHTML = `<p class="error">${escapeHtml(error.message)}</p>`;
      button.textContent = "Try loading player stats again";
    } finally {
      button.disabled = false;
    }
  });
}

function playerTable(teamName, players) {
  const rows = players
    .map((player) => {
      const line =
        player.group === "pitching"
          ? `${player.stats.wins ?? 0}-${player.stats.losses ?? 0}, ERA ${player.stats.era ?? "N/A"}, WHIP ${player.stats.whip ?? "N/A"}`
          : `AVG ${player.stats.avg ?? "N/A"}, OPS ${player.stats.ops ?? "N/A"}, HR ${player.stats.homeRuns ?? "N/A"}`;

      return `<tr><td>${escapeHtml(player.name)}</td><td>${escapeHtml(player.position)}</td><td>${escapeHtml(line)}</td></tr>`;
    })
    .join("");

  return `
    <div class="player-table">
      <h4>${escapeHtml(teamName)}</h4>
      <table>
        <thead><tr><th>Player</th><th>Pos</th><th>Season stats</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
}

function matchesOddsGame(odds, game) {
  const home = odds.home_team ?? "";
  const away = odds.away_team ?? "";
  return teamTokenMatch(home, game.home.name) && teamTokenMatch(away, game.away.name);
}

export function teamTokenMatch(left, right) {
  const compactLeft = String(left).toLowerCase();
  const compactRight = String(right).toLowerCase();
  const rightTokens = compactRight.split(/\s+/);
  return compactLeft === compactRight || rightTokens.some((token) => token.length > 3 && compactLeft.includes(token));
}

function statRows(rows) {
  return rows
    .map(([label, value]) => `<dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd>`)
    .join("");
}

function formatDateTime(value) {
  return new Intl.DateTimeFormat(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  }).format(new Date(value));
}

function formatDate(value) {
  return new Intl.DateTimeFormat(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  }).format(new Date(`${value}T12:00:00`));
}

function formatNumber(value, digits) {
  return Number(value).toFixed(digits);
}

function setStatus(message, isError = false) {
  statusElement.textContent = message;
  statusElement.classList.toggle("error", isError);
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
