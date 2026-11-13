// Cloudflare Pages Function: /api/cr-guest-registrations
// On-demand fetch of today's event registrations from CourtReserve (Protected with Staff Auth).

const AUTH_COOKIE = 'ipx_staff_token';
const VALID_TOKEN = 'c55f0253dcb8aa5fccdb111785e5e38158cad6568778efb0d06b46c40e3d781a'; // SHA-256 of 'ipxstaff'

export async function onRequest(context) {
  const { request, env } = context;
  const url = new URL(request.url);

  const corsHeaders = {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-cache, no-store, must-revalidate',
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

  // Check KV cache first
  if (env.IPX_DATA) {
    try {
      const kvData = await env.IPX_DATA.get('event_guests_latest');
      if (kvData) {
        let parsed = null;
        try {
          parsed = JSON.parse(kvData);
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
          headers: { ...corsHeaders, 'X-Data-Source': 'cloudflare-kv' }
        });
      }
    } catch (err) {
      console.warn('KV read error for event_guests_latest:', err);
    }
  }

  // Direct CourtReserve API call if credentials exist in Cloudflare environment
  const crUser = env.CR_USERNAME || env.CR_USER || '';
  const crPass = env.CR_PASSWORD || env.CR_PASS || '';

  if (crUser && crPass) {
    try {
      const nyDateStr = new Date().toLocaleDateString('en-CA', { timeZone: 'America/New_York' });
      const targetDate = url.searchParams.get('date') || nyDateStr;
      const fromUtc = `${targetDate}T00:00:00Z`;
      const toUtc = `${targetDate}T23:59:59Z`;

      const apiUrl = `https://api.courtreserve.com/api/v1/eventregistrationreport/listactive?eventDateFrom=${fromUtc}&eventDateTo=${toUtc}&includeCourts=true&includePartnerInfo=true&includeGuests=true`;
      const authHeader = 'Basic ' + btoa(`${crUser}:${crPass}`);

      const res = await fetch(apiUrl, {
        method: 'GET',
        headers: {
          'Authorization': authHeader,
          'Accept': 'application/json',
          'User-Agent': 'IPX-Staff-Guest-Sync/1.0'
        }
      });

      if (res.ok) {
        const data = await res.json();
        const items = Array.isArray(data) ? data : (data.Data || data.data || []);
        const guests = [];

        items.forEach(item => {
          if (!item || item.IsPublic === false || item.IsHidden === true) return;
          const eventId = String(item.EventId || item.eventId || '');
          const title = item.DivisionName || item.EventName || item.title || 'Event';
          const startTime = item.StartTime || item.startTime || '';
          const endTime = item.EndTime || item.endTime || '';

          const hostFirst = (item.FirstName || item.MemberFirstName || '').trim();
          const hostLast = (item.LastName || item.MemberLastName || '').trim();
          const hostName = `${hostFirst} ${hostLast}`.trim() || item.MemberName || 'Member';

          const isGuest = Boolean(
            item.IsGuest === true ||
            String(item.IsGuest).toLowerCase() === 'true' ||
            item.GuestName ||
            /\b\(g\)\b|\bguest\b/i.test(hostFirst) ||
            /\b\(g\)\b|\bguest\b/i.test(hostLast)
          );

          if (isGuest) {
            guests.push({
              name: (item.GuestName || `${hostFirst} ${hostLast}`).trim(),
              email: (item.Email || '').toLowerCase().trim(),
              phone: item.Phone || item.CellPhone || '',
              eventId,
              eventTitle: title,
              startTime,
              endTime,
              hostName: hostName || 'Direct Guest',
              checkedIn: Boolean(item.CheckedIn || item.CheckInStatusName === 'Checked-in'),
              source: 'Event Registration'
            });
          }

          // Nested guests
          ['Guests', 'PartnersInfo', 'EventRegistrationGuests', 'Partners'].forEach(key => {
            const nested = item[key];
            if (Array.isArray(nested)) {
              nested.forEach(sub => {
                if (!sub) return;
                const subFirst = (sub.FirstName || sub.MemberFirstName || '').trim();
                const subLast = (sub.LastName || sub.MemberLastName || '').trim();
                const subName = (sub.GuestName || `${subFirst} ${subLast}`).trim() || sub.MemberName || 'Guest';
                guests.push({
                  name: subName,
                  email: (sub.Email || '').toLowerCase().trim(),
                  phone: sub.Phone || sub.CellPhone || '',
                  eventId,
                  eventTitle: title,
                  startTime,
                  endTime,
                  hostName,
                  checkedIn: Boolean(sub.CheckedIn),
                  source: 'Event Guest'
                });
              });
            }
          });
        });

        return new Response(
          JSON.stringify({
            lastUpdated: new Date().toISOString(),
            date: targetDate,
            totalGuests: guests.length,
            guests
          }, null, 2),
          { headers: corsHeaders }
        );
      }
    } catch (err) {
      console.warn('CourtReserve direct fetch error:', err);
    }
  }

  // Fallback response
  return new Response(
    JSON.stringify({
      lastUpdated: new Date().toISOString(),
      totalGuests: 0,
      sessions: [],
      guests: [],
      message: 'No live guest registrations found or waiting for next scheduled sync pass.'
    }, null, 2),
    { headers: corsHeaders }
  );
}
