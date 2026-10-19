export async function onRequest(context) {
  const url = new URL(context.request.url);
  const path = url.pathname.toLowerCase();
  const host = url.hostname.toLowerCase();
  const isStaffHost = host.startsWith('staff.');

  // Block sensitive staff data on the public domain (ipxbk.com)
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

  return context.next();
}
