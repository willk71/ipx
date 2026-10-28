export default {
  // Cron Trigger handler: runs reliably on schedule via Cloudflare edge
  async scheduled(event, env, ctx) {
    ctx.waitUntil(triggerGitHubSync(env));
  },

  // HTTP handler: provides health check and manual 1-click trigger URL
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // Manual on-demand trigger: https://<worker>.workers.dev/trigger?key=YOUR_SECRET
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

    return new Response(
      'IPX CourtReserve Sync Pinger is active.\nSchedule: Every 10 minutes.\nStatus: Ready.',
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
