const AUTH_COOKIE = 'ipx_staff_token';
const VALID_TOKEN = 'c55f0253dcb8aa5fccdb111785e5e38158cad6568778efb0d06b46c40e3d781a'; // SHA-256 of 'ipxstaff'

export async function onRequest(context) {
  const url = new URL(context.request.url);
  const path = url.pathname.toLowerCase();
  const host = url.hostname.toLowerCase();
  const isStaffHost = host.startsWith('staff.');

  // Check auth credentials via cookie, query param, or Authorization header
  const cookieHeader = context.request.headers.get('Cookie') || '';
  const authHeader = context.request.headers.get('Authorization') || '';
  const hasAuthCookie = cookieHeader.includes(`${AUTH_COOKIE}=${VALID_TOKEN}`);
  const hasAuthHeader = authHeader === `Bearer ${VALID_TOKEN}` || authHeader === 'Bearer ipxstaff';
  const hasAuthQuery =
    url.searchParams.get('auth') === VALID_TOKEN ||
    url.searchParams.get('key') === 'ipxstaff' ||
    url.searchParams.get('pin') === 'ipxstaff';
  const isAuthed = hasAuthCookie || hasAuthQuery || hasAuthHeader;

  // Protect sensitive staff data & guest rosters: require authentication
  if (
    path.startsWith('/data/staff_') ||
    path.startsWith('/data/raw_') ||
    path.startsWith('/schedules/') ||
    path === '/api/event-guests' ||
    path === '/api/cr-guest-registrations' ||
    path === '/api/cr-waivers'
  ) {
    if (!isAuthed) {
      if (path.startsWith('/api/')) {
        return new Response(JSON.stringify({ error: 'Unauthorized: Staff authentication required.' }), {
          status: 401,
          headers: { 'Content-Type': 'application/json; charset=utf-8', 'Access-Control-Allow-Origin': '*' }
        });
      }
      if (isStaffHost) {
        return new Response('Access Denied: Please unlock the schedule at https://staff.ipxbk.com first.', {
          status: 401,
          headers: { 'Content-Type': 'text/plain; charset=utf-8' }
        });
      } else {
        return new Response('Not Found', {
          status: 404,
          headers: { 'Content-Type': 'text/plain; charset=utf-8' }
        });
      }
    }
  }

  return context.next();
}
