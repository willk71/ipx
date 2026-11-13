// Cloudflare Pages Function: /api/event-guests
// Serves extracted event & reservation guests from Cloudflare KV (Protected with Staff Auth).

const AUTH_COOKIE = 'ipx_staff_token';
const VALID_TOKEN = 'c55f0253dcb8aa5fccdb111785e5e38158cad6568778efb0d06b46c40e3d781a'; // SHA-256 of 'ipxstaff'

export async function onRequest(context) {
  const { request, env } = context;
  const url = new URL(request.url);

  const corsHeaders = {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store, no-cache, must-revalidate',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, OPTIONS'
  };

  if (request.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  // Verify staff authentication
  const cookieHeader = request.headers.get('Cookie') || '';
  const authHeader = request.headers.get('Authorization') || '';
  const isAuthed =
    cookieHeader.includes(`${AUTH_COOKIE}=${VALID_TOKEN}`) ||
    authHeader === `Bearer ${VALID_TOKEN}` ||
    authHeader === 'Bearer ipxstaff' ||
    url.searchParams.get('auth') === VALID_TOKEN ||
    url.searchParams.get('key') === 'ipxstaff' ||
    url.searchParams.get('pin') === 'ipxstaff';

  if (!isAuthed) {
    return new Response(
      JSON.stringify({ error: 'Unauthorized: Staff authentication required to access guest roster.' }),
      { status: 401, headers: corsHeaders }
    );
  }

  try {
    if (env.IPX_DATA) {
      const kvData = await env.IPX_DATA.get('event_guests_latest');
      if (kvData) {
        let parsed = null;
        try {
          parsed = JSON.parse(kvData);
          // Defense-in-depth: Ensure NO email or phone is ever returned even if present in legacy KV
          if (parsed && Array.isArray(parsed.guests)) {
            parsed.guests = parsed.guests.map(g => ({
              name: g.name || '',
              eventId: g.eventId || '',
              eventTitle: g.eventTitle || '',
              startTime: g.startTime || '',
              endTime: g.endTime || '',
              hostName: g.hostName || '',
              checkedIn: Boolean(g.checkedIn),
              source: g.source || 'Event Registration'
            }));
          }
        } catch (_) {}

        const outBody = parsed ? JSON.stringify(parsed, null, 2) : kvData;
        return new Response(outBody, {
          headers: {
            ...corsHeaders,
            'X-Data-Source': 'cloudflare-kv'
          }
        });
      }
    }
  } catch (err) {
    console.error('KV read error for event_guests_latest:', err);
  }

  // Fallback if KV not yet populated
  return new Response(
    JSON.stringify({
      lastUpdated: new Date().toISOString(),
      totalGuests: 0,
      sessions: [],
      guests: [],
      message: 'No guests currently registered or awaiting sync.'
    }, null, 2),
    { headers: corsHeaders }
  );
}
