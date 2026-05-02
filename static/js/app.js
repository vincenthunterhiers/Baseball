/* ============================================================
   Baseball Predictor — Frontend JavaScript
   ============================================================ */

'use strict';

// ---- State ----
let currentDate = '';
let currentGames = [];
// Odds API key is kept only in memory (never persisted to browser storage).
let oddsApiKey = '';
let gameModal = null;

// ---- Init ----
document.addEventListener('DOMContentLoaded', () => {
  const picker = document.getElementById('datePicker');
  currentDate = picker.value;

  gameModal = new bootstrap.Modal(document.getElementById('gameModal'));

  // Restore odds key (kept in memory only, not persisted)
  // Nothing to restore — user re-enters it each session

  // Bind controls
  picker.addEventListener('change', () => {
    currentDate = picker.value;
    loadGames();
  });

  document.getElementById('prevDay').addEventListener('click', () => shiftDate(-1));
  document.getElementById('nextDay').addEventListener('click', () => shiftDate(1));
  document.getElementById('todayBtn').addEventListener('click', () => {
    const today = new Date().toISOString().slice(0, 10);
    picker.value = today;
    currentDate = today;
    loadGames();
  });

  document.getElementById('saveOddsKey').addEventListener('click', () => {
    oddsApiKey = document.getElementById('oddsApiKey').value.trim();
    showToast('Odds API key set for this session!');
  });

  loadGames();
});

// ---- Date helpers ----
function shiftDate(days) {
  const picker = document.getElementById('datePicker');
  const d = new Date(picker.value + 'T12:00:00'); // noon avoids DST-edge date shifts
  d.setDate(d.getDate() + days);
  const iso = d.toISOString().slice(0, 10);
  picker.value = iso;
  currentDate = iso;
  loadGames();
}

// ---- Load games ----
async function loadGames() {
  showLoading(true);
  hideEmpty();
  document.getElementById('gamesGrid').innerHTML = '';

  try {
    const res = await fetch(`/api/games?date=${currentDate}`);
    const data = await res.json();

    currentGames = data.games || [];
    showLoading(false);
    renderSourceBadge(data.source);

    if (currentGames.length === 0) {
      showEmpty();
      return;
    }

    renderGames(currentGames);
  } catch (err) {
    showLoading(false);
    showError('Failed to load games. Please try again.');
    console.error(err);
  }
}

// ---- Render game cards ----
function renderGames(games) {
  const grid = document.getElementById('gamesGrid');
  grid.innerHTML = '';

  games.forEach(game => {
    const card = createGameCard(game);
    grid.appendChild(card);
    // Trigger prediction load asynchronously so cards appear immediately
    loadGamePrediction(game.gamePk, card);
  });
}

function createGameCard(game) {
  const col = document.createElement('div');
  col.className = 'game-card';
  col.setAttribute('data-game-pk', game.gamePk);

  const timeStr = formatTime(game.gameTime);
  const awayAbbr = game.awayTeam?.abbreviation || '???';
  const homeAbbr = game.homeTeam?.abbreviation || '???';
  const awayName = game.awayTeam?.name || '';
  const homeName = game.homeTeam?.name || '';
  const venue = game.venue || '';
  const series = game.seriesDescription || 'MLB';

  col.innerHTML = `
    <div class="card-header-bar">
      <span class="card-series">${escHtml(series)}</span>
      <span class="card-time"><i class="fa fa-clock fa-xs me-1"></i>${escHtml(timeStr)}</span>
    </div>
    <div class="card-body-inner">
      <div class="teams-row">
        <div class="team-block">
          <div class="team-abbr">${escHtml(awayAbbr)}</div>
          <div class="team-name">${escHtml(awayName)}</div>
          <div class="team-record" id="rec-away-${game.gamePk}"></div>
        </div>
        <div class="vs-divider">@</div>
        <div class="team-block">
          <div class="team-abbr">${escHtml(homeAbbr)}</div>
          <div class="team-name">${escHtml(homeName)}</div>
          <div class="team-record" id="rec-home-${game.gamePk}"></div>
        </div>
      </div>

      ${venue ? `
      <div class="card-venue">
        <i class="fa fa-map-marker-alt fa-xs"></i>
        <span>${escHtml(venue)}</span>
      </div>` : ''}

      <div class="prob-section" id="prob-${game.gamePk}">
        <div class="prob-labels">
          <span class="prob-label-away">${escHtml(awayAbbr)}</span>
          <span style="font-size:.65rem;color:var(--text-muted);">Win Probability</span>
          <span class="prob-label-home">${escHtml(homeAbbr)}</span>
        </div>
        <div class="prob-bar">
          <div class="prob-away-fill" id="bar-away-${game.gamePk}" style="width:50%"></div>
          <div class="prob-home-fill" id="bar-home-${game.gamePk}" style="width:50%"></div>
        </div>
        <div class="prob-pcts">
          <span id="pct-away-${game.gamePk}">–</span>
          <span id="pct-home-${game.gamePk}">–</span>
        </div>
      </div>

      <button class="btn-details" onclick="openGameModal(${game.gamePk})">
        <i class="fa fa-chart-bar me-1"></i>Full Stats &amp; Analysis
      </button>
    </div>
  `;

  return col;
}

async function loadGamePrediction(gamePk, card) {
  try {
    const keyParam = oddsApiKey ? `&oddsApiKey=${encodeURIComponent(oddsApiKey)}` : '';
    const res = await fetch(`/api/game/${gamePk}/details?date=${currentDate}${keyParam}`);
    const details = await res.json();
    if (!details.prediction) return;

    const pred = details.prediction;
    const awayPct = Math.round(pred.awayWinProbability * 100);
    const homePct = Math.round(pred.homeWinProbability * 100);

    // Win probability bars
    const barAway = document.getElementById(`bar-away-${gamePk}`);
    const barHome = document.getElementById(`bar-home-${gamePk}`);
    if (barAway) barAway.style.width = awayPct + '%';
    if (barHome) barHome.style.width = homePct + '%';

    const pctAway = document.getElementById(`pct-away-${gamePk}`);
    const pctHome = document.getElementById(`pct-home-${gamePk}`);
    if (pctAway) pctAway.textContent = awayPct + '%';
    if (pctHome) pctHome.textContent = homePct + '%';

    // Records
    const recAway = document.getElementById(`rec-away-${gamePk}`);
    const recHome = document.getElementById(`rec-home-${gamePk}`);
    if (recAway && details.awayTeam?.record) recAway.textContent = details.awayTeam.record;
    if (recHome && details.homeTeam?.record) recHome.textContent = details.homeTeam.record;
  } catch (err) {
    console.warn('Could not load prediction for game', gamePk, err);
  }
}

// ---- Modal ----
async function openGameModal(gamePk) {
  document.getElementById('modalTitle').textContent = 'Loading…';
  document.getElementById('modalBody').innerHTML = `
    <div class="text-center py-5">
      <div class="spinner-border text-warning"></div>
    </div>`;
  gameModal.show();

  try {
    const keyParam = oddsApiKey ? `&oddsApiKey=${encodeURIComponent(oddsApiKey)}` : '';
    const res = await fetch(`/api/game/${gamePk}/details?date=${currentDate}${keyParam}`);
    const details = await res.json();
    renderModal(details);
  } catch (err) {
    document.getElementById('modalBody').innerHTML = `
      <div class="alert alert-danger">Failed to load game details.</div>`;
    console.error(err);
  }
}

function renderModal(d) {
  const away = d.awayTeam;
  const home = d.homeTeam;
  const pred = d.prediction;

  document.getElementById('modalTitle').textContent =
    `${away.abbreviation} @ ${home.abbreviation} — ${d.gameDate && d.gameDate !== 'TBD' ? d.gameDate : currentDate}`;

  const homeWinPct = Math.round(pred.homeWinProbability * 100);
  const awayWinPct = Math.round(pred.awayWinProbability * 100);
  const confClass = `confidence-${pred.confidence.toLowerCase()}`;

  const mockNotice = d.isMock ? `
    <div class="mock-notice">
      <i class="fa fa-database"></i>
      Showing sample data — live MLB API unavailable or no games found for this date.
    </div>` : '';

  const factorsHtml = (pred.factors || []).map(f => `<li>${escHtml(f)}</li>`).join('');

  // Pitchers
  const pitchersHtml = renderPitchers(away, home);

  // Team stats comparison
  const teamStatsHtml = renderTeamStats(away, home);

  // Player tables
  const awayPlayersHtml = renderPlayersTable(away.players || []);
  const homePlayersHtml = renderPlayersTable(home.players || []);

  // Odds section
  const oddsHtml = renderOdds(d.bettingOdds, away, home);

  document.getElementById('modalBody').innerHTML = `
    ${mockNotice}

    <!-- Matchup header -->
    <div class="modal-matchup">
      <div class="modal-team">
        <div class="modal-team-abbr">${escHtml(away.abbreviation)}</div>
        <div class="modal-team-name">${escHtml(away.name)}</div>
        <div class="modal-team-record">${escHtml(away.record || '')}</div>
      </div>
      <div class="modal-vs">@</div>
      <div class="modal-team">
        <div class="modal-team-abbr">${escHtml(home.abbreviation)}</div>
        <div class="modal-team-name">${escHtml(home.name)}</div>
        <div class="modal-team-record">${escHtml(home.record || '')}</div>
      </div>
    </div>
    <div class="modal-meta">
      ${d.venue ? `<span><i class="fa fa-map-marker-alt fa-xs"></i>${escHtml(d.venue)}</span>` : ''}
      ${d.gameTime ? `<span><i class="fa fa-clock fa-xs"></i>${escHtml(formatTime(d.gameTime))}</span>` : ''}
      ${d.status && d.status !== 'Scheduled' ? `<span><i class="fa fa-circle fa-xs text-success"></i>${escHtml(d.status)}</span>` : ''}
    </div>

    <!-- Nav tabs -->
    <ul class="nav nav-tabs mt-3 mb-3" id="detailTabs" role="tablist">
      <li class="nav-item">
        <a class="nav-link active" data-bs-toggle="tab" href="#tab-prediction" role="tab">
          <i class="fa fa-brain me-1"></i>Prediction
        </a>
      </li>
      <li class="nav-item">
        <a class="nav-link" data-bs-toggle="tab" href="#tab-team-stats" role="tab">
          <i class="fa fa-chart-bar me-1"></i>Team Stats
        </a>
      </li>
      <li class="nav-item">
        <a class="nav-link" data-bs-toggle="tab" href="#tab-away-roster" role="tab">
          <i class="fa fa-users me-1"></i>${escHtml(away.abbreviation)} Roster
        </a>
      </li>
      <li class="nav-item">
        <a class="nav-link" data-bs-toggle="tab" href="#tab-home-roster" role="tab">
          <i class="fa fa-users me-1"></i>${escHtml(home.abbreviation)} Roster
        </a>
      </li>
      ${d.bettingOdds ? `
      <li class="nav-item">
        <a class="nav-link" data-bs-toggle="tab" href="#tab-odds" role="tab">
          <i class="fa fa-dollar-sign me-1"></i>Odds
        </a>
      </li>` : ''}
    </ul>

    <div class="tab-content">

      <!-- PREDICTION TAB -->
      <div class="tab-pane fade show active" id="tab-prediction" role="tabpanel">
        <div class="prediction-box">
          <div class="prediction-title">
            <i class="fa fa-brain"></i> Win Prediction
          </div>
          <div class="prediction-favored">
            Favored: <span class="favored-team">${escHtml(pred.favored)}</span>
            <span class="confidence-badge ${confClass}">${escHtml(pred.confidence)} Confidence</span>
          </div>

          <div class="big-prob-bar">
            <div class="big-away-fill" style="width:${awayWinPct}%">${awayWinPct}%</div>
            <div class="big-home-fill" style="width:${homeWinPct}%">${homeWinPct}%</div>
          </div>
          <div class="prob-team-labels">
            <span>${escHtml(away.name)} (Away)</span>
            <span>${escHtml(home.name)} (Home)</span>
          </div>

          <ul class="prediction-factors mt-2 mb-0">
            ${factorsHtml}
          </ul>
        </div>

        ${pitchersHtml}
      </div>

      <!-- TEAM STATS TAB -->
      <div class="tab-pane fade" id="tab-team-stats" role="tabpanel">
        ${teamStatsHtml}
      </div>

      <!-- AWAY ROSTER TAB -->
      <div class="tab-pane fade" id="tab-away-roster" role="tabpanel">
        <div class="stats-section">
          <div class="stats-section-title">
            <i class="fa fa-users"></i>${escHtml(away.name)} — Active Roster (Hitters)
          </div>
          ${awayPlayersHtml}
        </div>
      </div>

      <!-- HOME ROSTER TAB -->
      <div class="tab-pane fade" id="tab-home-roster" role="tabpanel">
        <div class="stats-section">
          <div class="stats-section-title">
            <i class="fa fa-users"></i>${escHtml(home.name)} — Active Roster (Hitters)
          </div>
          ${homePlayersHtml}
        </div>
      </div>

      ${d.bettingOdds ? `
      <!-- ODDS TAB -->
      <div class="tab-pane fade" id="tab-odds" role="tabpanel">
        ${oddsHtml}
      </div>` : ''}

    </div>
  `;
}

function renderPitchers(away, home) {
  const ap = away.probablePitcher;
  const hp = home.probablePitcher;
  if (!ap && !hp) return '';

  const pitcherCard = (p, label) => {
    if (!p) return `<div class="pitcher-card"><div class="pitcher-card-label">${label}</div><div class="pitcher-name text-muted">TBD</div></div>`;
    return `
      <div class="pitcher-card">
        <div class="pitcher-card-label">${label}</div>
        <div class="pitcher-name">${escHtml(p.name)}</div>
        <div class="pitcher-stat-row">
          <div class="pitcher-stat"><span class="label">ERA</span><span class="val">${fmt(p.era)}</span></div>
          <div class="pitcher-stat"><span class="label">WHIP</span><span class="val">${fmt(p.whip)}</span></div>
          <div class="pitcher-stat"><span class="label">K/9</span><span class="val">${fmt(p.k_per_9)}</span></div>
          <div class="pitcher-stat"><span class="label">W-L</span><span class="val">${p.wins ?? '?'}-${p.losses ?? '?'}</span></div>
          ${p.hand ? `<div class="pitcher-stat"><span class="label">Hand</span><span class="val">${escHtml(p.hand)}</span></div>` : ''}
        </div>
      </div>`;
  };

  return `
    <div class="stats-section">
      <div class="stats-section-title"><i class="fa fa-baseball-bat-ball"></i>Probable Pitchers</div>
      <div class="pitcher-cards">
        ${pitcherCard(ap, `${escHtml(away.abbreviation)} (Away)`)}
        ${pitcherCard(hp, `${escHtml(home.abbreviation)} (Home)`)}
      </div>
    </div>`;
}

function renderTeamStats(away, home) {
  const as = away.stats || {};
  const hs = home.stats || {};

  const row = (label, awayVal, homeVal, lowerIsBetter = false, decimals = 2) => {
    const av = parseFloat(awayVal);
    const hv = parseFloat(homeVal);
    let awayClass = '', homeClass = '';
    if (!isNaN(av) && !isNaN(hv) && av !== hv) {
      const awayBetter = lowerIsBetter ? av < hv : av > hv;
      awayClass = awayBetter ? 'stat-better' : 'stat-worse';
      homeClass = awayBetter ? 'stat-worse' : 'stat-better';
    }
    return `
      <div class="stat-row-away ${awayClass}">${fmt(awayVal, decimals)}</div>
      <div class="stat-row-label">${label}</div>
      <div class="stat-row-home ${homeClass}">${fmt(homeVal, decimals)}</div>`;
  };

  return `
    <div class="stats-section">
      <div class="stats-section-title"><i class="fa fa-bat"></i>Hitting</div>
      <div class="stats-compare-grid" style="margin-bottom:.3rem">
        <div class="stat-row-away" style="font-size:.68rem;color:var(--text-muted);text-align:right;font-weight:600">${escHtml(away.abbreviation)}</div>
        <div class="stat-row-label"></div>
        <div class="stat-row-home" style="font-size:.68rem;color:var(--text-muted);font-weight:600">${escHtml(home.abbreviation)}</div>
      </div>
      <div class="stats-compare-grid">
        ${row('AVG', as.batting_avg, hs.batting_avg, false, 3)}
        ${row('OBP', as.obp, hs.obp, false, 3)}
        ${row('SLG', as.slg, hs.slg, false, 3)}
        ${row('OPS', as.ops, hs.ops, false, 3)}
        ${row('R/G', as.runs_per_game, hs.runs_per_game)}
      </div>
    </div>

    <div class="stats-section">
      <div class="stats-section-title"><i class="fa fa-fire"></i>Pitching</div>
      <div class="stats-compare-grid">
        ${row('ERA', as.era, hs.era, true)}
        ${row('WHIP', as.whip, hs.whip, true)}
        ${row('K/9', as.k_per_9, hs.k_per_9)}
        ${row('RA/G', as.runs_allowed_per_game, hs.runs_allowed_per_game, true)}
      </div>
    </div>

    <div class="stats-section">
      <div class="stats-section-title"><i class="fa fa-trophy"></i>Season Record</div>
      <div class="stats-compare-grid">
        ${row('Wins', as.wins, hs.wins)}
        ${row('Losses', as.losses, hs.losses, true)}
        ${row('L10 W', as.last10_wins, hs.last10_wins)}
      </div>
    </div>`;
}

function renderPlayersTable(players) {
  if (!players || players.length === 0) {
    return '<p class="text-muted" style="font-size:.8rem">No player data available.</p>';
  }

  const rows = players.map(p => {
    const avg = fmt(p.avg, 3);
    const obp = fmt(p.obp, 3);
    const slg = fmt(p.slg, 3);
    const ops = (parseFloat(p.obp) + parseFloat(p.slg)).toFixed(3);
    return `
      <tr>
        <td>
          <span class="pos-badge">${escHtml(p.position || '?')}</span>
          ${escHtml(p.name)}
        </td>
        <td>${avg}</td>
        <td>${obp}</td>
        <td>${slg}</td>
        <td>${ops}</td>
        <td>${p.hr ?? '—'}</td>
        <td>${p.rbi ?? '—'}</td>
      </tr>`;
  }).join('');

  return `
    <table class="players-table">
      <thead>
        <tr>
          <th>Player</th>
          <th>AVG</th>
          <th>OBP</th>
          <th>SLG</th>
          <th>OPS</th>
          <th>HR</th>
          <th>RBI</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>`;
}

function renderOdds(oddsData, away, home) {
  if (!oddsData || !oddsData.bookmakers || oddsData.bookmakers.length === 0) {
    return `<p class="text-muted" style="font-size:.82rem;padding:.5rem 0">
      No odds data available. Enter your Odds API key above to see live betting lines.
    </p>`;
  }

  const rows = oddsData.bookmakers.map(bm => {
    const aml = bm.awayMoneyline;
    const hml = bm.homeMoneyline;
    const aClass = aml >= 0 ? 'ml-positive' : 'ml-negative';
    const hClass = hml >= 0 ? 'ml-positive' : 'ml-negative';
    const amlStr = aml >= 0 ? `+${aml}` : `${aml}`;
    const hmlStr = hml >= 0 ? `+${hml}` : `${hml}`;
    return `
      <tr>
        <td>${escHtml(bm.bookmaker)}</td>
        <td class="${aClass}">${amlStr}</td>
        <td class="${hClass}">${hmlStr}</td>
        <td>${Math.round(bm.awayImpliedProb * 100)}%</td>
        <td>${Math.round((bm.homeImpliedProb || 0) * 100)}%</td>
      </tr>`;
  }).join('');

  return `
    <div class="stats-section">
      <div class="stats-section-title">
        <i class="fa fa-dollar-sign"></i>Moneyline Odds
      </div>
      <table class="odds-table">
        <thead>
          <tr>
            <th>Sportsbook</th>
            <th>${escHtml(away.abbreviation)} ML</th>
            <th>${escHtml(home.abbreviation)} ML</th>
            <th>${escHtml(away.abbreviation)} Impl. Prob.</th>
            <th>${escHtml(home.abbreviation)} Impl. Prob.</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

// ---- UI helpers ----
function renderSourceBadge(source) {
  const badge = document.getElementById('sourceBadge');
  badge.classList.remove('d-none', 'live', 'mock');
  if (source === 'live') {
    badge.classList.add('live');
    badge.innerHTML = '<i class="fa fa-circle fa-xs"></i> Live MLB Data';
  } else {
    badge.classList.add('mock');
    badge.innerHTML = '<i class="fa fa-database fa-xs"></i> Sample Data (MLB API unavailable)';
  }
}

function showLoading(show) {
  const el = document.getElementById('loadingState');
  el.classList.toggle('d-none', !show);
}

function showEmpty() {
  document.getElementById('emptyState').classList.remove('d-none');
}

function hideEmpty() {
  document.getElementById('emptyState').classList.add('d-none');
}

function showError(msg) {
  const grid = document.getElementById('gamesGrid');
  grid.innerHTML = `<div class="alert alert-danger">${escHtml(msg)}</div>`;
}

function showToast(msg) {
  const existing = document.getElementById('appToast');
  if (existing) existing.remove();

  const toast = document.createElement('div');
  toast.id = 'appToast';
  toast.style.cssText = `
    position:fixed;bottom:1.5rem;right:1.5rem;
    background:var(--green);color:#fff;
    padding:.6rem 1.2rem;border-radius:8px;
    font-size:.82rem;font-weight:600;
    z-index:9999;box-shadow:0 4px 12px rgba(0,0,0,.4);
    animation:fadeIn .2s ease;
  `;
  toast.textContent = msg;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 2500);
}

// ---- Formatting helpers ----
function fmt(val, decimals = 2) {
  if (val === null || val === undefined) return '—';
  const n = parseFloat(val);
  if (isNaN(n)) return String(val);
  return n.toFixed(decimals);
}

function formatTime(timeStr) {
  if (!timeStr) return '';
  // Handle HH:MM format
  const parts = timeStr.split(':');
  if (parts.length < 2) return timeStr;
  let h = parseInt(parts[0], 10);
  const m = parts[1];
  const ampm = h >= 12 ? 'PM' : 'AM';
  h = h % 12 || 12;
  return `${h}:${m} ${ampm} ET`;
}

function escHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
