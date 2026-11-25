/**
 * IPX bi-weekly 4.0+ Open Play ladder — shared API core
 * Used by Pages Function (/api/ladder) and sync-pinger Worker.
 */

export const SESSION_TITLE_NEEDLE = '4.0+ Open Play';
export const MATCHES_KV_KEY = 'ladder_matches_4_0';
export const STANDINGS_KV_KEY = 'ladder_standings_4_0';

/** Anchor Sunday (America/New_York calendar date) for bi-weekly periods. */
const PERIOD_EPOCH_NY = '2025-01-05';

export function nyDateString(date = new Date()) {
  return date.toLocaleDateString('en-CA', { timeZone: 'America/New_York' });
}

function parseYmd(ymd) {
  const [y, m, d] = String(ymd).split('-').map(Number);
  return { y, m, d };
}

function ymdToUtcNoonMs({ y, m, d }) {
  return Date.UTC(y, m - 1, d, 12, 0, 0);
}

function addDaysYmd(ymd, days) {
  const ms = ymdToUtcNoonMs(parseYmd(ymd)) + days * 86400000;
  const dt = new Date(ms);
  const y = dt.getUTCFullYear();
  const m = String(dt.getUTCMonth() + 1).padStart(2, '0');
  const d = String(dt.getUTCDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

/** Bi-weekly period keyed by its starting Sunday (NY). Resets every other Sunday. */
export function getPeriodInfo(date = new Date()) {
  const todayNy = nyDateString(date);
  const epochMs = ymdToUtcNoonMs(parseYmd(PERIOD_EPOCH_NY));
  const todayMs = ymdToUtcNoonMs(parseYmd(todayNy));
  const daysSinceEpoch = Math.floor((todayMs - epochMs) / 86400000);
  const periodIndex = Math.floor(Math.max(0, daysSinceEpoch) / 14);
  const periodStart = addDaysYmd(PERIOD_EPOCH_NY, periodIndex * 14);
  const periodEnd = addDaysYmd(periodStart, 13); // inclusive Sat before next reset Sunday
  const nextReset = addDaysYmd(periodStart, 14);
  return {
    periodId: periodStart,
    periodStart,
    periodEnd,
    nextResetSunday: nextReset,
    periodIndex
  };
}

export function normalizePlayerId(name) {
  return String(name || '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

export function displayName(name) {
  if (!name) return '';
  return String(name)
    .replace(/([^\W_]+[^\s-]*) */g, (txt) => txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase())
    .trim();
}

export function isLadderSessionTitle(title) {
  return String(title || '').includes(SESSION_TITLE_NEEDLE);
}

/** Validate one game: first to 11, win by 2. Returns winner side 'a'|'b' or null. */
export function validateGameScore(scoreA, scoreB) {
  const a = Number(scoreA);
  const b = Number(scoreB);
  if (!Number.isFinite(a) || !Number.isFinite(b) || a < 0 || b < 0) return null;
  if (!Number.isInteger(a) || !Number.isInteger(b)) return null;
  const max = Math.max(a, b);
  const min = Math.min(a, b);
  if (max < 11) return null;
  if (max - min < 2) return null;
  // Once someone reaches 11+, game ends at win-by-2 (no inflated scores beyond that rule)
  if (max > 11 && max - min !== 2) return null;
  return a > b ? 'a' : 'b';
}

/**
 * games: [{ a: number, b: number }, ...]
 * Best-of-3 implied: first to 2 game wins. Allow 1–3 games.
 */
export function scoreMatch(games) {
  if (!Array.isArray(games) || games.length < 1 || games.length > 3) {
    return { ok: false, error: 'Enter 1–3 game scores (first to 2 game wins).' };
  }
  let winsA = 0;
  let winsB = 0;
  const normalized = [];
  for (let i = 0; i < games.length; i++) {
    const g = games[i] || {};
    const winner = validateGameScore(g.a, g.b);
    if (!winner) {
      return {
        ok: false,
        error: `Game ${i + 1}: invalid score (first to 11, win by 2).`
      };
    }
    if (winner === 'a') winsA += 1;
    else winsB += 1;
    normalized.push({ a: Number(g.a), b: Number(g.b), winner });
    // Stop early if match already decided and extra games provided — still accept if complete
  }
  if (winsA === winsB) {
    return { ok: false, error: 'Match must have a winner (uneven game wins).' };
  }
  if (Math.max(winsA, winsB) < 1) {
    return { ok: false, error: 'Need at least one game won.' };
  }
  // Prefer completed matches (someone reached 2), but allow single-game for v1 flexibility
  const matchWinner = winsA > winsB ? 'a' : 'b';
  return {
    ok: true,
    games: normalized,
    winsA,
    winsB,
    matchWinner
  };
}

export function emptyStanding(player) {
  return {
    playerId: player.playerId,
    name: player.name,
    points: 0,
    matchWins: 0,
    matchLosses: 0,
    gamesWon: 0,
    gamesLost: 0,
    matchesPlayed: 0,
    form: [] // recent W/L, newest last
  };
}

export function recomputeStandings(matches) {
  const byId = {};
  for (const m of matches || []) {
    const teamA = m.teamA || [];
    const teamB = m.teamB || [];
    const ensure = (p) => {
      const id = p.playerId || normalizePlayerId(p.name);
      if (!byId[id]) byId[id] = emptyStanding({ playerId: id, name: p.name || id });
      else if (p.name) byId[id].name = p.name;
      return byId[id];
    };
    teamA.forEach(ensure);
    teamB.forEach(ensure);

    const scored = scoreMatch(m.games || []);
    if (!scored.ok) continue;

    const winners = scored.matchWinner === 'a' ? teamA : teamB;
    const losers = scored.matchWinner === 'a' ? teamB : teamA;

    winners.forEach((p) => {
      const s = ensure(p);
      s.matchWins += 1;
      s.matchesPlayed += 1;
      s.points += 3;
      s.form.push('W');
      if (s.form.length > 5) s.form.shift();
    });
    losers.forEach((p) => {
      const s = ensure(p);
      s.matchLosses += 1;
      s.matchesPlayed += 1;
      s.form.push('L');
      if (s.form.length > 5) s.form.shift();
    });

    scored.games.forEach((g) => {
      const gw = g.winner === 'a' ? teamA : teamB;
      const gl = g.winner === 'a' ? teamB : teamA;
      gw.forEach((p) => {
        const s = ensure(p);
        s.gamesWon += 1;
        s.points += 1;
      });
      gl.forEach((p) => {
        ensure(p).gamesLost += 1;
      });
    });
  }

  return Object.values(byId).sort((a, b) => {
    if (b.points !== a.points) return b.points - a.points;
    if (b.matchWins !== a.matchWins) return b.matchWins - a.matchWins;
    if (b.gamesWon !== a.gamesWon) return b.gamesWon - a.gamesWon;
    return String(a.name).localeCompare(String(b.name));
  });
}

export function extractLadderSessions(scheduleObj, { daysBack = 1, daysForward = 0 } = {}) {
  const events = Array.isArray(scheduleObj)
    ? scheduleObj
    : (scheduleObj && scheduleObj.events) || [];

  const todayNy = nyDateString();
  const allowedDates = new Set();
  for (let i = -daysBack; i <= daysForward; i++) {
    allowedDates.add(addDaysYmd(todayNy, i));
  }

  const map = {};
  events.forEach((e) => {
    const title = e.title || e.DivisionName || e.EventName || '';
    if (!isLadderSessionTitle(title)) return;
    const startTime = e.startTime || e.StartTime || '';
    if (!startTime) return;
    const datePart = startTime.substring(0, 10);
    if (!allowedDates.has(datePart)) return;

    const eventId = String(e.eventId || e.EventId || '').split('_')[0];
    const key = `${eventId}_${startTime}`;
    if (!map[key]) {
      map[key] = {
        sessionKey: key,
        eventId,
        title: String(title).trim(),
        startTime,
        endTime: e.endTime || e.EndTime || '',
        playerCount: 0,
        players: new Map()
      };
    }
    let pName = e.playerName;
    if (!pName) {
      const f = e.FirstName || e.MemberFirstName || '';
      const l = e.LastName || e.MemberLastName || '';
      if (f) pName = `${f} ${l ? String(l).charAt(0) : ''}`.trim();
      else if (e.MemberName) pName = e.MemberName;
    }
    if (pName) {
      const name = displayName(pName);
      const playerId = normalizePlayerId(name);
      if (playerId && !map[key].players.has(playerId)) {
        map[key].players.set(playerId, {
          playerId,
          name,
          checkedIn: e.checkedIn === true || e.IsCheckedIn === true
        });
      }
    }
  });

  return Object.values(map)
    .map((s) => {
      const players = Array.from(s.players.values()).sort((a, b) =>
        a.name.localeCompare(b.name)
      );
      return {
        sessionKey: s.sessionKey,
        eventId: s.eventId,
        title: s.title,
        startTime: s.startTime,
        endTime: s.endTime,
        playerCount: players.length,
        players
      };
    })
    .sort((a, b) => String(a.startTime).localeCompare(String(b.startTime)));
}

async function readJsonKv(env, key, fallback) {
  if (!env.IPX_DATA) return fallback;
  try {
    const raw = await env.IPX_DATA.get(key);
    if (!raw) return fallback;
    return JSON.parse(raw);
  } catch (_) {
    return fallback;
  }
}

async function writeJsonKv(env, key, value) {
  const nowIso = new Date().toISOString();
  await env.IPX_DATA.put(key, JSON.stringify(value), {
    metadata: { lastUpdated: nowIso }
  });
  return nowIso;
}

export async function handleLadderRequest(request, env, corsHeaders = {}) {
  const url = new URL(request.url);
  const method = request.method.toUpperCase();
  const headers = {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-cache, no-store, must-revalidate',
    ...corsHeaders
  };

  if (method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  const json = (body, status = 200, extra = {}) =>
    new Response(JSON.stringify(body, null, 2), {
      status,
      headers: { ...headers, ...extra }
    });

  const period = getPeriodInfo();
  const action = (url.searchParams.get('action') || '').toLowerCase();

  // --- GET ---
  if (method === 'GET') {
    if (action === 'period' || action === '') {
      // default GET without action → standings (TV-friendly)
      if (!action) {
        // fall through to standings below when action empty and no other intent
      }
    }

    if (action === 'sessions' || action === 'roster') {
      let scheduleObj = null;
      if (env.IPX_DATA) {
        try {
          const raw = await env.IPX_DATA.get('schedule_latest');
          if (raw) scheduleObj = JSON.parse(raw);
        } catch (_) {}
      }
      if (!scheduleObj) {
        return json({
          period,
          sessions: [],
          message: 'Schedule not available in KV yet.'
        });
      }

      const daysBack = Math.min(7, Math.max(0, parseInt(url.searchParams.get('daysBack') || '1', 10) || 1));
      const sessions = extractLadderSessions(scheduleObj, { daysBack, daysForward: 0 });

      if (action === 'roster') {
        const sessionKey = url.searchParams.get('sessionKey') || '';
        const eventId = url.searchParams.get('eventId') || '';
        const startTime = url.searchParams.get('startTime') || '';
        let session =
          sessions.find((s) => s.sessionKey === sessionKey) ||
          sessions.find(
            (s) =>
              (!eventId || s.eventId === eventId) &&
              (!startTime || s.startTime === startTime)
          );
        if (!session) {
          return json({ error: 'Session not found for ladder filter.', period, sessions }, 404);
        }
        return json({
          period,
          session: {
            sessionKey: session.sessionKey,
            eventId: session.eventId,
            title: session.title,
            startTime: session.startTime,
            endTime: session.endTime,
            playerCount: session.playerCount
          },
          players: session.players,
          source: 'schedule_latest'
        });
      }

      return json({
        period,
        filter: SESSION_TITLE_NEEDLE,
        sessions,
        scheduleDate: scheduleObj.date || null,
        lastUpdated: scheduleObj.lastUpdated || null
      });
    }

    if (action === 'matches') {
      const store = await readJsonKv(env, MATCHES_KV_KEY, { periods: {}, lastUpdated: null });
      const periodId = url.searchParams.get('periodId') || period.periodId;
      const bucket = (store.periods && store.periods[periodId]) || { matches: [] };
      return json({
        period: periodId === period.periodId ? period : { periodId, ...bucket.meta },
        matches: bucket.matches || [],
        lastUpdated: store.lastUpdated
      });
    }

    if (action === 'period') {
      return json({ period, scoring: { matchWin: 3, gameWin: 1, gameTo: 11, winBy: 2 } });
    }

    // standings (default)
    const standingsStore = await readJsonKv(env, STANDINGS_KV_KEY, {
      periodId: null,
      standings: [],
      lastUpdated: null
    });
    const matchesStore = await readJsonKv(env, MATCHES_KV_KEY, { periods: {}, lastUpdated: null });
    const bucket = (matchesStore.periods && matchesStore.periods[period.periodId]) || {
      matches: []
    };
    let standings = standingsStore.periodId === period.periodId ? standingsStore.standings : [];
    if (!standings.length && bucket.matches && bucket.matches.length) {
      standings = recomputeStandings(bucket.matches);
    }

    return json({
      period,
      scoring: { matchWin: 3, gameWin: 1, gameTo: 11, winBy: 2 },
      standings,
      matchCount: (bucket.matches || []).length,
      lastUpdated: standingsStore.lastUpdated || matchesStore.lastUpdated
    });
  }

  // --- POST: submit match ---
  if (method === 'POST') {
    if (!env.IPX_DATA) {
      return json({ success: false, error: 'Cloudflare KV IPX_DATA binding not found.' }, 500);
    }

    let payload;
    try {
      payload = await request.json();
    } catch (_) {
      return json({ success: false, error: 'Invalid JSON body.' }, 400);
    }

    const teamA = Array.isArray(payload.teamA) ? payload.teamA : [];
    const teamB = Array.isArray(payload.teamB) ? payload.teamB : [];
    if (teamA.length !== 2 || teamB.length !== 2) {
      return json({ success: false, error: 'Need exactly 2 players per team (4 total).' }, 400);
    }

    const normalizeTeam = (team) =>
      team.map((p) => {
        const name = displayName(p.name || p);
        const playerId = p.playerId || normalizePlayerId(name);
        return { playerId, name };
      });

    const normA = normalizeTeam(teamA);
    const normB = normalizeTeam(teamB);
    const ids = [...normA, ...normB].map((p) => p.playerId);
    if (ids.some((id) => !id) || new Set(ids).size !== 4) {
      return json({ success: false, error: 'Four distinct players required.' }, 400);
    }

    const scored = scoreMatch(payload.games || []);
    if (!scored.ok) {
      return json({ success: false, error: scored.error }, 400);
    }

    const nowIso = new Date().toISOString();
    const match = {
      id: `m_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`,
      periodId: period.periodId,
      createdAt: nowIso,
      sessionKey: payload.sessionKey || '',
      eventId: payload.eventId || '',
      sessionTitle: payload.sessionTitle || SESSION_TITLE_NEEDLE,
      startTime: payload.startTime || '',
      teamA: normA,
      teamB: normB,
      games: scored.games.map(({ a, b, winner }) => ({ a, b, winner })),
      winsA: scored.winsA,
      winsB: scored.winsB,
      matchWinner: scored.matchWinner,
      author: payload.author || 'Court Tablet'
    };

    const store = await readJsonKv(env, MATCHES_KV_KEY, { periods: {}, lastUpdated: null });
    if (!store.periods) store.periods = {};
    if (!store.periods[period.periodId]) {
      store.periods[period.periodId] = {
        meta: {
          periodId: period.periodId,
          periodStart: period.periodStart,
          periodEnd: period.periodEnd,
          nextResetSunday: period.nextResetSunday
        },
        matches: []
      };
    }
    store.periods[period.periodId].matches.push(match);
    store.lastUpdated = nowIso;

    // Prune very old periods (keep last 6 = ~12 weeks)
    const periodIds = Object.keys(store.periods).sort();
    while (periodIds.length > 6) {
      const drop = periodIds.shift();
      delete store.periods[drop];
    }

    const standings = recomputeStandings(store.periods[period.periodId].matches);
    const standingsPayload = {
      periodId: period.periodId,
      periodStart: period.periodStart,
      periodEnd: period.periodEnd,
      nextResetSunday: period.nextResetSunday,
      standings,
      matchCount: store.periods[period.periodId].matches.length,
      lastUpdated: nowIso
    };

    await writeJsonKv(env, MATCHES_KV_KEY, store);
    await writeJsonKv(env, STANDINGS_KV_KEY, standingsPayload);

    return json({
      success: true,
      match,
      period,
      standings,
      matchCount: standingsPayload.matchCount
    });
  }

  return new Response('Method Not Allowed', { status: 405, headers });
}
