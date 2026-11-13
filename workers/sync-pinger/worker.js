export default {
  // Cron Trigger handler: runs reliably on schedule via Cloudflare edge (every 3 minutes)
  async scheduled(event, env, ctx) {
    const nyTimeStr = new Date().toLocaleString("en-US", { timeZone: "America/New_York" });
    const nyDate = new Date(nyTimeStr);
    const nyHour = nyDate.getHours();
    const nyMinute = nyDate.getMinutes();

    // Facility is closed 12:00 AM - 6:00 AM ET.
    // Run an hourly check at :00 during off-hours, instead of every 3 minutes.
    if (nyHour >= 0 && nyHour < 6 && nyMinute >= 3) {
      console.log(`Off-hours (${nyHour}:${nyMinute < 10 ? '0' : ''}${nyMinute} ET): skipping automated sync.`);
      return;
    }

    ctx.waitUntil(triggerGitHubSync(env));
  },

  // HTTP handler: edge data delivery, manual trigger, and health checks
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const method = request.method.toUpperCase();

    const corsHeaders = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization',
      'Access-Control-Max-Age': '86400'
    };

    if (method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders });
    }

    // 1. Manual on-demand trigger: /trigger
    if (url.pathname === '/trigger') {
      const key = url.searchParams.get('key');
      if (env.TRIGGER_KEY && key !== env.TRIGGER_KEY) {
        return new Response('Unauthorized: Invalid key', { status: 401, headers: corsHeaders });
      }

      const result = await triggerGitHubSync(env);
      return new Response(JSON.stringify(result, null, 2), {
        headers: { 'Content-Type': 'application/json', ...corsHeaders }
      });
    }

    // 1b. Serve Court Manager UI directly from edge (immune to GitHub Pages build delays)
    if (url.pathname === '/courts' || url.pathname === '/courts.html') {
      try {
        const rawRes = await fetch('https://raw.githubusercontent.com/willk71/ipx/main/courts.html?_t=' + Date.now(), {
          cf: { cacheTtl: 0, cacheEverything: false }
        });
        if (rawRes.ok) {
          const html = await rawRes.text();
          return new Response(html, {
            headers: {
              'Content-Type': 'text/html; charset=utf-8',
              'Cache-Control': 'no-cache, no-store, must-revalidate',
              ...corsHeaders
            }
          });
        }
      } catch (err) {
        return new Response('Error loading Court Manager: ' + err.message, { status: 500, headers: corsHeaders });
      }
    }

    // 1c. Serve Waiver Reconciliation UI directly from edge
    if (url.pathname === '/waivers' || url.pathname === '/waivers.html') {
      try {
        const rawRes = await fetch('https://raw.githubusercontent.com/willk71/ipx/main/waivers.html?_t=' + Date.now(), {
          cf: { cacheTtl: 0, cacheEverything: false }
        });
        if (rawRes.ok) {
          const html = await rawRes.text();
          return new Response(html, {
            headers: {
              'Content-Type': 'text/html; charset=utf-8',
              'Cache-Control': 'no-cache, no-store, must-revalidate',
              ...corsHeaders
            }
          });
        }
      } catch (err) {
        return new Response('Error loading Waiver Manager: ' + err.message, { status: 500, headers: corsHeaders });
      }
    }

    // 1d. CourtReserve Waiver API integration
    if (url.pathname === '/api/cr-waivers') {
      const crUser = env.CR_USERNAME || env.CR_USER || '';
      const crPass = env.CR_PASSWORD || env.CR_PASS || '';

      if (!crUser || !crPass) {
        return new Response(
          JSON.stringify({
            success: false,
            error: 'CourtReserve API credentials not configured in Cloudflare environment.',
            help: 'Upload or paste your signed waiver report CSV directly into the page below, or configure CR_USERNAME / CR_PASSWORD in Cloudflare environment.'
          }, null, 2),
          { status: 200, headers: { 'Content-Type': 'application/json', ...corsHeaders } }
        );
      }

      const authHeader = 'Basic ' + btoa(`${crUser}:${crPass}`);
      const userAgent = 'IPX-Staff-Waiver-Sync/1.0';
      const candidateEndpoints = [
        'https://api.courtreserve.com/api/v1/waiverreport/list',
        'https://api.courtreserve.com/api/v1/waiverreport/listactive',
        'https://api.courtreserve.com/api/v1/waivers/report',
        'https://api.courtreserve.com/api/v1/waivers'
      ];

      let lastStatus = 0;
      let lastErrorText = '';

      for (const endpoint of candidateEndpoints) {
        try {
          const res = await fetch(endpoint, {
            method: 'GET',
            headers: {
              'Authorization': authHeader,
              'Accept': 'application/json',
              'User-Agent': userAgent
            }
          });
          lastStatus = res.status;
          if (res.ok) {
            const data = await res.json();
            const records = Array.isArray(data) ? data : (data.Data || data.data || data.Items || []);
            return new Response(
              JSON.stringify({ success: true, count: records.length, waivers: records }, null, 2),
              { headers: { 'Content-Type': 'application/json', ...corsHeaders } }
            );
          } else {
            lastErrorText = await res.text().catch(() => '');
          }
        } catch (err) {
          lastErrorText = err.message;
        }
      }

      return new Response(
        JSON.stringify({
          success: false,
          statusCode: lastStatus,
          error: lastStatus === 403 || lastStatus === 401
            ? 'CourtReserve account does not have permission to access the Waiver API endpoint yet.'
            : `CourtReserve API responded with HTTP ${lastStatus}.`,
          help: 'No problem! Simply export your Signed Waiver Report CSV from CourtReserve and drag/drop it into the Waiver Report panel.'
        }, null, 2),
        { status: 200, headers: { 'Content-Type': 'application/json', ...corsHeaders } }
      );
    }

    // 2. Manual Court Assignments API: /api/court-assignments
    if (url.pathname === '/api/court-assignments') {
      const KV_KEY = 'manual_court_assignments';

      if (method === 'GET') {
        if (env.IPX_DATA) {
          try {
            const raw = await env.IPX_DATA.get(KV_KEY);
            if (raw) {
              return new Response(raw, {
                headers: {
                  'Content-Type': 'application/json; charset=utf-8',
                  'Cache-Control': 'no-cache, no-store, must-revalidate',
                  'X-Data-Source': 'cloudflare-kv',
                  ...corsHeaders
                }
              });
            }
          } catch (err) {
            console.error('KV read error for manual_court_assignments:', err);
          }
        }
        return new Response(
          JSON.stringify({ lastUpdated: null, sessions: {} }),
          { headers: { 'Content-Type': 'application/json', ...corsHeaders } }
        );
      }

      if (method === 'POST' || method === 'PUT') {
        if (!env.IPX_DATA) {
          return new Response(
            JSON.stringify({ success: false, error: 'Cloudflare KV IPX_DATA binding not found.' }),
            { status: 500, headers: { 'Content-Type': 'application/json', ...corsHeaders } }
          );
        }

        try {
          const payload = await request.json();
          const sessionKey = payload.sessionKey;
          if (!sessionKey) {
            return new Response(
              JSON.stringify({ success: false, error: "Missing required 'sessionKey' field." }),
              { status: 400, headers: { 'Content-Type': 'application/json', ...corsHeaders } }
            );
          }

          let currentData = { lastUpdated: null, sessions: {} };
          try {
            const rawExisting = await env.IPX_DATA.get(KV_KEY);
            if (rawExisting) {
              currentData = JSON.parse(rawExisting);
              if (!currentData.sessions) currentData.sessions = {};
            }
          } catch (_) {}

          const nowIso = new Date().toISOString();
          if (payload.reset === true) {
            delete currentData.sessions[sessionKey];
          } else {
            currentData.sessions[sessionKey] = {
              sessionKey: sessionKey,
              eventId: payload.eventId || '',
              title: payload.title || '',
              startTime: payload.startTime || '',
              endTime: payload.endTime || '',
              allocations: payload.allocations || {},
              courtStatus: payload.courtStatus || {},
              author: payload.author || 'Staff',
              updatedAt: nowIso
            };
          }

          currentData.lastUpdated = nowIso;
          await env.IPX_DATA.put(KV_KEY, JSON.stringify(currentData), {
            metadata: { lastUpdated: nowIso }
          });

          // Invalidate default cache so next schedule fetch picks up overrides instantly
          try {
            const scheduleCacheKey = new Request(new URL('/api/schedule', url.origin));
            await caches.default.delete(scheduleCacheKey);
          } catch (_) {}

          return new Response(
            JSON.stringify({
              success: true,
              action: payload.reset ? 'reset' : 'saved',
              sessionKey: sessionKey,
              timestamp: nowIso
            }),
            { headers: { 'Content-Type': 'application/json', ...corsHeaders } }
          );
        } catch (e) {
          return new Response(
            JSON.stringify({ success: false, error: e.message }),
            { status: 500, headers: { 'Content-Type': 'application/json', ...corsHeaders } }
          );
        }
      }

      return new Response('Method Not Allowed', { status: 405, headers: corsHeaders });
    }

    // 3. High-speed KV edge delivery for schedule.json with live manual override merging
    if (url.pathname === '/data/schedule.json' || url.pathname === '/api/schedule') {
      const cache = caches.default;
      const cacheKey = new Request(new URL(url.pathname, url.origin), request);
      let cachedResp = await cache.match(cacheKey);
      if (cachedResp) {
        return cachedResp;
      }

      if (env.IPX_DATA) {
        try {
          const liveData = await env.IPX_DATA.get('schedule_latest');
          if (liveData) {
            let scheduleObj;
            try {
              scheduleObj = JSON.parse(liveData);
            } catch (_) {
              scheduleObj = null;
            }

            if (scheduleObj) {
              try {
                const rawManual = await env.IPX_DATA.get('manual_court_assignments');
                if (rawManual) {
                  const manualData = JSON.parse(rawManual);
                  const manualSessions = manualData.sessions || {};

                  const groupSlugs = {
                    'Advanced Beginner': 'advbeg',
                    'Intermediate': 'int',
                    'Intermediate+': 'int',
                    'High Intermediate': 'highint',
                    'High Intermediate+': 'highint',
                    'Advanced': 'adv',
                    'Novice / Beginner': 'novice',
                    'Novice/Beginner': 'novice',
                    'Drilling': 'drilling',
                    'Clinic': 'clinic'
                  };

                  const matchesTierStrict = (title, matchStr) => {
                    if (!matchStr) return true;
                    const t = String(title || '').toLowerCase();
                    const m = String(matchStr).toLowerCase().trim();
                    if (m === 'high intermediate' || m === 'high int' || m === 'high intermediate+' || m === 'high int+') {
                      return /\bhigh\s*intermediate\b/.test(t) || /\bhigh\s*int\b/.test(t) || /\bhigh\b/.test(t);
                    }
                    if (m === 'intermediate' || m === 'int' || m === 'intermediate+' || m === 'int+') {
                      return (/\bintermediate\b/.test(t) || /\bint\b/.test(t)) && !/\bhigh\b/.test(t);
                    }
                    if (m === 'advanced beginner' || m === 'adv beg' || m === 'advbeg') {
                      return /\b(advanced|adv)\s*beginner\b/.test(t) || /\badvbeg\b/.test(t);
                    }
                    if (m === 'novice / beginner' || m === 'novice/beginner' || m === 'novice' || m === 'beginner') {
                      return /\bnovice\b/.test(t) || (/\bbeginner\b/.test(t) && !/\badv(?:anced)?\b/.test(t));
                    }
                    if (m === 'drilling' || m === 'drill') {
                      return /\bdrill(?:ing)?\b/.test(t);
                    }
                    if (m === 'clinic' || m === 'clinics') {
                      return /\bclinic[s]?\b/.test(t);
                    }
                    if (m === 'advanced' || m === 'adv') {
                      return (/\badvanced\b/.test(t) || /\badv\b/.test(t)) && !/\bbeginner\b/.test(t) && !/\bbeg\b/.test(t);
                    }
                    return new RegExp('\\b' + m.replace(/[+*?^$(){}|[\]\\]/g, '\\$&') + '\\b', 'i').test(t);
                  };

                  Object.values(manualSessions).forEach(man => {
                    const eId = String(man.eventId || '').trim();
                    const sTime = String(man.startTime || '').trim();
                    const allocs = man.allocations || {};

                    (scheduleObj.events || []).forEach(ev => {
                      const evId = String(ev.eventId || '').trim();
                      const evStart = String(ev.startTime || '').trim();
                      const matchesId = eId && (evId === eId || evId.startsWith(`${eId}_`));
                      const matchesTime = !sTime || evStart === sTime;

                      if (matchesId && matchesTime) {
                        for (const [tier, courts] of Object.entries(allocs)) {
                          const slug = groupSlugs[tier] || '';
                          const isTierMatch = (slug && evId.endsWith(`_${slug}`)) || matchesTierStrict(ev.title, tier);
                          if (isTierMatch && Array.isArray(courts)) {
                            ev.courts = courts.map(c => `Court ${c}`);
                            ev.manualOverride = true;
                          }
                        }
                      }
                    });

                    // Determine session end time to prevent overrides from persisting beyond their session window
                    let endStr = '';
                    if (man.endTime && man.endTime.includes('T')) {
                      endStr = man.endTime.split('T')[1].substring(0, 5);
                    } else {
                      const matchEv = (scheduleObj.events || []).find(ev => {
                        const evId = String(ev.eventId || '').trim();
                        const evStart = String(ev.startTime || '').trim();
                        return eId && (evId === eId || evId.startsWith(`${eId}_`)) && (!sTime || evStart === sTime);
                      });
                      if (matchEv && matchEv.endTime && matchEv.endTime.includes('T')) {
                        endStr = matchEv.endTime.split('T')[1].substring(0, 5);
                      } else if (sTime && sTime.includes('T')) {
                        const parts = sTime.split('T')[1].substring(0, 5).split(':').map(Number);
                        const endMin = (parts[0] || 0) * 60 + (parts[1] || 0) + 120;
                        const h = Math.floor(endMin / 60) % 24;
                        const m = endMin % 60;
                        endStr = `${h < 10 ? '0' : ''}${h}:${m < 10 ? '0' : ''}${m}`;
                      }
                    }

                    if (!Array.isArray(scheduleObj.courtOverrides)) {
                      scheduleObj.courtOverrides = [];
                    }
                    for (const [tier, courts] of Object.entries(allocs)) {
                      if (Array.isArray(courts) && courts.length > 0) {
                        scheduleObj.courtOverrides.push({
                          match: tier,
                          start: sTime && sTime.includes('T') ? sTime.split('T')[1].substring(0, 5) : '',
                          end: endStr,
                          courts: courts
                        });
                      }
                    }
                  });
                }
              } catch (_) {}

              const mergedBody = JSON.stringify(scheduleObj);
              const resp = new Response(mergedBody, {
                headers: {
                  'Content-Type': 'application/json; charset=utf-8',
                  'Cache-Control': 'public, max-age=10, s-maxage=10',
                  'Access-Control-Allow-Origin': '*',
                  'X-Data-Source': 'cloudflare-kv-merged'
                }
              });
              ctx.waitUntil(cache.put(cacheKey, resp.clone()));
              return resp;
            }
          }
        } catch (err) {
          console.error('KV read error for schedule_latest:', err);
        }
      }
      return fetch(`https://ipxbk.com/data/schedule.json?_t=${Date.now()}`);
    }

    // 4. High-speed KV edge delivery for event-choices.json
    if (url.pathname === '/data/event-choices.json' || url.pathname === '/api/event-choices') {
      const cache = caches.default;
      const cacheKey = new Request(new URL(url.pathname, url.origin), request);
      let cachedResp = await cache.match(cacheKey);
      if (cachedResp) {
        return cachedResp;
      }

      if (env.IPX_DATA) {
        try {
          const liveData = await env.IPX_DATA.get('event_choices_latest');
          if (liveData) {
            const resp = new Response(liveData, {
              headers: {
                'Content-Type': 'application/json; charset=utf-8',
                'Cache-Control': 'public, max-age=15, s-maxage=15',
                'Access-Control-Allow-Origin': '*',
                'X-Data-Source': 'cloudflare-kv'
              }
            });
            ctx.waitUntil(cache.put(cacheKey, resp.clone()));
            return resp;
          }
        } catch (err) {
          console.error('KV read error for event_choices_latest:', err);
        }
      }
      return fetch(`https://ipxbk.com/data/event-choices.json?_t=${Date.now()}`);
    }

    // 5. Edge Health Check & KV Status
    if (url.pathname === '/status') {
      let kvStatus = 'not_bound';
      let scheduleSize = 0;
      let lastUpdated = null;

      if (env.IPX_DATA) {
        kvStatus = 'bound';
        try {
          const sample = await env.IPX_DATA.get('schedule_latest');
          if (sample) {
            scheduleSize = sample.length;
            const parsed = JSON.parse(sample);
            lastUpdated = parsed.lastUpdated || null;
            kvStatus = 'active_with_data';
          } else {
            kvStatus = 'bound_but_empty';
          }
        } catch (e) {
          kvStatus = `error: ${e.message}`;
        }
      }

      return new Response(
        JSON.stringify(
          {
            pinger: 'active',
            schedule: 'Every 3 minutes (6am-12am ET, hourly overnight; Events every ~9m)',
            kv_status: kvStatus,
            schedule_bytes: scheduleSize,
            last_schedule_sync: lastUpdated,
            server_time_utc: new Date().toISOString()
          },
          null,
          2
        ),
        {
          headers: {
            'Content-Type': 'application/json; charset=utf-8',
            'Access-Control-Allow-Origin': '*'
          }
        }
      );
    }

    // Fallback: simple text splash
    return new Response(
      'IPX CourtReserve Sync Pinger & Edge Cache is active.\nSchedule: Every 3 minutes (Events every ~9-10 min).\nEndpoints:\n- /status\n- /trigger\n- /api/schedule\n- /api/event-choices\n- /api/court-assignments\n',
      {
        headers: { 'Content-Type': 'text/plain; charset=utf-8', 'Access-Control-Allow-Origin': '*' }
      }
    );
  }
};

async function triggerGitHubSync(env) {
  const GITHUB_OWNER = 'willk71';
  const GITHUB_REPO = 'ipx';
  const WORKFLOW_ID = 'sync-courtreserve.yml';

  if (!env.GITHUB_TOKEN) {
    console.error('Error: GITHUB_TOKEN secret is not set in Cloudflare Worker.');
    return { success: false, error: 'GITHUB_TOKEN secret not configured.' };
  }

  const dispatchUrl = `https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/actions/workflows/${WORKFLOW_ID}/dispatches`;

  try {
    const res = await fetch(dispatchUrl, {
      method: 'POST',
      headers: {
        'Accept': 'application/vnd.github+json',
        'Authorization': `Bearer ${env.GITHUB_TOKEN}`,
        'User-Agent': 'IPX-Cloudflare-Sync-Pinger',
        'X-GitHub-Api-Version': '2022-11-28'
      },
      body: JSON.stringify({ ref: 'main' })
    });

    const isSuccess = res.status === 204;
    console.log(`GitHub workflow dispatch: HTTP ${res.status} (${isSuccess ? 'Success' : 'Failed'})`);
    return {
      success: isSuccess,
      status: res.status,
      timestamp: new Date().toISOString()
    };
  } catch (err) {
    console.error('Fetch error triggering GitHub workflow:', err);
    return { success: false, error: err.message };
  }
}
