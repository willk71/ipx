// Cloudflare Pages Function: /api/event-guests
// Serves extracted event & reservation guests from Cloudflare KV.

export async function onRequest(context) {
  const corsHeaders = {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'public, max-age=30, s-maxage=30',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, OPTIONS'
  };

  if (context.request.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    if (context.env.IPX_DATA) {
      const kvData = await context.env.IPX_DATA.get('event_guests_latest');
      if (kvData) {
        return new Response(kvData, {
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
