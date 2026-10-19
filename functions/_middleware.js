const AUTH_COOKIE = 'ipx_staff_token';
const VALID_TOKEN = 'c55f0253dcb8aa5fccdb111785e5e38158cad6568778efb0d06b46c40e3d781a'; // SHA-256 of 'ipxstaff'

export async function onRequest(context) {
  const url = new URL(context.request.url);
  const path = url.pathname.toLowerCase();
  const host = url.hostname.toLowerCase();
  const isStaffHost = host.startsWith('staff.');

  // Check auth credentials via cookie or query param
  const cookieHeader = context.request.headers.get('Cookie') || '';
  const hasAuthCookie = cookieHeader.includes(`${AUTH_COOKIE}=${VALID_TOKEN}`);
  const hasAuthQuery =
    url.searchParams.get('auth') === VALID_TOKEN ||
    url.searchParams.get('key') === 'ipxstaff' ||
    url.searchParams.get('pin') === 'ipxstaff';

  // 1. Block sensitive staff data completely on the public domain (ipxbk.com)
  if (!isStaffHost) {
    if (
      path.startsWith('/data/staff_') ||
      path.startsWith('/data/raw_') ||
      path.startsWith('/schedules/')
    ) {
      return new Response('Not Found', {
        status: 404,
        headers: { 'Content-Type': 'text/plain; charset=utf-8' }
      });
    }
  }

  // 2. On staff.ipxbk.com: Enforce authentication for raw JSON & schedule images at the edge
  if (
    path.startsWith('/data/staff_') ||
    path.startsWith('/data/raw_') ||
    path.startsWith('/schedules/')
  ) {
    if (!hasAuthCookie && !hasAuthQuery) {
      return new Response('Access Denied: Please unlock the schedule at https://staff.ipxbk.com first.', {
        status: 401,
        headers: { 'Content-Type': 'text/plain; charset=utf-8' }
      });
    }
  }

  return context.next();
}
