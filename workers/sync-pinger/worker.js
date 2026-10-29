export default {
  // Cron Trigger handler: runs reliably on schedule via Cloudflare edge
  async scheduled(event, env, ctx) {
    ctx.waitUntil(triggerGitHubSync(env));
  },

  // HTTP handler: edge data delivery, manual trigger, and health checks
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // 1. Manual on-demand trigger: /trigger
    if (url.pathname === '/trigger') {
      const key = url.searchParams.get('key');
      if (env.TRIGGER_KEY && key !== env.TRIGGER_KEY) {
        return new Response('Unauthorized: Invalid key', { status: 401 });
      }

      const result = await triggerGitHubSync(env);
      return new Response(JSON.stringify(result, null, 2), {
        headers: { 'Content-Type': 'application/json' }
      });
    }

    // 2. High-speed KV edge delivery for schedule.json
    if (url.pathname === '/data/schedule.json' || url.pathname === '/api/schedule') {
      if (env.IPX_DATA) {
        try {
          const liveData = await env.IPX_DATA.get('schedule_latest');
          if (liveData) {
            return new Response(liveData, {
              headers: {
                'Content-Type': 'application/json; charset=utf-8',
                'Cache-Control': 'public, max-age=10, s-maxage=10',
                'Access-Control-Allow-Origin': '*',
                'X-Data-Source': 'cloudflare-kv'
              }
            });
          }
        } catch (err) {
          console.error('KV read error for schedule_latest:', err);
        }
      }
      // Seamless fallback to static file if KV is empty or during transition
      return fetch(`https://ipxbk.com/data/schedule.json?_t=${Date.now()}`);
    }

    // 3. High-speed KV edge delivery for event-choices.json
    if (url.pathname === '/data/event-choices.json' || url.pathname === '/api/event-choices') {
      if (env.IPX_DATA) {
        try {
          const liveData = await env.IPX_DATA.get('event_choices_latest');
          if (liveData) {
            return new Response(liveData, {
              headers: {
                'Content-Type': 'application/json; charset=utf-8',
                'Cache-Control': 'public, max-age=10, s-maxage=10',
                'Access-Control-Allow-Origin': '*',
                'X-Data-Source': 'cloudflare-kv'
              }
            });
          }
        } catch (err) {
          console.error('KV read error for event_choices_latest:', err);
        }
      }
      return fetch(`https://ipxbk.com/data/event-choices.json?_t=${Date.now()}`);
    }

    // 4. Edge Health Check & KV Status
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
            schedule: 'Every 10 minutes',
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

    return new Response(
      'IPX CourtReserve Sync Pinger & Edge Cache is active.\nEndpoints:\n- /status\n- /trigger\n- /api/schedule\n- /api/event-choices\n',
      { headers: { 'Content-Type': 'text/plain; charset=utf-8' } }
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
