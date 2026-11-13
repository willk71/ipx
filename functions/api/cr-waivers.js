// Cloudflare Pages Function: /api/cr-waivers
// Pulls signed waiver reports from CourtReserve API if credentials and permissions exist.

export async function onRequest(context) {
  const { request, env } = context;
  const url = new URL(request.url);

  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    'Cache-Control': 'no-cache, no-store, must-revalidate'
  };

  if (request.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  // Determine CourtReserve credentials from environment secrets
  const crUser = env.CR_USERNAME || env.CR_USER || '';
  const crPass = env.CR_PASSWORD || env.CR_PASS || '';

  if (!crUser || !crPass) {
    return new Response(
      JSON.stringify({
        success: false,
        error: 'CourtReserve API credentials not configured in Cloudflare environment.',
        help: 'Upload or paste your signed waiver report CSV directly into the page below, or configure CR_USERNAME / CR_PASSWORD in Cloudflare Pages secrets.'
      }, null, 2),
      {
        status: 200, // Return 200 so UI can display friendly instructions without failing fetch
        headers: { 'Content-Type': 'application/json', ...corsHeaders }
      }
    );
  }

  const authHeader = 'Basic ' + btoa(`${crUser}:${crPass}`);
  const userAgent = 'IPX-Staff-Waiver-Sync/1.0';

  // Candidate CourtReserve waiver report endpoints
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
          JSON.stringify({
            success: true,
            endpoint,
            count: records.length,
            waivers: records
          }, null, 2),
          {
            headers: { 'Content-Type': 'application/json', ...corsHeaders }
          }
        );
      } else {
        lastErrorText = await res.text().catch(() => '');
      }
    } catch (err) {
      lastErrorText = err.message;
    }
  }

  // If endpoints returned 401 or 403 (permissions not yet granted)
  return new Response(
    JSON.stringify({
      success: false,
      statusCode: lastStatus,
      error: lastStatus === 403 || lastStatus === 401
        ? 'CourtReserve account does not have permission to access the Waiver API endpoint yet.'
        : `CourtReserve API responded with HTTP ${lastStatus}.`,
      detail: lastErrorText ? lastErrorText.slice(0, 300) : 'Waiver report endpoint not enabled.',
      help: 'No problem! Simply export your Signed Waiver Report CSV from CourtReserve and drag/drop it into the Waiver Report panel below.'
    }, null, 2),
    {
      status: 200,
      headers: { 'Content-Type': 'application/json', ...corsHeaders }
    }
  );
}
